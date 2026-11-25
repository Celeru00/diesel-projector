from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.linear_model import LinearRegression
from sklearn.neighbors import KNeighborsRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from fuelcast.config import FLAT_BAND, SETTINGS
from fuelcast.features import direction, round_tick

INTERVAL_Z = 1.2816


def direction_confidence(pred: np.ndarray, sigma: np.ndarray, band: float = FLAT_BAND) -> tuple[np.ndarray, np.ndarray]:
    sigma = np.maximum(sigma, 1e-6)
    p_up = 1 - norm.cdf(band / 2, pred, sigma)
    p_down = norm.cdf(-band / 2, pred, sigma)
    p_flat = np.clip(1 - p_up - p_down, 0, 1)
    probs = np.vstack([p_down, p_flat, p_up]).T
    labels = np.array(["down", "flat", "up"])
    return labels[probs.argmax(axis=1)], probs.max(axis=1)


def _result(pred: np.ndarray, sigma: np.ndarray, index) -> pd.DataFrame:
    pred = np.asarray(pred, dtype=float)
    sigma = np.broadcast_to(np.asarray(sigma, dtype=float), pred.shape)
    _, conf = direction_confidence(pred, sigma)
    return pd.DataFrame(
        {
            "pred": round_tick(pred),
            "direction": direction(round_tick(pred)),
            "confidence": conf,
            "low": round_tick(pred - INTERVAL_Z * sigma),
            "high": round_tick(pred + INTERVAL_Z * sigma),
            "sigma": sigma,
        },
        index=index,
    )


@dataclass
class KNNModel:
    k: int = SETTINGS.knn_k
    name: str = "knn"

    def fit(self, X: pd.DataFrame, y: pd.Series):
        self.k_ = min(self.k, len(X))
        self.pipe_ = make_pipeline(StandardScaler(), KNeighborsRegressor(n_neighbors=self.k_, weights="distance"))
        self.pipe_.fit(X, y)
        self.y_ = y.to_numpy()
        self.train_index_ = X.index
        return self

    def neighbors(self, X: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        scaled = self.pipe_[:-1].transform(X)
        dist, idx = self.pipe_[-1].kneighbors(scaled)
        return dist, idx

    def predict(self, X: pd.DataFrame) -> pd.DataFrame:
        pred = self.pipe_.predict(X)
        _, idx = self.neighbors(X)
        sigma = np.array([max(self.y_[i].std(ddof=1), 0.05) for i in idx])
        sigma = np.sqrt(sigma**2 + (self.y_[idx].mean(axis=1) - pred) ** 2)
        out = _result(pred, sigma, X.index)
        neigh_dirs = direction(self.y_[idx].ravel()).reshape(idx.shape)
        out["neighbor_agreement"] = (neigh_dirs == out["direction"].to_numpy()[:, None]).mean(axis=1)
        return out


@dataclass
class LinearModel:
    name: str = "linreg"

    def fit(self, X: pd.DataFrame, y: pd.Series):
        self.pipe_ = make_pipeline(StandardScaler(), LinearRegression())
        self.pipe_.fit(X, y)
        resid = y.to_numpy() - self.pipe_.predict(X)
        dof = max(len(y) - X.shape[1] - 1, 1)
        self.sigma_ = float(np.sqrt((resid**2).sum() / dof))
        return self

    def coefficients(self, columns) -> pd.Series:
        return pd.Series(self.pipe_[-1].coef_, index=columns).sort_values(key=np.abs, ascending=False)

    def predict(self, X: pd.DataFrame) -> pd.DataFrame:
        return _result(self.pipe_.predict(X), self.sigma_, X.index)


@dataclass
class HybridModel:
    weight_knn: float | None = None
    k: int = SETTINGS.knn_k
    holdout: int = 26
    name: str = "hybrid"

    def _validation_weight(self, X: pd.DataFrame, y: pd.Series) -> float:
        if len(X) < self.holdout * 3:
            return 0.5
        Xa, ya, Xb, yb = X.iloc[: -self.holdout], y.iloc[: -self.holdout], X.iloc[-self.holdout :], y.iloc[-self.holdout :]
        mae_knn = np.abs(KNNModel(k=self.k).fit(Xa, ya).pipe_.predict(Xb) - yb).mean()
        mae_lin = np.abs(LinearModel().fit(Xa, ya).pipe_.predict(Xb) - yb).mean()
        inv = np.array([1 / max(mae_knn, 1e-6), 1 / max(mae_lin, 1e-6)]) ** 2
        return float(inv[0] / inv.sum())

    def fit(self, X: pd.DataFrame, y: pd.Series):
        self.w_ = self.weight_knn if self.weight_knn is not None else self._validation_weight(X, y)
        self.knn_ = KNNModel(k=self.k).fit(X, y)
        self.lin_ = LinearModel().fit(X, y)
        return self

    def predict(self, X: pd.DataFrame) -> pd.DataFrame:
        a, b = self.knn_.predict(X), self.lin_.predict(X)
        w = self.w_
        pred = w * self.knn_.pipe_.predict(X) + (1 - w) * self.lin_.pipe_.predict(X)
        sigma = np.sqrt(w * a["sigma"] ** 2 + (1 - w) * b["sigma"] ** 2)
        out = _result(pred, sigma.to_numpy(), X.index)
        out["knn_pred"], out["linreg_pred"] = a["pred"], b["pred"]
        out["neighbor_agreement"] = a["neighbor_agreement"]
        out["models_agree"] = a["direction"] == b["direction"]
        out["knn_weight"] = w
        return out


@dataclass
class PersistenceBaseline:
    name: str = "persistence"

    def fit(self, X: pd.DataFrame, y: pd.Series):
        self.sigma_ = float((y - X["lag1"]).std(ddof=1))
        return self

    def predict(self, X: pd.DataFrame) -> pd.DataFrame:
        return _result(X["lag1"].to_numpy(), self.sigma_, X.index)


@dataclass
class MajorityBaseline:
    name: str = "majority"

    def fit(self, X: pd.DataFrame, y: pd.Series):
        dirs = pd.Series(direction(y.to_numpy()))
        self.majority_ = dirs.mode().iloc[0]
        self.value_ = float(y[dirs.to_numpy() == self.majority_].median())
        self.sigma_ = float(y.std(ddof=1))
        return self

    def predict(self, X: pd.DataFrame) -> pd.DataFrame:
        out = _result(np.full(len(X), self.value_), self.sigma_, X.index)
        out["direction"] = self.majority_
        return out


MODEL_FACTORIES = {
    "hybrid": HybridModel,
    "knn": KNNModel,
    "linreg": LinearModel,
    "persistence": PersistenceBaseline,
    "majority": MajorityBaseline,
}
