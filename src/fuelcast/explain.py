import pickle

import pandas as pd

from fuelcast import db
from fuelcast.config import DATA_DIR
from fuelcast.features import feature_list
from fuelcast.pipeline import latest_row


def explain(fuel: str) -> dict:
    with open(DATA_DIR / f"model_{fuel}.pkl", "rb") as fh:
        model = pickle.load(fh)
    frame = db.read_table(f"features_{fuel}", index_col="effective_date", parse_dates=["effective_date", "asof"])
    feats = feature_list()
    target = latest_row(frame)
    X = target[feats]
    dist, idx = model.knn_.neighbors(X)
    train = frame.loc[model.knn_.train_index_]
    neigh = train.iloc[idx[0]][["implied_partial", "brent_trend5_pct", "fx_trend5_pct", "lag1", "target"]].copy()
    neigh.insert(0, "week", neigh.index.strftime("%Y-%m-%d"))
    neigh.insert(1, "distance", dist[0])
    p = model.predict(X).iloc[0]
    return {
        "effective_date": target.index[0].date(),
        "asof": pd.Timestamp(target["asof"].iloc[0]).date(),
        "current": target[feats].iloc[0],
        "neighbors": neigh.reset_index(drop=True),
        "coefficients": model.lin_.coefficients(feats),
        "knn_weight": model.w_,
        "knn_pred": p["knn_pred"],
        "linreg_pred": p["linreg_pred"],
        "pred": p["pred"],
    }
