import numpy as np
import pandas as pd

from fuelcast.config import FUELS, SETTINGS
from fuelcast.domain.advisor import advise, detect_shock
from fuelcast.domain.cleaning import clean_market, normalize_units
from fuelcast.domain.evaluation import trainable
from fuelcast.domain.features import build_cycles, feature_list, fuel_frame
from fuelcast.domain.models import HybridModel
from fuelcast.infrastructure import database as db
from fuelcast.infrastructure.artifacts import write_csv

SCENARIOS = {
    "brent_spike_15": {"brent": 1.15, "mops_gasoil": 1.15, "usdphp": 1.00},
    "brent_crash_20": {"brent": 0.80, "mops_gasoil": 0.80, "usdphp": 1.00},
    "peso_slide_4": {"brent": 1.00, "mops_gasoil": 1.00, "usdphp": 1.04},
    "diesel_squeeze": {"brent": 1.05, "mops_gasoil": 1.18, "usdphp": 1.01},
}


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
    write_csv(out, "stress_tests")
    return out
