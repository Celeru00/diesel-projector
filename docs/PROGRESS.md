# Progress Update — as of November 25, 2026

**Project:** Weekly Fuel (Diesel) Price Adjustment Predictor and Advisor
**Proponents:** Arranguez, Francis Reid N. & Guillermo, Roslyn Faith U.
**Current phase:** End of Week 5 (Evaluate). Next: Week 6 (report, README, demo, log)

## Summary

The system runs end to end with one command:

1. It downloads daily market data (Brent crude, diesel futures, USD/PHP).
2. It aligns the data to each Tuesday price adjustment and builds features.
3. It trains two techniques: k-Nearest Neighbors and linear regression.
4. **Every Tuesday**, when DOE's new prices take effect, it forecasts the **following Tuesday's diesel** price adjustment (₱/L), one week ahead.
5. A rule-based expert system turns the forecast into advice for motorists, tricycle operators, and fleets.

Evaluation is complete. It covers 352 weeks of walk-forward testing, two baselines with significance tests, a failure analysis, and 76 automated tests, all passing.

**Main open issue:** the model is trained and scored on _estimated_ adjustments, not official DOE figures. Collecting the DOE history is the top task for the final week (see Risks).

## Status by week

| Week         | Planned focus                                             | Status                   | What was delivered                                                                                                 |
| ------------ | --------------------------------------------------------- | ------------------------ | ------------------------------------------------------------------------------------------------------------------ |
| Oct 22–28    | Form pair, choose problem and techniques, write proposal  | ✅ Done                  | Proposal submitted. Techniques: k-NN + linear regression (prediction) and a production-rule expert system (advice) |
| Oct 29–Nov 4 | Gather or build the data; set up repository and baseline  | ✅ Done, with deviations | See the list below                                                                                                 |
| Nov 5–11     | Implement the core technique                              | ✅ Done                  | See the list below                                                                                                 |
| Nov 12–18    | Add the second technique; get one path working end to end | ✅ Done                  | See the list below                                                                                                 |
| Nov 19–25    | Evaluate: test cases, baseline comparison, failure cases  | ✅ Done                  | See the list below                                                                                                 |
| Nov 26–Dec 2 | Report, README, demo rehearsal, log                       | 🔄 In progress           | See the list below                                                                                                 |

**Oct 29–Nov 4 (data, repository, baselines):**

- Data ingestion from Yahoo Finance: 8 years of daily data, 2018 to present.
- Cleaning: weekend rows dropped, gaps forward-filled, isolated spikes removed using a median-absolute-deviation check, all prices converted to ₱/L.
- SQLite database (`data/fuelcast.db`).
- Two baselines: persistence (repeat last week's adjustment) and majority class (always predict the most common direction).
- Deviations from the proposal are covered under "Deviations from the proposal".

**Nov 5–11 (core technique):** k-NN regressor.

- Uses standardized features, k = 7, and distance weighting.
- Inputs are 10 features: the price change implied so far in the pricing week, 5-day trends in Brent, the diesel benchmark price, and USD/PHP, Brent's slope and volatility, and the last 3 weeks' adjustments.
- Outputs the direction, the size in ₱/L, a confidence score, and an 80% prediction interval.

**Nov 12–18 (second technique, end to end):**

- **Linear regression**, plus a **hybrid** that blends it with k-NN. The blend weight is learned from each model's error over the last 26 weeks of training data.
- **Expert system:**
  - A forward-chaining rule engine with salience (priority) ordering and an explanation trace.
  - Persona rules for motorists, tricycle operators, and fleets.
  - A shock-week override, triggered by a Brent move of 8% or more in 5 days, a volatility z-score of 2.5 or more, or a manual flag.
- The whole pipeline runs with one command (`make` / `fuelcast run`).

**Nov 19–25 (evaluation):**

- Walk-forward backtest over 352 weeks.
- Comparison against both baselines, with Diebold–Mariano and McNemar significance tests.
- Failure analysis by condition, plus a list of the 20 worst weeks with likely causes.
- Four synthetic shock stress tests.
- 76 automated tests.

**Nov 26–Dec 2 (in progress):**

- Done so far: README, formatted terminal output (tables and panels), auto-generated result reports (`reports/`), and a demo script (`docs/DEMO.md`).
- Remaining: final written report, demo rehearsal, filling in the log.

## Results so far (walk-forward, 352 weeks)

| Model                | Directional accuracy | Macro precision | Macro recall | MAE (₱/L) | RMSE (₱/L) |
| -------------------- | -------------------- | --------------- | ------------ | --------- | ---------- |
| Hybrid               | 80.1%                | 0.63            | 0.63         | 0.81      | 1.29       |
| Linear regression    | 80.4%                | 0.63            | 0.63         | 0.81      | 1.32       |
| k-NN                 | 73.0%                | 0.56            | 0.56         | 1.12      | 1.76       |
| Persistence baseline | 52.8%                | 0.39            | 0.39         | 2.26      | 3.53       |
| Majority baseline    | 51.1%                | 0.32            | 0.34         | 1.89      | 2.77       |

**Against the baselines:**

- The hybrid model cuts average error by 57–64% compared with the two baselines.
- It has the smaller error in 77–80% of weeks.
- Both significance tests give p < 0.001.

**Failure analysis (hybrid model):**

| Condition                                       | Directional accuracy                                   |
| ----------------------------------------------- | ------------------------------------------------------ |
| All weeks                                       | 80.1%                                                  |
| Near-flat weeks (actual move within ±₱0.25)     | 44.4%                                                  |
| Late reversals (prices turned after Tuesday)    | 8.6% (58 weeks)                                        |
| Direction changed from last week                | 69.3%                                                  |
| High-confidence predictions (≥ 0.75)            | 93.6%                                                  |
| Lower-confidence predictions                    | 53.8%                                                  |
| Shock weeks                                     | 94.0% (but the failure rate rises from 27.2% to 36.0%) |

- The biggest failure mode is a reversal later in the pricing week. The forecast sees only Monday and Tuesday, so a turnaround from Wednesday to Friday is invisible to it.
- Near-flat weeks are the next weakest, because up versus down is close to noise.
- The confidence score is well calibrated (93.6% vs 53.8%), so the advisor can use it to tell users when not to act.
- The 80% interval contained the actual value 74% of the time, slightly below target. The ranges are a little too narrow for a full week ahead.

**Effect of forecasting on Tuesday:** forecasting one week ahead costs accuracy compared with a Thursday cutoff, which sees 4 of the 5 pricing days:

| Forecast made on | Pricing days known | Directional accuracy | MAE (₱/L) |
| ---------------- | ------------------ | -------------------- | --------- |
| Tuesday (chosen) | 2 of 5             | 80.1%                | 0.81      |
| Thursday         | 4 of 5             | 93.8%                | 0.21      |

Tuesday was chosen because DOE adjustments take effect every Tuesday. Forecasting on that same day gives users a full week of lead time.

**Finding about the two techniques:** linear regression is still more accurate than k-NN, and the learned blend gives k-NN a **26%** weight (up from 3% with a Thursday cutoff). With only two days of the pricing week known, the most similar past weeks carry more useful information. k-NN also contributes:

- A disagreement check: when the two models disagree on direction, the advisor lowers its confidence.
- An explanation: it shows the most similar past weeks (`fuelcast explain`).

## Deviations from the proposal

0. **Scope:** narrowed to **diesel only**, matching the proposal's title. Gasoline and kerosene were removed from the pipeline.

1. **DOE adjustment history:** DOE does not publish a downloadable dataset, so the training target is estimated from market data. The estimate is the change in the weekly average benchmark price, converted to ₱/L, with 12% VAT. The pipeline already accepts the official figures (`data/doe_adjustments.csv`) and uses them in place of the estimates wherever they are available.
2. **MOPS quotes:** Platts MOPS Gasoil is paywalled, so NYMEX ULSD diesel futures (`HO=F`) are used as a substitute.
3. **Automated weekly run:** the pipeline runs with one command but is not yet scheduled to run automatically each week.
4. **Geopolitical shock detection:** shocks are detected from market moves, or flagged manually with `--shock "reason"`. There is no news feed.

## Risks and next steps (Nov 26–Dec 2)

| Priority     | Task                                                                                    | Why it matters                                                                                                                                                                      |
| ------------ | --------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1            | Collect official DOE weekly adjustments (at least 1–2 years) and re-run `make evaluate` | Current accuracy is measured against estimates built from the same market data as the features, so it is optimistic. The proposal promises evaluation against official DOE updates. |
| 2            | Write the final report                                                                  | Required deliverable                                                                                                                                                                |
| 3            | Rehearse the demo (`docs/DEMO.md`)                                                      | Required deliverable                                                                                                                                                                |
| 4            | Fill in the project log                                                                 | Required deliverable                                                                                                                                                                |
| 5 (optional) | Schedule the weekly run (cron)                                                          | Completes the "automated weekly pipeline" in the proposal                                                                                                                           |
