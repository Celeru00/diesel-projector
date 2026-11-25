# Code Walkthrough — How the Files Connect

A script for walking an adviser through the system **file by file**, following one forecast from raw data to advice. Target length: about 15 minutes. Run everything from the project root.

## Before the meeting

```bash
make run      # fetch fresh data once, rebuild the database and model
make test     # confirm 76 passed
```

Open in your editor, in this order (one tab each): `Makefile`, `src/fuelcast/interface/cli.py`, `src/fuelcast/application/pipeline.py`, then the rest as you reach them. Keep a terminal open beside the editor.

---

## The map (show this first, 1 min)

The code follows **clean architecture**: four layers, grouped by what they do.

```
src/fuelcast/
├── interface/        what the user sees           cli.py, display.py, report.py
├── application/      use cases (the order)        pipeline.py, stress.py, explain.py
├── domain/           the AI, pure logic, no I/O   cleaning, features, models, evaluation, analysis, advisor
├── infrastructure/   the outside world            market_data.py, doe.py, database.py, artifacts.py
└── config.py         settings shared by all
```

```
Makefile ──► interface/cli.py ──► application/pipeline.py
                                        │
         ┌──────────────────────────────┼──────────────────────────────────┐
         ▼                              ▼                                  ▼
 infrastructure/              domain/ (pure functions)               infrastructure/
 market_data.py ──► cleaning.py ──► features.py ──► models.py ──► advisor.py   database.py
 doe.py                                  │              │                       artifacts.py
                                         ▼              ▼                       (saves every step)
                                   evaluation.py ──► analysis.py
```

**Say:**
- "Dependencies only point inward. `domain/` never imports from the other layers, so the AI logic has no network, file, or database code in it. That's why the tests can run it on fake data without internet."
- "`infrastructure/` is the only layer that touches Yahoo, the DOE file, SQLite, or the disk. `application/` decides the order. `interface/` only presents results."
- "Each stage passes a pandas DataFrame to the next and saves its output to SQLite, so you can inspect any step."

---

## Step 0 — Entry point: `Makefile` → `interface/cli.py` (1 min)

**Show [Makefile](../Makefile):**
- `make offline` runs `uv run fuelcast run --offline`.
- `make evaluate`, `make explain`, `make advise`, and `make test` map one-to-one to CLI subcommands or pytest.

**Show [cli.py](../src/fuelcast/interface/cli.py):**
- `main()` (line 57) defines four subcommands: `run`, `evaluate`, `explain`, `advise`.
- `cmd_run()` (line 19) calls `pipeline.run_all(...)`, then hands the results to `display.py` for the terminal and `report.py` for `reports/report.md`.

**Say:** "The interface layer does no AI work. It calls the application layer and prints the results."

---

## Step 0.5 — The conductor: `application/pipeline.py` (1 min)

**Show `run_all()` in [pipeline.py](../src/fuelcast/application/pipeline.py) (line 139).** It's the whole system in 8 lines:

```python
raw, doe   = stage_ingest(offline)        # infrastructure/market_data.py, doe.py
daily, ... = stage_clean(raw)             # domain/cleaning.py
frames     = stage_features(daily, doe)   # domain/features.py
metrics, backtests = stage_evaluate(...)  # domain/evaluation.py
analysis   = stage_analysis(backtests)    # domain/analysis.py
forecasts  = stage_train_predict(frames)  # domain/models.py
advice     = stage_advise(forecasts)      # domain/advisor.py
stress_df  = stage_stress(raw, doe)       # application/stress.py
```

**Say:** "I'll go through these in order. Each `stage_*` function calls one domain module, then saves the result through the infrastructure layer."

| Stage function | Calls | Writes SQLite table | Writes file |
|---|---|---|---|
| `stage_ingest` | `infrastructure/market_data.py`, `doe.py` | `market_raw` | `data/raw/market_daily.csv` (cache) |
| `stage_clean` | `domain/cleaning.py` | `market_daily` | — |
| `stage_features` | `domain/features.py` | `cycles`, `features_diesel` | — |
| `stage_evaluate` | `domain/evaluation.py` + `models.py` | `backtest_diesel`, `metrics` | `reports/metrics.csv` |
| `stage_analysis` | `domain/analysis.py` | `baseline_comparison`, `failure_breakdown`, `failure_cases` | matching `reports/*.csv` |
| `stage_train_predict` | `domain/models.py` | `forecasts` | `data/model_diesel.pkl` |
| `stage_advise` | `domain/advisor.py` | `advice` | — |
| `stage_stress` | `application/stress.py`, re-running the stages above | `stress_tests` | `reports/stress_tests.csv` |

**Show it's real:**

```bash
sqlite3 data/fuelcast.db ".tables"
```

---

## Step 1 — Settings: `config.py` (30 s)

**Show [config.py](../src/fuelcast/config.py):**
- `MARKET_SYMBOLS` (line 14): the three inputs from the proposal. `BZ=F` is Brent, `HO=F` is the diesel benchmark (substitute for MOPS Gasoil), `PHP=X` is USD/PHP.
- `VAT = 1.12`, `ADJUSTMENT_TICK = 0.05` (DOE rounds to 5 centavos).
- `Settings` (line 32): one place for every tunable number. `asof_weekday=1` means forecast on **Tuesday**. `knn_k=7`, `min_train_weeks=104`, and the shock thresholds (8% Brent move, volatility z ≥ 2.5).

**Say:** "Every other file imports from here, so changing the forecast day or k is a one-line change."

---

## Step 2 — Data in: `infrastructure/` (1 min)

**Show [market_data.py](../src/fuelcast/infrastructure/market_data.py):**
- `fetch_yahoo()` (line 12): downloads one daily price series. It fails loudly if Yahoo returns nothing.
- `fetch_market()`: downloads all three and caches them to `data/raw/market_daily.csv`. That cache is what `--offline` reads.

**Show [doe.py](../src/fuelcast/infrastructure/doe.py):**
- `load_doe()` (line 6): reads `data/doe_adjustments.csv` **if it exists**. It checks the columns, that every date is a Tuesday, and that values are numbers.

**Say:** "This is where DOE data plugs in. Right now there's no file, so it returns `None` and the system falls back to estimated adjustments. That's the data note you see in the output."

---

## Step 3 — Cleaning: `domain/cleaning.py` (1 min)

**Show [cleaning.py](../src/fuelcast/domain/cleaning.py):**
- `clean_market()` (line 7):
  1. Drops weekend rows.
  2. Treats zero or negative prices as missing.
  3. Removes one-day spikes that immediately reverse (a median-absolute-deviation check).
  4. Forward-fills holiday gaps.
- `normalize_units()` (line 28): converts everything to **pesos per liter**. Barrels ÷ 159 L, gallons ÷ 3.785 L, then × USD/PHP.

**Say:** "After this file, every number is in ₱/L, the same unit DOE announces."

```bash
sqlite3 -header -column data/fuelcast.db "SELECT substr(Date,1,10) AS day, round(brent_usd_bbl,2) AS brent_usd, round(usdphp,2) AS usdphp, round(mops_gasoil_php_l,2) AS diesel_php_per_l FROM market_daily ORDER BY Date DESC LIMIT 5"
```

---

## Step 4 — Features: `domain/features.py` (2 min, the key idea)

This file turns **daily prices** into **one row per Tuesday adjustment**.

**Show [features.py](../src/fuelcast/domain/features.py):**
- `pricing_window()` (line 26): for an adjustment taking effect Tuesday T, the prices that decide it run from Monday T−8 to Friday T−4.
- `cycle_features()` (line 41): builds one row. The cutoff is `asof = Monday + 1 day` (Tuesday), so it only uses data **up to the forecast day**. It never looks ahead. It computes:
  - `implied_partial`: how far diesel has moved over the Mon–Tue known so far vs last week's average, × VAT.
  - `brent_trend5_pct`, `fx_trend5_pct`, `bench_trend5_pct`: the 5-day trends from the proposal.
  - `brent_slope5`, `brent_vol20`, `bench_vs_ma20_pct`: momentum and volatility.
  - `proxy_adjustment`: the **estimated target**, the full-week average change × VAT.
- `fuel_frame()` (line 81):
  - Sets `target` to the estimate, rounded to ₱0.05.
  - **If DOE data exists, it replaces the estimate** (`target_source = "doe"`).
  - Adds `lag1–lag3`: the last three weeks' adjustments.

**Show the result:**

```bash
sqlite3 -header -column data/fuelcast.db "SELECT substr(effective_date,1,10) AS tuesday, substr(asof,1,10) AS forecast_made, round(implied_partial,2) AS implied_so_far, round(brent_trend5_pct,2) AS brent_5d_pct, round(lag1,2) AS last_week, round(target,2) AS actual, target_source FROM features_diesel ORDER BY effective_date DESC LIMIT 5"
```

**Say:** "Each row is one Tuesday. `forecast_made` is one week earlier. The top row has no `actual` yet; that's the week we're forecasting."

---

## Step 5 — The two techniques: `domain/models.py` (2 min)

**Show [models.py](../src/fuelcast/domain/models.py):**
- `KNNModel` (line 45): standardizes the 10 features, finds the **7 most similar past weeks**, and averages their adjustments, weighted by distance. Its uncertainty is how much those 7 neighbors disagree.
- `LinearModel` (line 74): standardized linear regression. Its uncertainty is the residual standard deviation.
- `HybridModel` (line 93):
  - `_validation_weight()` holds out the last 26 training weeks, scores both models on them, and weights each by 1 ÷ error².
  - Result for the current forecast: **k-NN 26%, linear regression 74%**.
  - `predict()` also reports whether the two models **agree on direction**. The expert system uses that.
- `PersistenceBaseline` (line 128): repeats last week's adjustment.
- `MajorityBaseline` (line 140): always predicts the most common direction.
- All models output the same columns: `pred`, `direction`, `confidence`, `low`, `high` (the 80% range). That's why evaluation and the advisor can treat them interchangeably.

**Show it explained:**

```bash
make explain
```

[explain.py](../src/fuelcast/application/explain.py) loads the saved `data/model_diesel.pkl` through `infrastructure/artifacts.py` and prints the 7 neighbor weeks and the regression weights.

---

## Step 6 — Evaluation: `domain/evaluation.py` → `domain/analysis.py` (2 min)

**Show `walk_forward()` in [evaluation.py](../src/fuelcast/domain/evaluation.py) (line 17):**

```python
for i in range(min_train, len(data)):
    train, test = data.iloc[:i], data.iloc[[i]]
```

**Say:** "For each week from week 104 onward, train only on earlier weeks, then predict that one week. It's exactly how the model would have been used live, so there's no leakage. That gives 352 test weeks for every model, including both baselines."

- `metrics()`: directional accuracy, macro precision/recall/F1, MAE, RMSE, and interval coverage. These are the metrics the proposal names.

**Show [analysis.py](../src/fuelcast/domain/analysis.py):**
- `compare_to_baselines()` (line 37): error reduction, win rate, a **Diebold–Mariano** test on error size, and a **McNemar** test on direction hits.
- `tag_conditions()` (line 75): labels each week: shock, turning point, near-flat, large move, high confidence, or late reversal.
- `failure_cases()` (line 111): the worst weeks, each with an automatic likely cause.

```bash
make evaluate
```

Point at three things in the output: 80.1% vs 51–53%, p < 0.001, and the "prices reversed after Tuesday" row at 8.6%.

---

## Step 7 — The expert system: `domain/advisor.py` (2–3 min)

**Show [advisor.py](../src/fuelcast/domain/advisor.py):**
- `PERSONAS` (line 4): motorist 40 L/week, tricycle 25 L/week, fleet 5,000 L/week.
- `BASE_RULES` (line 70): production rules, each **name, salience, IF, THEN**. Walk the layers by salience:

| Salience | Rules | What they do |
|---|---|---|
| 100 | `classify-confidence-*`, `classify-size-*` | Turn numbers into categories (high/medium/low, small/moderate/large) |
| 95 | `model-disagreement` | k-NN and LinReg disagree on direction → lower confidence |
| 90 | `shock-override` | Shock week → switch to cautious mode and widen the range |
| 80 | `compute-impact` | Forecast × liters per week = pesos |
| 70 | `signal-strong` / `signal-weak` | Is this worth acting on? |
| 60 | `timing-*` | Decide: buy before, wait, normal, or a shock variant |
| 40 | `PERSONA_RULES` (line 117) | Persona-specific wording |
| 10 | `emit-headline` | Write the summary |

- `infer()` (line 157): the **forward-chaining engine** in 12 lines. Each cycle it finds all rules whose IF matches, fires the highest-salience one, records its name in the trace, and repeats until nothing matches.
- `detect_shock()` (line 172): the market-based shock check.

**Show it changing:**

```bash
make advise PERSONA=fleet PRED=-4.95 CONFIDENCE=0.99
uv run fuelcast advise --persona fleet --pred 2.5 --confidence 0.9 --shock "Strait of Hormuz closure"
```

**Say:** "The reasoning line under each panel is `infer()`'s trace, so every recommendation can be traced back to the rules that produced it. In the second run, `shock-override` fires right after classification and changes which timing rule applies."

---

## Step 8 — Output: `interface/display.py`, `interface/report.py`, `infrastructure/` (30 s)

- [display.py](../src/fuelcast/interface/display.py): the colored terminal tables and panels. It formats only; no logic.
- [report.py](../src/fuelcast/interface/report.py): the same results written to `reports/report.md` and `reports/evaluation.md`.
- [database.py](../src/fuelcast/infrastructure/database.py): four small functions wrapping SQLite.
- [artifacts.py](../src/fuelcast/infrastructure/artifacts.py): saves and loads the trained model, and writes the report CSVs.

**Say:** "Presentation is kept separate from the AI code, so the same results feed the terminal, the Markdown reports, and the database."

---

## Step 9 — Tests: `tests/` (1 min)

| File | What it checks | Maps to |
|---|---|---|
| [conftest.py](../tests/conftest.py) | Builds synthetic market data and backtests | Shared fixtures |
| [test_pipeline.py](../tests/test_pipeline.py) | Cleaning, ₱/L conversion, Tuesday windows, no future data, DOE override, Tuesday-forecast timing | `domain/cleaning`, `domain/features`, `infrastructure/doe` |
| [test_baselines.py](../tests/test_baselines.py) | Baseline behavior, metrics math, DM and McNemar tests | `domain/models`, `domain/evaluation`, `domain/analysis` |
| [test_failure_cases.py](../tests/test_failure_cases.py) | Bad DOE files, network failures, holidays, and every persona × direction × confidence × shock combination | `infrastructure/`, `domain/advisor`, `domain/analysis` |

```bash
make test
```

---

## Wrap-up (30 s)

**Say:**
1. "The code is layered: `domain/` holds the AI with no I/O, `infrastructure/` talks to the outside world, `application/` sets the order, and `interface/` presents. Data flows one way: ingest → clean → features → models → evaluation and advice."
2. "DOE data plugs in at one point, `load_doe()`. Once the CSV exists, it becomes both the training target and the evaluation ground truth with no code changes."
3. "The k-NN and linear regression models share one output format, so the evaluation and the expert system work with either, or with the hybrid."

## Likely code questions

| Question | Where to point |
|---|---|
| How do you prevent data leakage? | `cycle_features()` cuts off at `asof`; `walk_forward()` trains on `iloc[:i]` only; there's a test for both |
| Where's the forecast day set? | `Settings.asof_weekday` in `config.py` |
| Why split into layers? | The AI logic in `domain/` can be tested and reused without the network or database, and swapping a data source (say, a real MOPS feed) only touches `infrastructure/` |
| How is confidence computed? | `direction_confidence()` in `domain/models.py`: treats the forecast as a normal distribution and takes the probability of the predicted direction (down, flat within ±₱0.05, or up) |
| Where would a new persona go? | Add it to `PERSONAS` and 5 `_r(...)` lines in `PERSONA_RULES` |
| Where would a news-based shock feed go? | Add a module in `infrastructure/` and pass its reason as `shock_override` to `stage_advise()`. The `--shock` flag already does this |
