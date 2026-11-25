import numpy as np
import pandas as pd

from fuelcast.config import ADJUSTMENT_TICK, FLAT_BAND, FUEL_BENCHMARK, FUELS, SETTINGS, VAT

FEATURE_COLUMNS = [
    "implied_partial",
    "bench_trend5_pct",
    "brent_trend5_pct",
    "brent_slope5",
    "fx_trend5_pct",
    "brent_vol20",
    "bench_vs_ma20_pct",
]


def round_tick(x, tick: float = ADJUSTMENT_TICK):
    return np.round(np.asarray(x, dtype=float) / tick) * tick + 0.0


def direction(x, band: float = FLAT_BAND) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    return np.where(x > band / 2, "up", np.where(x < -band / 2, "down", "flat"))


def pricing_window(tuesday: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    monday = tuesday - pd.Timedelta(days=8)
    return monday, monday + pd.Timedelta(days=4)


def cycle_tuesdays(daily: pd.DataFrame, include_next: bool = True) -> pd.DatetimeIndex:
    first = daily.index.min() + pd.Timedelta(days=30)
    last = daily.index.max() + pd.Timedelta(days=8 if include_next else 0)
    return pd.date_range(first, last, freq="W-TUE")


def _pct(a: float, b: float) -> float:
    return (a / b - 1.0) * 100.0 if b else np.nan


def cycle_features(daily: pd.DataFrame, tuesday: pd.Timestamp, asof_weekday: int = SETTINGS.asof_weekday) -> dict | None:
    mon, fri = pricing_window(tuesday)
    prev_mon, prev_fri = mon - pd.Timedelta(days=7), fri - pd.Timedelta(days=7)
    asof = mon + pd.Timedelta(days=asof_weekday)
    window = daily.loc[mon:fri]
    prev = daily.loc[prev_mon:prev_fri]
    hist = daily.loc[:asof]
    partial = window.loc[:asof]
    if prev.empty or partial.empty or len(hist) < 25:
        return None
    last5 = hist.iloc[-6:]
    row = {
        "effective_date": tuesday,
        "asof": hist.index[-1],
        "window_complete": bool(daily.index.max() >= fri and len(window) >= 3),
        "brent_trend5_pct": _pct(last5["brent_usd_bbl"].iloc[-1], last5["brent_usd_bbl"].iloc[0]),
        "brent_slope5": float(np.polyfit(np.arange(len(last5)), last5["brent_usd_bbl"].to_numpy(), 1)[0]),
        "fx_trend5_pct": _pct(last5["usdphp"].iloc[-1], last5["usdphp"].iloc[0]),
        "brent_vol20": float(np.log(hist["brent_usd_bbl"]).diff().iloc[-20:].std() * np.sqrt(252) * 100),
        "brent_usd_bbl": float(hist["brent_usd_bbl"].iloc[-1]),
        "usdphp": float(hist["usdphp"].iloc[-1]),
    }
    for fuel in FUELS:
        col = f"{FUEL_BENCHMARK[fuel]}_php_l"
        prev_avg = prev[col].mean()
        row[f"{fuel}__implied_partial"] = (partial[col].mean() - prev_avg) * VAT
        row[f"{fuel}__bench_trend5_pct"] = _pct(last5[col].iloc[-1], last5[col].iloc[0])
        row[f"{fuel}__bench_vs_ma20_pct"] = _pct(hist[col].iloc[-1], hist[col].iloc[-20:].mean())
        row[f"{fuel}__proxy_adjustment"] = (window[col].mean() - prev_avg) * VAT if not window.empty else np.nan
    return row


def build_cycles(daily: pd.DataFrame, asof_weekday: int = SETTINGS.asof_weekday) -> pd.DataFrame:
    rows = [r for t in cycle_tuesdays(daily) if (r := cycle_features(daily, t, asof_weekday))]
    df = pd.DataFrame(rows).set_index("effective_date")
    vol = df["brent_vol20"]
    df["brent_vol_z"] = (vol - vol.rolling(52, min_periods=26).mean()) / vol.rolling(52, min_periods=26).std()
    return df


def fuel_frame(cycles: pd.DataFrame, fuel: str, doe: pd.DataFrame | None = None, lags: int = SETTINGS.lags) -> pd.DataFrame:
    shared = ["brent_trend5_pct", "brent_slope5", "fx_trend5_pct", "brent_vol20", "brent_vol_z", "brent_usd_bbl", "usdphp", "asof", "window_complete"]
    out = cycles[shared].copy()
    for col in ("implied_partial", "bench_trend5_pct", "bench_vs_ma20_pct"):
        out[col] = cycles[f"{fuel}__{col}"]
    proxy = pd.Series(round_tick(cycles[f"{fuel}__proxy_adjustment"]), index=cycles.index)
    proxy[~cycles["window_complete"]] = np.nan
    out["target"] = proxy
    out["target_source"] = np.where(proxy.notna(), "proxy", "none")
    if doe is not None and fuel in doe:
        actual = doe.set_index("effective_date")[fuel].reindex(out.index)
        has = actual.notna()
        out.loc[has, "target"] = actual[has]
        out.loc[has, "target_source"] = "doe"
    for k in range(1, lags + 1):
        out[f"lag{k}"] = out["target"].shift(k)
    return out


def feature_list(lags: int = SETTINGS.lags) -> list[str]:
    return FEATURE_COLUMNS + [f"lag{k}" for k in range(1, lags + 1)]


def latest_row(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.dropna(subset=feature_list()).iloc[[-1]]
