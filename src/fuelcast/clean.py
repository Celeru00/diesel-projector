import numpy as np
import pandas as pd

from fuelcast.config import LITERS_PER_BARREL, LITERS_PER_GALLON, SETTINGS


def clean_market(df: pd.DataFrame, outlier_z: float = SETTINGS.outlier_z) -> tuple[pd.DataFrame, dict]:
    df = df.sort_index().copy()
    df = df[df.index.day_of_week < 5]
    df = df.where(df > 0)
    log_ret = np.log(df).diff()
    med = log_ret.rolling(60, min_periods=20).median()
    mad = (log_ret - med).abs().rolling(60, min_periods=20).median() * 1.4826
    z = (log_ret - med) / mad.replace(0, np.nan)
    spikes = (z.abs() > outlier_z) & (z.shift(-1).abs() > outlier_z) & (np.sign(z) != np.sign(z.shift(-1)))
    df = df.mask(spikes)
    report = {
        "rows": len(df),
        "missing_before_ffill": df.isna().sum().to_dict(),
        "spikes_removed": spikes.sum().to_dict(),
    }
    df = df.ffill().dropna()
    if df.empty:
        raise ValueError("No usable market rows after cleaning; check that every series has data")
    return df, report


def normalize_units(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    out["usdphp"] = df["usdphp"]
    out["brent_usd_bbl"] = df["brent"]
    out["brent_php_l"] = df["brent"] * df["usdphp"] / LITERS_PER_BARREL
    for col in ("mops_gasoil",):
        out[f"{col}_usd_bbl"] = df[col] * LITERS_PER_BARREL / LITERS_PER_GALLON
        out[f"{col}_php_l"] = df[col] * df["usdphp"] / LITERS_PER_GALLON
    return out
