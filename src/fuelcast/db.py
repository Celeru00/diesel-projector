import sqlite3
from contextlib import closing

import pandas as pd

from fuelcast.config import DB_PATH


def connect(path=DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(path)


def write_table(df: pd.DataFrame, table: str, path=DB_PATH, index: bool = True) -> None:
    with closing(connect(path)) as conn:
        df.to_sql(table, conn, if_exists="replace", index=index)


def read_table(table: str, path=DB_PATH, parse_dates=None, index_col=None) -> pd.DataFrame:
    with closing(connect(path)) as conn:
        return pd.read_sql(f"SELECT * FROM {table}", conn, parse_dates=parse_dates, index_col=index_col)


def tables(path=DB_PATH) -> list[str]:
    with closing(connect(path)) as conn:
        return [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
