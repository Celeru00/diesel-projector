import json

import numpy as np
import pandas as pd
import pytest
import requests
from conftest import make_bt, make_raw

from fuelcast import ingest
from fuelcast.advisor import advise
from fuelcast.analysis import failure_breakdown, failure_cases, tag_conditions
from fuelcast.clean import clean_market, normalize_units
from fuelcast.evaluate import walk_forward
from fuelcast.features import build_cycles, cycle_features, feature_list, fuel_frame
from fuelcast.ingest import load_doe
from fuelcast.models import MODEL_FACTORIES, HybridModel, KNNModel, LinearModel

PRED = {"pred": 1.0, "low": 0.5, "high": 1.5, "direction": "up", "confidence": 0.9}


def test_wrong_direction_is_flagged_and_explained():
    bt = make_bt([1.0, -1.0, 0.5], {"hybrid": [1.0, 1.0, 0.5]}, implied_partial=np.array([1.0, 0.8, 0.5]))
    f = failure_cases(bt)
    assert len(f) == 1
    row = f.iloc[0]
    assert row["failure_type"] == "wrong_direction"
    assert "reversed after" in row["likely_cause"].lower()
    assert "overconfident" in row["likely_cause"].lower()


def test_big_magnitude_miss_with_right_direction():
    actual = [0.5] * 9 + [6.0]
    pred = [0.5] * 9 + [1.0]
    f = failure_cases(make_bt(actual, {"hybrid": pred}))
    assert list(f["failure_type"]) == ["big_miss"]
    assert "under-predicted" in f.iloc[0]["likely_cause"].lower()


def test_near_flat_miss_is_attributed_to_noise():
    f = failure_cases(make_bt([0.1, 1.0], {"hybrid": [-0.1, 1.0]}))
    assert "within ±₱0.25" in f.iloc[0]["likely_cause"].lower()


def test_shock_week_cause():
    bt = make_bt([2.0, -1.0], {"hybrid": [2.0, 1.0]}, brent_trend5_pct=np.array([0.0, -12.0]))
    f = failure_cases(bt)
    assert "shock week" in f.iloc[0]["likely_cause"].lower()


def test_no_failures_returns_empty():
    f = failure_cases(make_bt([1.0, -1.0], {"hybrid": [1.0, -1.0]}))
    assert f.empty


def test_failure_cases_sorted_worst_first_and_capped():
    actual = np.tile([1.0, -1.0], 20)
    pred = -actual * np.linspace(0.2, 3, 40)
    f = failure_cases(make_bt(actual, {"hybrid": pred}), top=5)
    assert len(f) == 5
    assert f["abs_error"].is_monotonic_decreasing


def test_breakdown_partitions_every_condition():
    rng = np.random.default_rng(3)
    actual = rng.normal(0, 1, 80).round(2)
    bt = make_bt(actual, {"hybrid": actual + rng.normal(0, 0.4, 80)})
    fb = failure_breakdown(bt).set_index("condition")
    assert fb.loc["all weeks", "n"] == 80
    for cond in ("near_flat", "turning_point", "high_confidence"):
        yes = fb.loc[f"{cond}=yes", "n"] if f"{cond}=yes" in fb.index else 0
        no = fb.loc[f"{cond}=no", "n"] if f"{cond}=no" in fb.index else 0
        assert yes + no == 80


def test_tag_conditions_turning_point():
    t = tag_conditions(make_bt([1.0, -1.0, -1.0], {"m": [1.0, -1.0, -1.0]}))
    assert list(t["turning_point"]) == [True, True, False]


def test_walk_forward_too_little_history_returns_empty(frames):
    bt = walk_forward(frames["diesel"].iloc[:30], models=["linreg"], min_train=104)
    assert bt.empty
    assert {"actual", "pred", "actual_direction"} <= set(bt.columns)


@pytest.mark.parametrize("cls", [KNNModel, LinearModel, HybridModel])
def test_models_survive_tiny_training_set(frames, cls):
    data = frames["diesel"].dropna(subset=[*feature_list(), "target"])
    X, y = data[feature_list()], data["target"]
    out = cls().fit(X.iloc[:4], y.iloc[:4]).predict(X.iloc[4:6])
    assert out["pred"].notna().all()


@pytest.mark.parametrize("name", [m for m in MODEL_FACTORIES if m != "persistence"])
def test_models_handle_constant_target(frames, name):
    data = frames["diesel"].dropna(subset=feature_list()).iloc[:40]
    X, y = data[feature_list()], pd.Series(0.5, index=data.index)
    out = MODEL_FACTORIES[name]().fit(X, y).predict(X.iloc[:3])
    assert np.allclose(out["pred"], 0.5)
    assert out["confidence"].between(0, 1).all()


def test_persistence_ignores_training_target(frames):
    data = frames["diesel"].dropna(subset=feature_list()).iloc[:40]
    X = data[feature_list()]
    out = MODEL_FACTORIES["persistence"]().fit(X, pd.Series(0.5, index=X.index)).predict(X.iloc[:3])
    assert np.allclose(out["pred"], X["lag1"].iloc[:3])


def test_knn_extreme_out_of_distribution_input(frames):
    data = frames["diesel"].dropna(subset=[*feature_list(), "target"])
    X, y = data[feature_list()], data["target"]
    model = HybridModel().fit(X, y)
    extreme = X.iloc[[-1]].copy()
    extreme["implied_partial"] = 50.0
    out = model.predict(extreme)
    assert out["pred"].iloc[0] > 0
    assert out["high"].iloc[0] >= out["pred"].iloc[0] >= out["low"].iloc[0]


def test_clean_rejects_all_missing_series():
    raw = make_raw(200)
    raw["usdphp"] = np.nan
    with pytest.raises(ValueError, match="No usable market rows"):
        clean_market(raw)


def test_clean_drops_nonpositive_prices():
    raw = make_raw(200)
    raw.iloc[100, 0] = -37.63
    raw.iloc[101, 0] = 0.0
    cleaned, report = clean_market(raw)
    assert (cleaned["brent"] > 0).all()
    assert report["missing_before_ffill"]["brent"] >= 2


def test_clean_drops_weekend_rows():
    raw = make_raw(50)
    weekend = pd.DataFrame(raw.iloc[[0]].to_numpy(), index=[pd.Timestamp("2019-01-05")], columns=raw.columns)
    cleaned, _ = clean_market(pd.concat([raw, weekend]))
    assert (cleaned.index.day_of_week < 5).all()


def test_clean_keeps_real_sustained_jump():
    raw = make_raw(300)
    raw.iloc[200:, 0] *= 1.4
    cleaned, report = clean_market(raw)
    assert report["spikes_removed"]["brent"] == 0
    assert cleaned["brent"].iloc[250] == pytest.approx(raw["brent"].iloc[250])


def test_cycle_features_none_without_history():
    daily = normalize_units(make_raw(10))
    assert cycle_features(daily, pd.Timestamp("2019-01-15")) is None


def test_holiday_in_pricing_window():
    raw = make_raw(400)
    holiday = pd.Timestamp("2019-12-25")
    daily = normalize_units(clean_market(raw.drop(index=holiday, errors="ignore"))[0])
    cycles = build_cycles(daily)
    assert pd.Timestamp("2019-12-31") in cycles.index
    assert cycles.loc["2019-12-31", "window_complete"]


def test_latest_cycle_with_incomplete_window_has_no_target():
    raw = make_raw(400)
    last = raw.index[-1]
    raw = raw[raw.index <= last - pd.Timedelta(days=(last.day_of_week - 2) % 7)]
    cycles = build_cycles(normalize_units(clean_market(raw)[0]))
    f = fuel_frame(cycles, "diesel")
    assert np.isnan(f["target"].iloc[-1])
    assert f["target_source"].iloc[-1] == "none"


def test_load_doe_missing_file_returns_none(tmp_path):
    assert load_doe(tmp_path / "nope.csv") is None


def test_load_doe_missing_column(tmp_path):
    p = tmp_path / "doe.csv"
    p.write_text("effective_date,gasoline\n2026-11-24,1\n")
    with pytest.raises(ValueError, match="missing columns"):
        load_doe(p)


def test_load_doe_bad_date(tmp_path):
    p = tmp_path / "doe.csv"
    p.write_text("effective_date,gasoline,diesel,kerosene\nnext tuesday,1,1,1\n")
    with pytest.raises(ValueError, match="unparseable"):
        load_doe(p)


def test_load_doe_non_numeric_value(tmp_path):
    p = tmp_path / "doe.csv"
    p.write_text("effective_date,diesel\n2026-11-24,rollback\n")
    with pytest.raises(ValueError):
        load_doe(p)


def test_load_doe_header_only(tmp_path):
    p = tmp_path / "doe.csv"
    p.write_text("effective_date,gasoline,diesel,kerosene\n")
    assert load_doe(p).empty


def test_load_doe_duplicate_dates_keep_last(tmp_path):
    p = tmp_path / "doe.csv"
    p.write_text("effective_date,gasoline,diesel,kerosene\n2026-11-24,1,1,1\n2026-11-24,2,2,2\n")
    df = load_doe(p)
    assert len(df) == 1 and df["diesel"].iloc[0] == 2


class _Resp:
    def __init__(self, payload, status=200):
        self.payload, self.status = payload, status

    def raise_for_status(self):
        if self.status >= 400:
            raise requests.HTTPError(f"{self.status}")

    def json(self):
        return self.payload


def test_fetch_yahoo_http_error(monkeypatch):
    monkeypatch.setattr(ingest.requests, "get", lambda *a, **k: _Resp({}, 429))
    with pytest.raises(requests.HTTPError):
        ingest.fetch_yahoo("BZ=F", "2024-01-01", "2024-02-01")


def test_fetch_yahoo_unknown_symbol(monkeypatch):
    payload = {"chart": {"result": None, "error": {"code": "Not Found", "description": "No data found"}}}
    monkeypatch.setattr(ingest.requests, "get", lambda *a, **k: _Resp(payload))
    with pytest.raises(ValueError, match="No data returned"):
        ingest.fetch_yahoo("NOPE", "2024-01-01", "2024-02-01")


def test_fetch_yahoo_network_down(monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(ingest.requests, "get", boom)
    with pytest.raises(requests.ConnectionError):
        ingest.fetch_yahoo("BZ=F", "2024-01-01")


def test_fetch_yahoo_dedupes_and_sorts(monkeypatch):
    ts = [1704412800, 1704326400, 1704412800]
    payload = {"chart": {"result": [{"timestamp": ts, "indicators": {"quote": [{"close": [2.0, 1.0, 3.0]}]}}], "error": None}}
    monkeypatch.setattr(ingest.requests, "get", lambda *a, **k: _Resp(json.loads(json.dumps(payload))))
    s = ingest.fetch_yahoo("BZ=F", "2024-01-01", "2024-02-01")
    assert s.index.is_monotonic_increasing
    assert list(s) == [1.0, 3.0]


def test_advise_unknown_persona():
    with pytest.raises(ValueError, match="Unknown persona"):
        advise(PRED, "jeepney")


def test_advise_flat_prediction():
    a = advise({"pred": 0.0, "low": -0.3, "high": 0.3, "direction": "flat", "confidence": 0.9}, "motorist")
    assert a.facts["timing"] == "normal"
    assert "little to no change" in a.headline


def test_advise_custom_volume_scales_impact():
    small = advise(PRED, "fleet", liters_per_week=100)
    big = advise(PRED, "fleet", liters_per_week=10000)
    assert big.facts["weekly_impact"] == pytest.approx(100 * small.facts["weekly_impact"])


def test_advise_shock_rollback():
    a = advise({"pred": -3.0, "low": -4.0, "high": -2.0, "direction": "down", "confidence": 0.95}, "motorist", shock_reason="ceasefire")
    assert a.facts["timing"] == "shock_buy_as_needed"


def test_advise_every_persona_always_produces_action():
    for persona in ("motorist", "tricycle", "fleet"):
        for pred, direction in ((2.0, "up"), (-2.0, "down"), (0.0, "flat")):
            for conf in (0.3, 0.6, 0.95):
                for shock in (None, "test"):
                    a = advise({"pred": pred, "low": pred - 1, "high": pred + 1, "direction": direction, "confidence": conf}, persona, shock_reason=shock)
                    assert a.headline, (persona, pred, conf, shock)
                    assert a.actions, (persona, pred, conf, shock)
                    assert a.trace[-1] == "emit-headline"


def test_explain_cli_parses():
    from fuelcast.cli import main

    with pytest.raises(SystemExit):
        main(["explain", "--bogus"])
