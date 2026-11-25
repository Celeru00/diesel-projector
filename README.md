# fuelcast — Weekly Fuel Price Adjustment Predictor and Advisor

CMSC 170 project — Arranguez, Francis Reid N. & Guillermo, Roslyn Faith U.

A hybrid decision-support system that forecasts the Philippines' Tuesday **diesel** price adjustment (₱/L). It then turns each forecast into advice for motorists, tricycle operators, and fleets.

## Quick start

```bash
uv sync
uv run fuelcast run              # fetch data, run the full pipeline, write reports/report.md
uv run fuelcast run --offline    # re-run on cached market data
uv run fuelcast run --shock "Strait of Hormuz closure"   # force the geopolitical override
uv run fuelcast evaluate --offline   # metrics, baseline comparison, failure analysis → reports/evaluation.md
uv run fuelcast explain   # similar past weeks + regression weights behind the forecast
uv run fuelcast advise --persona fleet --pred 1.8 --confidence 0.85
uv run pytest
```

Or use the Makefile: `make`, `make offline`, `make evaluate`, `make explain`, `make test`, `make check`.

## Pipeline

| Stage | Module | Output (SQLite `data/fuelcast.db`) |
|---|---|---|
| Ingestion | `ingest.py` | `market_raw`, `doe_adjustments` |
| Cleaning and normalization | `clean.py` | `market_daily` |
| Cycle alignment and features | `features.py` | `cycles`, `features_<fuel>` |
| Walk-forward evaluation | `evaluate.py` | `backtest_<fuel>`, `metrics`, `reports/metrics.csv` |
| Training and forecast | `models.py` | `forecasts`, `data/model_<fuel>.pkl` |
| Baseline comparison and failure analysis | `analysis.py` | `baseline_comparison`, `failure_breakdown`, `failure_cases` (+ CSVs in `reports/`) |
| Expert system | `advisor.py` | `advice` |
| Shock stress tests | `pipeline.py` | `stress_tests`, `reports/stress_tests.csv` |

### Data sources

| Proposal input | Source used |
|---|---|
| Brent crude futures | Yahoo Finance `BZ=F` |
| MOPS Gasoil (diesel) | NYMEX ULSD `HO=F` (proxy) |
| USD/PHP | Yahoo Finance `PHP=X` |
| Past DOE adjustments | `data/doe_adjustments.csv` (you supply this) |

MOPS (Platts Singapore) quotes are paywalled, so the closest free NYMEX diesel futures stand in for them.

### Training targets

A Tuesday adjustment reflects the change in average MOPS between the two previous Monday–Friday windows, converted to ₱/L and with 12% VAT added.

- **With DOE data:** if `data/doe_adjustments.csv` exists (columns: `effective_date,diesel`, Tuesdays only; see the `.template.csv`), its official figures are used as targets.
- **Without DOE data:** targets are proxy adjustments computed from the formula above and rounded to ₱0.05.
- **Mixed:** weeks missing from the DOE file fall back to the proxy. The `target_source` column records which was used.

### Features (computed every Tuesday, one week before the adjustment)

DOE adjustments take effect every Tuesday. On that day the system forecasts the following Tuesday's adjustment, using the first two days (Monday and Tuesday) of that adjustment's Monday–Friday pricing week. The cutoff day is configurable with `asof_weekday` in `config.py`.

- `implied_partial`: average benchmark price so far this window minus last window's average, in ₱/L with VAT.
- 5-day % trends for Brent, the fuel's benchmark, and USD/PHP.
- 5-day Brent slope.
- 20-day annualized Brent volatility.
- Benchmark price versus its 20-day moving average.
- The last 3 weekly adjustments (lags).

### Models

- k-NN regressor (k=7, distance-weighted, standardized features).
- Linear regression.
- **Hybrid:** a blend of the two. The weight comes from each model's error on the last 26 training weeks, using inverse squared MAE.
- Baselines: persistence (repeats last week's adjustment) and majority class.

Each prediction includes a direction (up, down, or flat; flat means within ±₱0.05), a confidence score, and an 80% interval.

### Expert system

A forward-chaining production-rule engine. Rules hold a salience and condition → action pairs, and each fired rule is recorded in a trace that explains the advice. Rule layers, from highest priority to lowest:

1. Classify confidence and move size.
2. Downgrade confidence when k-NN and linear regression disagree.
3. **Shock override**: triggered when Brent moves ≥ 8% in 5 days, the volatility z-score is ≥ 2.5, or `--shock` is passed. It widens the forecast range and swaps normal timing advice for partial top-up / buy-as-needed advice.
4. Weekly cost impact from each persona's volume (motorist 40 L, tricycle 25 L, fleet 5,000 L).
5. Timing decision: buy before Tuesday, wait for the rollback, or buy as normal.
6. Persona-specific actions and the headline.

## Evaluation

Expanding-window walk-forward, starting with 104 weeks of training and predicting each later week out of sample. Metrics:

- Directional accuracy
- Macro and per-class precision/recall
- MAE and RMSE
- Interval coverage

Each is reported for all weeks and for shock weeks only. See `reports/report.md`.

### Baseline comparison

Each learned model is paired week-by-week with each baseline and compared on:

- Skill scores: 1 − model MAE (or RMSE) ÷ baseline MAE (or RMSE).
- Gain in directional accuracy.
- Win rate: share of weeks the model's error is smaller.
- Diebold–Mariano test on squared errors.
- Exact McNemar test on directional hits.

### Failure analysis

A failure is a week where the model got the direction wrong, or got it right but missed by more than max(2×MAE, ₱0.50). The analysis:

- Tags every week with conditions: shock week, turning point (direction changed from last week), near-flat move (≤ ₱0.25), large move (≥ ₱1.50), high confidence (≥ 0.75), and late reversal (prices turned after the Tuesday cutoff).
- Reports the failure rate under each condition.
- Lists the worst failures, each with a likely cause.

## Tests

`tests/` contains 76 tests:

| File | Covers |
|---|---|
| `test_pipeline.py` | The core pipeline: cleaning, unit conversion, features, models, and the rule engine |
| `test_baselines.py` | Baseline behaviour, metric correctness, significance tests, models vs baselines, no lookahead |
| `test_failure_cases.py` | Failure diagnosis, bad or missing inputs, and robustness (tiny or constant data, holidays, network errors, persona and shock combinations) |
