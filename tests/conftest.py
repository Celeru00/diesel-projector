import numpy as np
import pandas as pd
import pytest

from fuelcast.clean import clean_market, normalize_units
from fuelcast.features import build_cycles, fuel_frame


def make_raw(periods: int = 900, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2019-01-01", periods=periods)
    shocks = rng.normal(0, 0.015, (len(idx), 3)).cumsum(axis=0)
    brent = 65 * np.exp(shocks[:, 0])
    return pd.DataFrame(
        {
            "brent": brent,
            "mops_gasoline": brent / 42 * 1.15 * np.exp(shocks[:, 1] * 0.3),
            "mops_gasoil": brent / 42 * 1.25 * np.exp(shocks[:, 2] * 0.3),
            "usdphp": 52 * np.exp(rng.normal(0, 0.002, len(idx)).cumsum()),
        },
        index=idx,
    )


def make_bt(actual, preds: dict, conf=0.9, **extra) -> pd.DataFrame:
    from fuelcast.features import direction

    actual = np.asarray(actual, dtype=float)
    dates = pd.date_range("2024-01-02", periods=len(actual), freq="W-TUE")
    rows = []
    for model, pred in preds.items():
        pred = np.asarray(pred, dtype=float)
        rows.append(
            pd.DataFrame(
                {
                    "effective_date": dates,
                    "model": model,
                    "actual": actual,
                    "pred": pred,
                    "pred_direction": direction(pred),
                    "confidence": conf,
                    "low": pred - 0.5,
                    "high": pred + 0.5,
                    "brent_trend5_pct": extra.get("brent_trend5_pct", 0.0),
                    "brent_vol_z": extra.get("brent_vol_z", 0.0),
                    "implied_partial": extra.get("implied_partial", actual),
                    "lag1": extra.get("lag1", np.r_[0.0, actual[:-1]]),
                }
            )
        )
    bt = pd.concat(rows, ignore_index=True)
    bt["actual_direction"] = direction(bt["actual"])
    return bt


@pytest.fixture(scope="session")
def raw():
    return make_raw()


@pytest.fixture(scope="session")
def frames(raw):
    daily = normalize_units(clean_market(raw)[0])
    cycles = build_cycles(daily)
    return {f: fuel_frame(cycles, f) for f in ("diesel",)}
