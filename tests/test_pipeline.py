import numpy as np
import pandas as pd
import pytest

from fuelcast.domain.advisor import advise, detect_shock, infer
from fuelcast.domain.cleaning import clean_market, normalize_units
from fuelcast.domain.evaluation import metrics, walk_forward
from fuelcast.domain.features import build_cycles, direction, feature_list, fuel_frame, pricing_window, round_tick
from fuelcast.domain.models import MODEL_FACTORIES
from fuelcast.infrastructure.doe import load_doe


def test_pricing_window_is_prior_mon_to_fri():
    mon, fri = pricing_window(pd.Timestamp("2026-12-01"))
    assert (mon.weekday(), fri.weekday()) == (0, 4)
    assert mon == pd.Timestamp("2026-11-23")


def test_clean_removes_isolated_spike_and_fills_gaps(raw):
    dirty = raw.copy()
    dirty.iloc[400, 0] *= 3
    dirty.iloc[401:403, 3] = np.nan
    cleaned, report = clean_market(dirty)
    assert report["spikes_removed"]["brent"] >= 1
    assert cleaned.isna().sum().sum() == 0
    assert cleaned["brent"].iloc[400] < raw["brent"].iloc[400] * 1.5


def test_units_convert_to_php_per_liter(raw):
    n = normalize_units(raw)
    expected = raw["brent"] * raw["usdphp"] / 158.987
    assert np.allclose(n["brent_php_l"], expected)


def test_features_use_only_data_up_to_asof(frames):
    f = frames["diesel"]
    assert (f["asof"] < f.index - pd.Timedelta(days=4)).all()
    assert f["lag1"].iloc[5] == f["target"].iloc[4]


def test_targets_rounded_to_tick(frames):
    t = frames["diesel"]["target"].dropna()
    assert np.allclose(t, round_tick(t))


def test_direction_flat_band():
    assert list(direction([0.3, -0.3, 0.0, 0.04])) == ["up", "down", "flat", "flat"]


@pytest.mark.parametrize("name", list(MODEL_FACTORIES))
def test_models_fit_predict(frames, name):
    data = frames["diesel"].dropna(subset=[*feature_list(), "target"])
    X, y = data[feature_list()], data["target"]
    out = MODEL_FACTORIES[name]().fit(X.iloc[:-5], y.iloc[:-5]).predict(X.iloc[-5:])
    assert {"pred", "direction", "confidence", "low", "high"} <= set(out.columns)
    assert ((out["low"] <= out["pred"]) & (out["pred"] <= out["high"])).all()
    assert out["confidence"].between(0, 1).all()


def test_walk_forward_beats_baselines(frames):
    bt = walk_forward(frames["diesel"], models=["linreg", "persistence", "majority"], min_train=60, refit_every=8)
    m = {k: metrics(g) for k, g in bt.groupby("model")}
    assert m["linreg"]["mae"] < m["persistence"]["mae"]
    assert m["linreg"]["directional_accuracy"] > m["majority"]["directional_accuracy"]


def test_rule_engine_fires_by_salience():
    wm, trace = infer({"persona": "motorist", "fuel": "diesel", "liters_per_week": 40, "pred": 1.0, "low": 0.5, "high": 1.5, "direction": "up", "confidence": 0.9, "shock": False})
    assert trace[0].startswith("classify-")
    assert trace[-1] == "emit-headline"
    assert wm["timing"] == "buy_before"


def test_advice_hike_vs_rollback():
    up = advise({"pred": 1.2, "low": 0.8, "high": 1.6, "direction": "up", "confidence": 0.9}, "fleet")
    down = advise({"pred": -1.2, "low": -1.6, "high": -0.8, "direction": "down", "confidence": 0.9}, "fleet")
    assert up.facts["timing"] == "buy_before" and "before Tuesday" in up.actions[0]
    assert down.facts["timing"] == "wait" and "Defer" in down.actions[0]


def test_low_confidence_gives_normal_timing():
    a = advise({"pred": 0.3, "low": -0.4, "high": 1.0, "direction": "up", "confidence": 0.5}, "tricycle")
    assert a.facts["timing"] == "normal"


def test_model_disagreement_downgrades_confidence():
    a = advise({"pred": 0.8, "low": 0.2, "high": 1.4, "direction": "up", "confidence": 0.8, "models_agree": False}, "motorist")
    assert a.facts["confidence_level"] == "medium"
    assert "model-disagreement" in a.trace


def test_shock_override_widens_range_and_changes_timing():
    a = advise({"pred": 2.0, "low": 1.5, "high": 2.5, "direction": "up", "confidence": 0.95}, "fleet", shock_reason="Strait closure")
    assert a.facts["mode"] == "shock"
    assert a.facts["timing"] == "shock_partial_topup"
    assert a.facts["low"] < 1.5 and a.facts["high"] > 2.5
    assert a.headline.startswith("[SHOCK WEEK]")
    assert any("surcharge" in x for x in a.actions)


def test_detect_shock():
    assert detect_shock(9.0, 0.0, 8.0, 2.5)
    assert detect_shock(1.0, 3.0, 8.0, 2.5)
    assert detect_shock(1.0, float("nan"), 8.0, 2.5) is None


def test_load_doe_validates_tuesdays(tmp_path):
    p = tmp_path / "doe.csv"
    p.write_text("effective_date,gasoline,diesel,kerosene\n2026-11-24,-1.0,-2.0,-2.1\n")
    assert len(load_doe(p)) == 1
    p.write_text("effective_date,gasoline,diesel,kerosene\n2026-11-25,-1.0,-2.0,-2.1\n")
    with pytest.raises(ValueError):
        load_doe(p)


def test_doe_overrides_proxy_target(frames, raw):
    daily = normalize_units(clean_market(raw)[0])
    cycles = build_cycles(daily)
    t = cycles.index[10]
    doe = pd.DataFrame({"effective_date": [t], "diesel": [9.99]})
    f = fuel_frame(cycles, "diesel", doe)
    assert f.loc[t, "target"] == 9.99 and f.loc[t, "target_source"] == "doe"


def test_forecast_made_on_tuesday_one_week_ahead(frames):
    f = frames["diesel"]
    assert (f["asof"] <= f.index - pd.Timedelta(days=7)).all()
    assert (f["asof"].dt.day_of_week == 1).mean() > 0.9
