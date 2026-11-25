import numpy as np
import pandas as pd
import pytest
from conftest import make_bt

from fuelcast.domain.analysis import compare_to_baselines, diebold_mariano, mcnemar
from fuelcast.domain.evaluation import metrics, summarize, walk_forward
from fuelcast.domain.features import feature_list
from fuelcast.domain.models import MajorityBaseline, PersistenceBaseline


def _xy(lag1, y):
    X = pd.DataFrame({"lag1": lag1})
    return X, pd.Series(y, dtype=float)


def test_persistence_repeats_last_adjustment():
    X, y = _xy([0.5, -1.0, 0.0], [0.4, -0.9, 0.1])
    out = PersistenceBaseline().fit(X, y).predict(X)
    assert list(out["pred"]) == [0.5, -1.0, 0.0]
    assert list(out["direction"]) == ["up", "down", "flat"]


def test_majority_predicts_most_common_direction():
    X, y = _xy([0] * 6, [1.0, 0.8, 1.2, -0.5, 0.9, 0.0])
    out = MajorityBaseline().fit(X, y).predict(X.iloc[:2])
    assert set(out["direction"]) == {"up"}
    assert out["pred"].iloc[0] == pytest.approx(0.95, abs=0.05)


def test_majority_on_all_rollbacks():
    X, y = _xy([0] * 4, [-1.0, -0.5, -2.0, -0.3])
    out = MajorityBaseline().fit(X, y).predict(X)
    assert set(out["direction"]) == {"down"}


def test_perfect_model_metrics():
    bt = make_bt([1.0, -1.0, 0.0, 2.0], {"m": [1.0, -1.0, 0.0, 2.0]})
    m = metrics(bt)
    assert m["directional_accuracy"] == 1.0
    assert m["mae"] == 0.0 and m["rmse"] == 0.0
    assert m["macro_f1"] == 1.0
    assert m["interval_coverage"] == 1.0


def test_always_wrong_direction_metrics():
    bt = make_bt([1.0, -1.0, 1.0, -1.0], {"m": [-1.0, 1.0, -1.0, 1.0]})
    m = metrics(bt)
    assert m["directional_accuracy"] == 0.0
    assert m["mae"] == pytest.approx(2.0)
    assert m["recall_up"] == 0.0 and m["recall_down"] == 0.0


def test_rmse_penalizes_large_errors_more_than_mae():
    bt = make_bt([0.0, 0.0, 0.0, 0.0], {"m": [0.0, 0.0, 0.0, 4.0]})
    m = metrics(bt)
    assert m["mae"] == pytest.approx(1.0)
    assert m["rmse"] == pytest.approx(2.0)


def test_summarize_splits_shock_subset():
    bt = make_bt([1.0, -1.0, 1.0, -1.0], {"m": [1.0, 1.0, 1.0, 1.0]})
    shock = pd.Series([True, True, False, False], index=bt.index)
    s = summarize(bt, shock)
    assert set(s["subset"]) == {"all", "shock"}
    assert s.loc[s.subset == "shock", "n"].iloc[0] == 2


def test_diebold_mariano_detects_better_model():
    rng = np.random.default_rng(1)
    good, bad = rng.normal(0, 0.2, 200), rng.normal(0, 1.5, 200)
    stat, p = diebold_mariano(good, bad)
    assert stat > 0 and p < 0.01
    stat, p = diebold_mariano(bad, good)
    assert stat < 0


def test_diebold_mariano_identical_errors_is_undefined():
    e = np.array([0.1, -0.2, 0.3, 0.0])
    stat, p = diebold_mariano(e, e)
    assert np.isnan(stat) and np.isnan(p)


def test_mcnemar_counts_discordant_pairs():
    a = np.array([True, True, True, True, False, True])
    b = np.array([False, False, False, True, False, True])
    a_only, b_only, p = mcnemar(a, b)
    assert (a_only, b_only) == (3, 0)
    assert 0 < p <= 1
    assert mcnemar(a, a)[2] == 1.0


def test_compare_to_baselines_skill_and_significance():
    rng = np.random.default_rng(2)
    actual = rng.normal(0, 1.5, 150).round(2)
    bt = make_bt(
        actual,
        {
            "hybrid": actual + rng.normal(0, 0.1, 150),
            "persistence": np.r_[0.0, actual[:-1]],
            "majority": np.full(150, 0.5),
        },
    )
    c = compare_to_baselines(bt)
    assert set(c["baseline"]) == {"persistence", "majority"}
    assert (c["model"] == "hybrid").all()
    assert (c["mae_skill"] > 0.8).all()
    assert (c["dir_acc_gain"] > 0.3).all()
    assert c["significant"].all()


def test_compare_flags_model_worse_than_baseline():
    actual = np.tile([1.0, -1.0], 30)
    bt = make_bt(actual, {"bad": -actual, "persistence": actual * 0.5, "majority": np.full(60, 1.0)})
    row = compare_to_baselines(bt).set_index("baseline").loc["persistence"]
    assert row["mae_skill"] < 0
    assert row["win_rate"] == 0.0
    assert not row["significant"]


def test_learned_models_beat_both_baselines_on_synthetic_market(frames):
    fuel = "diesel"
    bt = walk_forward(frames[fuel], models=["hybrid", "linreg", "knn", "persistence", "majority"], min_train=60, refit_every=10)
    c = compare_to_baselines(bt)
    for model in ("hybrid", "linreg"):
        rows = c[c["model"] == model]
        assert (rows["mae_skill"] > 0).all(), rows
        assert (rows["dir_acc_gain"] > 0).all(), rows


def test_walk_forward_has_no_lookahead(frames):
    bt = walk_forward(frames["diesel"], models=["linreg"], min_train=60, refit_every=1000)
    data = frames["diesel"].dropna(subset=[*feature_list(), "target"])
    first_test = bt["effective_date"].min()
    assert first_test == data.index[60]
    assert bt["effective_date"].is_monotonic_increasing
