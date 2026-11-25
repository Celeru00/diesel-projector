import pickle

import pandas as pd

from fuelcast.config import DATA_DIR, REPORT_DIR


def model_path(fuel: str):
    return DATA_DIR / f"model_{fuel}.pkl"


def save_model(model, fuel: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(model_path(fuel), "wb") as fh:
        pickle.dump(model, fh)


def load_model(fuel: str):
    with open(model_path(fuel), "rb") as fh:
        return pickle.load(fh)


def write_csv(df: pd.DataFrame, name: str) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(REPORT_DIR / f"{name}.csv", index=False)
