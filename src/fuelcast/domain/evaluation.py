import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_fscore_support

from fuelcast.config import SETTINGS
from fuelcast.domain.features import direction, feature_list
from fuelcast.domain.models import MODEL_FACTORIES

LABELS = ["down", "flat", "up"]
BACKTEST_COLUMNS = ["effective_date", "model", "actual", "pred", "pred_direction", "confidence", "low", "high", "brent_trend5_pct", "brent_vol_z", "implied_partial", "lag1"]


def trainable(frame: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    return frame.dropna(subset=[*features, "target"])


def walk_forward(
    frame: pd.DataFrame,
    models: list[str] = tuple(MODEL_FACTORIES),
    min_train: int = SETTINGS.min_train_weeks,
    refit_every: int = 1,
) -> pd.DataFrame:
    feats = feature_list()
    data = trainable(frame, feats)
    rows = []
    fitted = {}
    for i in range(min_train, len(data)):
        train, test = data.iloc[:i], data.iloc[[i]]
        if (i - min_train) % refit_every == 0:
            fitted = {m: MODEL_FACTORIES[m]().fit(train[feats], train["target"]) for m in models}
        for m, model in fitted.items():
            p = model.predict(test[feats]).iloc[0]
            rows.append(
                {
                    "effective_date": test.index[0],
                    "model": m,
                    "actual": test["target"].iloc[0],
                    "pred": p["pred"],
                    "pred_direction": p["direction"],
                    "confidence": p["confidence"],
                    "low": p["low"],
                    "high": p["high"],
                    "brent_trend5_pct": test["brent_trend5_pct"].iloc[0],
                    "brent_vol_z": test["brent_vol_z"].iloc[0] if "brent_vol_z" in test else np.nan,
                    "implied_partial": test["implied_partial"].iloc[0],
                    "lag1": test["lag1"].iloc[0],
                }
            )
    out = pd.DataFrame(rows, columns=BACKTEST_COLUMNS)
    out["actual_direction"] = direction(out["actual"])
    return out


def metrics(bt: pd.DataFrame) -> dict:
    y, yhat = bt["actual_direction"], bt["pred_direction"]
    p, r, f, _ = precision_recall_fscore_support(y, yhat, labels=LABELS, zero_division=0)
    err = bt["pred"] - bt["actual"]
    out = {
        "n": len(bt),
        "directional_accuracy": float((y == yhat).mean()),
        "macro_precision": float(p.mean()),
        "macro_recall": float(r.mean()),
        "macro_f1": float(f.mean()),
        "mae": float(err.abs().mean()),
        "rmse": float(np.sqrt((err**2).mean())),
        "interval_coverage": float(((bt["actual"] >= bt["low"]) & (bt["actual"] <= bt["high"])).mean()),
    }
    for lab, pi, ri in zip(LABELS, p, r, strict=True):
        out[f"precision_{lab}"] = float(pi)
        out[f"recall_{lab}"] = float(ri)
    return out


def summarize(bt: pd.DataFrame, shock_mask: pd.Series | None = None) -> pd.DataFrame:
    rows = []
    for m, g in bt.groupby("model", sort=False):
        rows.append({"model": m, "subset": "all", **metrics(g)})
        if shock_mask is not None:
            s = g[shock_mask.loc[g.index]]
            if len(s):
                rows.append({"model": m, "subset": "shock", **metrics(s)})
    return pd.DataFrame(rows)
