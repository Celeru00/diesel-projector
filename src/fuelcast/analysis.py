import numpy as np
import pandas as pd
from scipy.stats import binomtest, norm

from fuelcast.config import ASOF_DAY, SETTINGS
from fuelcast.features import direction

BASELINES = ("persistence", "majority")
NEAR_FLAT = 0.25
LARGE_MOVE = 1.50
HIGH_CONF = 0.75


def _paired(bt: pd.DataFrame, a: str, b: str) -> pd.DataFrame:
    left = bt[bt["model"] == a].set_index("effective_date")
    right = bt[bt["model"] == b].set_index("effective_date")
    return left.join(right, suffixes=("_a", "_b"), how="inner")


def diebold_mariano(err_a: np.ndarray, err_b: np.ndarray) -> tuple[float, float]:
    d = np.asarray(err_b) ** 2 - np.asarray(err_a) ** 2
    n = len(d)
    if n < 3 or np.allclose(d.std(ddof=1), 0):
        return float("nan"), float("nan")
    stat = d.mean() / np.sqrt(d.var(ddof=1) / n)
    return float(stat), float(2 * (1 - norm.cdf(abs(stat))))


def mcnemar(correct_a: np.ndarray, correct_b: np.ndarray) -> tuple[int, int, float]:
    a_only = int((correct_a & ~correct_b).sum())
    b_only = int((~correct_a & correct_b).sum())
    if a_only + b_only == 0:
        return a_only, b_only, 1.0
    return a_only, b_only, float(binomtest(min(a_only, b_only), a_only + b_only, 0.5).pvalue)


def compare_to_baselines(bt: pd.DataFrame, baselines=BASELINES) -> pd.DataFrame:
    rows = []
    for model in [m for m in bt["model"].unique() if m not in baselines]:
        for base in baselines:
            j = _paired(bt, model, base)
            if j.empty:
                continue
            ea, eb = j["pred_a"] - j["actual_a"], j["pred_b"] - j["actual_b"]
            ca = (j["pred_direction_a"] == j["actual_direction_a"]).to_numpy()
            cb = (j["pred_direction_b"] == j["actual_direction_b"]).to_numpy()
            mae_a, mae_b = ea.abs().mean(), eb.abs().mean()
            rmse_a, rmse_b = np.sqrt((ea**2).mean()), np.sqrt((eb**2).mean())
            dm, dm_p = diebold_mariano(ea.to_numpy(), eb.to_numpy())
            a_only, b_only, mc_p = mcnemar(ca, cb)
            rows.append(
                {
                    "model": model,
                    "baseline": base,
                    "n": len(j),
                    "dir_acc_model": ca.mean(),
                    "dir_acc_baseline": cb.mean(),
                    "dir_acc_gain": ca.mean() - cb.mean(),
                    "mae_model": mae_a,
                    "mae_baseline": mae_b,
                    "mae_skill": 1 - mae_a / mae_b if mae_b else float("nan"),
                    "rmse_skill": 1 - rmse_a / rmse_b if rmse_b else float("nan"),
                    "win_rate": float((ea.abs() < eb.abs()).mean()),
                    "dm_stat": dm,
                    "dm_pvalue": dm_p,
                    "mcnemar_model_only": a_only,
                    "mcnemar_baseline_only": b_only,
                    "mcnemar_pvalue": mc_p,
                    "significant": bool((dm_p < 0.05 and dm > 0) or (mc_p < 0.05 and a_only > b_only)),
                }
            )
    return pd.DataFrame(rows)


def tag_conditions(bt: pd.DataFrame) -> pd.DataFrame:
    out = bt.copy()
    err = out["pred"] - out["actual"]
    out["abs_error"] = err.abs()
    out["shock"] = (out["brent_trend5_pct"].abs() >= SETTINGS.shock_brent_pct) | (out["brent_vol_z"] >= SETTINGS.shock_vol_z)
    out["turning_point"] = direction(out["lag1"].fillna(0)) != out["actual_direction"]
    out["near_flat"] = out["actual"].abs() <= NEAR_FLAT
    out["large_move"] = out["actual"].abs() >= LARGE_MOVE
    out["high_confidence"] = out["confidence"] >= HIGH_CONF
    out["late_reversal"] = np.sign(out["implied_partial"]) != np.sign(out["actual"])
    out["wrong_direction"] = out["pred_direction"] != out["actual_direction"]
    mae = out.groupby("model")["abs_error"].transform("mean")
    out["big_miss"] = ~out["wrong_direction"] & (out["abs_error"] > np.maximum(2 * mae, 0.5))
    out["outside_interval"] = (out["actual"] < out["low"]) | (out["actual"] > out["high"])
    out["failure"] = out["wrong_direction"] | out["big_miss"]
    return out


def _cause(r) -> str:
    causes = []
    if r["wrong_direction"] and r["near_flat"]:
        causes.append(f"tiny move (within ±₱{NEAR_FLAT:.2f})")
    if r["late_reversal"]:
        causes.append(f"prices reversed after {ASOF_DAY}")
    if r["shock"]:
        causes.append("shock week")
    if r["turning_point"]:
        causes.append("direction changed from last week")
    if r["large_move"] and not r["wrong_direction"]:
        causes.append("large move, size under-predicted" if abs(r["pred"]) < abs(r["actual"]) else "large move, size over-predicted")
    if r["high_confidence"] and r["wrong_direction"]:
        causes.append("overconfident")
    text = "; ".join(causes)
    return text[:1].upper() + text[1:] if text else "Not explained by tracked conditions"


def failure_cases(bt: pd.DataFrame, model: str = "hybrid", top: int = 20) -> pd.DataFrame:
    t = tag_conditions(bt)
    f = t[(t["model"] == model) & t["failure"]].copy()
    if f.empty:
        return f.assign(failure_type=[], likely_cause=[])
    f["failure_type"] = np.where(f["wrong_direction"], "wrong_direction", "big_miss")
    f["likely_cause"] = f.apply(_cause, axis=1)
    f = f.sort_values(["wrong_direction", "abs_error"], ascending=False).head(top)
    cols = ["effective_date", "model", "failure_type", "actual", "pred", "low", "high", "confidence", "abs_error", "implied_partial", "lag1", "brent_trend5_pct", "likely_cause"]
    return f[cols].reset_index(drop=True)


CONDITIONS = ("shock", "turning_point", "near_flat", "large_move", "high_confidence", "late_reversal")


def failure_breakdown(bt: pd.DataFrame, models=None) -> pd.DataFrame:
    t = tag_conditions(bt)
    rows = []
    for model, g in t.groupby("model", sort=False):
        if models and model not in models:
            continue
        rows.append(_bucket(model, "all weeks", g))
        for cond in CONDITIONS:
            for flag in (True, False):
                s = g[g[cond] == flag]
                if len(s):
                    rows.append(_bucket(model, f"{cond}={'yes' if flag else 'no'}", s))
    return pd.DataFrame(rows)


def _bucket(model: str, label: str, g: pd.DataFrame) -> dict:
    return {
        "model": model,
        "condition": label,
        "n": len(g),
        "directional_accuracy": float((~g["wrong_direction"]).mean()),
        "mae": float(g["abs_error"].mean()),
        "failure_rate": float(g["failure"].mean()),
        "interval_miss_rate": float(g["outside_interval"].mean()),
    }
