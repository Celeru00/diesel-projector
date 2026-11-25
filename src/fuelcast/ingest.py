from datetime import UTC, datetime

import pandas as pd
import requests

from fuelcast.config import DOE_CSV, FUELS, MARKET_SYMBOLS, RAW_DIR

YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
HEADERS = {"User-Agent": "Mozilla/5.0 (fuelcast)"}


def fetch_yahoo(symbol: str, start: str, end: str | None = None) -> pd.Series:
    p1 = int(pd.Timestamp(start, tz="UTC").timestamp())
    p2 = int((pd.Timestamp(end, tz="UTC") if end else pd.Timestamp(datetime.now(UTC))).timestamp())
    resp = requests.get(
        YAHOO_URL.format(symbol=symbol),
        params={"period1": p1, "period2": p2, "interval": "1d"},
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json().get("chart", {})
    if payload.get("error") or not payload.get("result"):
        raise ValueError(f"No data returned for {symbol}: {payload.get('error')}")
    result = payload["result"][0]
    idx = pd.to_datetime(result["timestamp"], unit="s", utc=True).tz_convert(None).normalize()
    close = pd.Series(result["indicators"]["quote"][0]["close"], index=idx, dtype="float64")
    return close[~close.index.duplicated(keep="last")].sort_index()


def fetch_market(start: str, end: str | None = None, cache: bool = True) -> pd.DataFrame:
    frames = {name: fetch_yahoo(sym, start, end) for name, sym in MARKET_SYMBOLS.items()}
    df = pd.DataFrame(frames)
    df.index.name = "date"
    if cache:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        df.to_csv(RAW_DIR / "market_daily.csv")
    return df


def load_cached_market() -> pd.DataFrame:
    return pd.read_csv(RAW_DIR / "market_daily.csv", parse_dates=["date"], index_col="date")


def load_doe(path=DOE_CSV) -> pd.DataFrame | None:
    if not path.exists():
        return None
    df = pd.read_csv(path)
    missing = {"effective_date", *FUELS} - set(df.columns)
    if missing:
        raise ValueError(f"DOE file missing columns: {sorted(missing)}")
    df = df[["effective_date", *FUELS]].dropna(subset=list(FUELS), how="all").copy()
    try:
        df["effective_date"] = pd.to_datetime(df["effective_date"], format="ISO8601").dt.normalize()
    except (ValueError, TypeError) as e:
        raise ValueError(f"DOE file has unparseable effective_date values: {e}") from e
    for fuel in FUELS:
        df[fuel] = pd.to_numeric(df[fuel], errors="raise")
    if not (df["effective_date"].dt.day_of_week == 1).all():
        bad = df.loc[df["effective_date"].dt.day_of_week != 1, "effective_date"]
        raise ValueError(f"DOE effective dates must be Tuesdays: {bad.dt.date.tolist()[:5]}")
    return df.drop_duplicates("effective_date", keep="last").sort_values("effective_date")
