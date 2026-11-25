import pandas as pd

from fuelcast.config import DOE_CSV, FUELS


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
