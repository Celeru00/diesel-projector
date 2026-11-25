import json
import pickle
from dataclasses import asdict

import numpy as np
import pandas as pd

from fuelcast import db
from fuelcast.advisor import PERSONAS, advise, detect_shock
from fuelcast.analysis import compare_to_baselines, failure_breakdown, failure_cases
from fuelcast.clean import clean_market, normalize_units
from fuelcast.config import DATA_DIR, FUELS, REPORT_DIR, SETTINGS
from fuelcast.evaluate import summarize, trainable, walk_forward
from fuelcast.features import build_cycles, feature_list, fuel_frame
from fuelcast.ingest import fetch_market, load_cached_market, load_doe
from fuelcast.models import HybridModel

SCENARIOS = {
    "brent_spike_15": {"brent": 1.15, "mops_gasoil": 1.15, "usdphp": 1.00},
    "brent_crash_20": {"brent": 0.80, "mops_gasoil": 0.80, "usdphp": 1.00},
    "peso_slide_4": {"brent": 1.00, "mops_gasoil": 1.00, "usdphp": 1.04},
    "diesel_squeeze": {"brent": 1.05, "mops_gasoil": 1.18, "usdphp": 1.01},
}


def stage_ingest(offline: bool = False, start: str = SETTINGS.start) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    raw = load_cached_market() if offline else fetch_market(start)
    doe = load_doe()
    db.write_table(raw, "market_raw")
    if doe is not None:
        db.write_table(doe, "doe_adjustments", index=False)
    return raw, doe


def stage_clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    cleaned, report = clean_market(raw)
    daily = normalize_units(cleaned)
    db.write_table(daily, "market_daily")
    return daily, report


def stage_features(daily: pd.DataFrame, doe: pd.DataFrame | None) -> dict[str, pd.DataFrame]:
    cycles = build_cycles(daily)
    db.write_table(cycles, "cycles")
    frames = {f: fuel_frame(cycles, f, doe) for f in FUELS}
    for f, fr in frames.items():
        db.write_table(fr, f"features_{f}")
    return frames


def shock_mask(frame: pd.DataFrame) -> pd.Series:
    return (frame["brent_trend5_pct"].abs() >= SETTINGS.shock_brent_pct) | (frame["brent_vol_z"] >= SETTINGS.shock_vol_z)


def stage_evaluate(frames: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    summaries = []
    backtests = {}
    for fuel, frame in frames.items():
        bt = walk_forward(frame)
        backtests[fuel] = bt
        db.write_table(bt, f"backtest_{fuel}", index=False)
        bt_shock = bt["effective_date"].map(shock_mask(frame)).fillna(False).astype(bool)
        s = summarize(bt, bt_shock)
        s.insert(0, "fuel", fuel)
        summaries.append(s)
    out = pd.concat(summaries, ignore_index=True)
    db.write_table(out, "metrics", index=False)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(REPORT_DIR / "metrics.csv", index=False)
    return out, backtests


def stage_analysis(backtests: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    tables = {"baseline_comparison": [], "failure_cases": [], "failure_breakdown": []}
    for fuel, bt in backtests.items():
        for name, df in (
            ("baseline_comparison", compare_to_baselines(bt)),
            ("failure_cases", failure_cases(bt, "hybrid")),
            ("failure_breakdown", failure_breakdown(bt, models=("hybrid", "linreg", "knn", "persistence"))),
        ):
            df.insert(0, "fuel", fuel)
            tables[name].append(df)
    out = {k: pd.concat(v, ignore_index=True) for k, v in tables.items()}
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    for name, df in out.items():
        db.write_table(df, name, index=False)
        df.to_csv(REPORT_DIR / f"{name}.csv", index=False)
    return out


def latest_row(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.dropna(subset=feature_list()).iloc[[-1]]


def stage_train_predict(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    feats = feature_list()
    rows = []
    for fuel, frame in frames.items():
        data = trainable(frame, feats)
        target = latest_row(frame)
        train = data[data.index < target.index[0]]
        model = HybridModel().fit(train[feats], train["target"])
        with open(DATA_DIR / f"model_{fuel}.pkl", "wb") as fh:
            pickle.dump(model, fh)
        p = model.predict(target[feats]).iloc[0].to_dict()
        t = target.iloc[0]
        shock = detect_shock(t["brent_trend5_pct"], t["brent_vol_z"], SETTINGS.shock_brent_pct, SETTINGS.shock_vol_z)
        rows.append(
            {
                "fuel": fuel,
                "effective_date": target.index[0],
                "asof": t["asof"],
                "actual_if_known": t["target"],
                "target_source": t["target_source"],
                "brent_trend5_pct": t["brent_trend5_pct"],
                "brent_vol_z": t["brent_vol_z"],
                "shock_reason": shock,
                "n_train": len(train),
                **p,
            }
        )
    out = pd.DataFrame(rows)
    db.write_table(out, "forecasts", index=False)
    return out


def stage_advise(forecasts: pd.DataFrame, personas=tuple(PERSONAS), shock_override: str | None = None) -> list[dict]:
    results = []
    by_fuel = forecasts.set_index("fuel")
    for persona in personas:
        fuel = PERSONAS[persona]["fuel"]
        row = by_fuel.loc[fuel].to_dict()
        shock = shock_override or (row["shock_reason"] if isinstance(row["shock_reason"], str) else None)
        a = advise(row, persona, shock_reason=shock)
        results.append({"effective_date": str(pd.Timestamp(row["effective_date"]).date()), **asdict(a)})
    db.write_table(
        pd.DataFrame([{**r, "actions": json.dumps(r["actions"]), "facts": json.dumps(r["facts"], default=str), "trace": json.dumps(r["trace"])} for r in results]),
        "advice",
        index=False,
    )
    return results


def perturb_last_week(raw: pd.DataFrame, factors: dict[str, float], days: int = 5) -> pd.DataFrame:
    out = raw.copy()
    ramp = np.linspace(0, 1, days + 1)[1:]
    for col, f in factors.items():
        out.iloc[-days:, out.columns.get_loc(col)] = out[col].iloc[-days:].to_numpy() * (1 + (f - 1) * ramp)
    return out


def stage_stress(raw: pd.DataFrame, doe: pd.DataFrame | None) -> pd.DataFrame:
    rows = []
    base, _ = clean_market(raw)
    last_asof = build_cycles(normalize_units(base))["asof"].max()
    base = base[base.index <= last_asof]
    for name, factors in {"baseline": {}, **SCENARIOS}.items():
        cleaned = perturb_last_week(base, factors) if factors else base
        daily = normalize_units(cleaned)
        cycles = build_cycles(daily)
        frames = {f: fuel_frame(cycles, f, doe) for f in FUELS}
        feats = feature_list()
        for fuel, frame in frames.items():
            data = trainable(frame, feats)
            last_asof = frame["asof"].max()
            target = frame[frame["asof"] == last_asof].dropna(subset=feats).iloc[[-1]]
            train = data[data.index < target.index[0]]
            p = HybridModel().fit(train[feats], train["target"]).predict(target[feats]).iloc[0].to_dict()
            t = target.iloc[0]
            shock = detect_shock(t["brent_trend5_pct"], t["brent_vol_z"], SETTINGS.shock_brent_pct, SETTINGS.shock_vol_z)
            persona = "fleet"
            a = advise(p, persona, fuel=fuel, shock_reason=shock)
            rows.append(
                {
                    "scenario": name,
                    "brent_trend5_pct": t["brent_trend5_pct"],
                    "implied_partial": t["implied_partial"],
                    "pred": p["pred"],
                    "low": p["low"],
                    "high": p["high"],
                    "confidence": round(p["confidence"], 3),
                    "shock": shock or "",
                    "persona": persona,
                    "timing": a.facts.get("timing"),
                    "headline": a.headline,
                }
            )
    out = pd.DataFrame(rows)
    db.write_table(out, "stress_tests", index=False)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(REPORT_DIR / "stress_tests.csv", index=False)
    return out


def run_evaluation(offline: bool = True) -> dict:
    raw, doe = stage_ingest(offline)
    daily, clean_report = stage_clean(raw)
    frames = stage_features(daily, doe)
    metrics, backtests = stage_evaluate(frames)
    return {"metrics": metrics, "analysis": stage_analysis(backtests), "doe_loaded": doe is not None}


def run_all(offline: bool = False, shock_override: str | None = None, evaluate: bool = True, stress: bool = True) -> dict:
    raw, doe = stage_ingest(offline)
    daily, clean_report = stage_clean(raw)
    frames = stage_features(daily, doe)
    metrics, backtests = stage_evaluate(frames) if evaluate else (None, None)
    analysis = stage_analysis(backtests) if evaluate else None
    forecasts = stage_train_predict(frames)
    advice = stage_advise(forecasts, shock_override=shock_override)
    stress_df = stage_stress(raw, doe) if stress else None
    return {
        "clean_report": clean_report,
        "frames": frames,
        "metrics": metrics,
        "analysis": analysis,
        "forecasts": forecasts,
        "advice": advice,
        "stress": stress_df,
        "doe_loaded": doe is not None,
    }
