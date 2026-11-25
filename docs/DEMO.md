# Demo Script — Weekly Diesel Price Adjustment Predictor and Advisor

Target length: about 12 minutes. Every command runs from the project root.

## Before the demo (do this the day before)

```bash
make install     # install dependencies
make run         # fetch fresh market data once and build everything
make test        # confirm all 76 tests pass
```

During the demo, use the **offline** commands. They reuse the market data already downloaded, so the demo doesn't depend on Wi-Fi and the numbers stay the same as in rehearsal.

Open two things in advance:

- A terminal at the project root: maximized, dark theme, large font. The output uses colored tables and panels, so make the window wide enough (at least 120 columns).
- `reports/report.md` in a Markdown preview, as a backup if a command is slow.

---

## Step 1 — The problem (1 min, no commands)

**Say:**

- Every Tuesday, DOE's diesel price adjustment takes effect. Its size is set by the international diesel price (MOPS Gasoil) and the peso–dollar rate over the Monday–Friday pricing week before it.
- Motorists, tricycle drivers, and fleet operators find out only shortly before, so they can't plan their fuel budget.
- Our system runs **every Tuesday**, the same day the new prices take effect. It forecasts **next Tuesday's** diesel adjustment, then tells each type of user what to do about it, giving them a full week to plan.

**Show this diagram (on a slide, or just say it):**

```
Yahoo Finance ──► clean & convert to ₱/L ──► weekly features ──► k-NN + Linear Regression ──► forecast
 (Brent, diesel                             (computed every         (hybrid blend)             (₱/L, direction,
  futures, USD/PHP)                          Tuesday)                                           confidence, range)
                                                                                                      │
                                                                     advice for each persona ◄── expert system
                                                                                                 (production rules)
```

**Timeline to explain (one cycle):**

```
Tue Nov 24        Wed–Fri Nov 25–27             Mon Nov 30            Tue Dec 1
adjustment takes  rest of the pricing week      DOE announcement      new adjustment
effect → OUR      (the model can't see this)                          takes effect →
FORECAST RUNS                                                         next forecast runs
(Mon + Tue prices known)
```

---

## Step 2 — Run the whole system (2 min)

```bash
make offline
```

**While the spinner runs, say:** "One command runs the whole pipeline: ingest, clean, build features, evaluate, train, forecast, advise, and stress test."

The output is split into numbered sections. Walk through the top of it:

1. **The yellow "⚠ Data note" panel.**
   - We don't yet have the official DOE history, so the training targets are estimated using the formula the oil companies use.
   - Be upfront about this; it's the main limitation (Step 10).
2. **Section 1 · Data ingestion and cleaning.**
   - About 2,300 trading days of three series: Brent crude, the diesel benchmark, and USD/PHP.
   - "Gaps forward-filled": USD/PHP has the most because currency markets close on different holidays.
   - "Bad ticks removed": one-day price spikes that immediately reversed.

Then scroll down past sections 2–4 (they come back in Step 8) to **Section 5 · Forecast**:

- **▼ ROLLBACK −₱4.95 per liter** for Tue, Dec 1, 2026, with an 80% range of −₱7.10 to −₱2.85.
- **Forecast made Tue, Nov 24, 2026 (runs every Tuesday, one week ahead).** Point out the lead time.
- **Confidence >99%**: even the worst case in the range is a rollback. k-NN says −₱2.30 and linear regression says −₱5.90; they disagree on the size but agree on the direction.
- **Shock check:** a normal week, with Brent down 1.9% over 5 days.

---

## Step 3 — What the model sees (1 min)

```bash
sqlite3 -header -column data/fuelcast.db "SELECT substr(effective_date,1,10) AS tuesday, substr(asof,1,10) AS forecast_made, round(implied_partial,2) AS implied_so_far, round(brent_trend5_pct,2) AS brent_5d_pct, round(fx_trend5_pct,2) AS fx_5d_pct, round(lag1,2) AS last_week, round(target,2) AS actual FROM features_diesel ORDER BY effective_date DESC LIMIT 5"
```

**Explain:**

- **Each row is one Tuesday price adjustment.** `forecast_made` is the Tuesday a week earlier, when the forecast runs.
- **`implied_so_far`:** how much the diesel benchmark price has moved over the Monday and Tuesday of the pricing week, compared with last week's average, in ₱/L with VAT. The model only uses data up to the forecast day, so it never sees the future.
- **`brent_5d_pct` and `fx_5d_pct`:** the 5-day trends in Brent crude and USD/PHP that the proposal specifies.
- **`last_week`:** the adjustment that just took effect (a lag feature).
- **`actual`:** what we're trying to predict. The top row is empty because that Tuesday hasn't happened yet; it's the one we forecast.

---

## Step 4 — Inside the two techniques (2 min)

```bash
make explain
```

**Explain each table from the top:**

1. **"How the two techniques are blended."**
   - k-NN says −₱2.30 with a **26%** weight; linear regression says −₱5.90 with a **74%** weight; the hybrid gives −₱4.95.
   - The weights aren't hand-picked. They're learned from how well each technique did over the last 26 weeks of training data.
2. **"Conditions when the forecast was made."** The 10 inputs, in plain language. The key one is "Price change so far this week: −₱5.65/L". Diesel also sits 12.6% below its 20-day average.
3. **"k-NN: the 7 most similar past weeks."**
   - This is the "match current conditions to historical patterns" part of the proposal.
   - The closest week is **2022-12-13**: a similar −₱5.58 early-week drop, which ended as a **−₱7.15** rollback.
   - Six of the seven neighbors were rollbacks, but **2022-05-31** ended as a **+₱1.55 hike**. This shows why a one-week-ahead forecast is uncertain: similar starts can end differently.
4. **"Linear regression: what moves the forecast."**
   - "Price change so far this week" has by far the largest weight. The model extends the early-week movement to the rest of the week.
   - "Diesel vs its 20-day average" comes second. When diesel is already far below its recent average, the model expects some of that gap to persist.

---

## Step 5 — The expert system (2 min)

Scroll back to **Section 6 · Advice** in the `make offline` output. There is one panel per persona, each showing its weekly diesel volume.

**Explain using the fleet panel:**

- **Headline:** "Diesel: rollback of about −₱4.95/L expected (range −₱7.10 to −₱2.85; high confidence)".
- **Decision: Wait for the rollback.** This is the timing conclusion the rules reached.
- **Bullet:** "Defer bulk purchases until after Tuesday's rollback to save about ₱24,750.00 on 5,000 L". The rules multiply the forecast by the persona's weekly volume.
- **Reasoning:** the rules that fired, in order. This is the expert system explaining itself:
  1. `classify-confidence-high` and `classify-size-large` turn numbers into categories.
  2. `compute-impact` works out the ₱ cost for this persona.
  3. `signal-strong` then `timing-wait` decide the timing: a confident rollback means wait.
  4. `fleet-wait` is the persona-specific advice.
  5. `emit-headline` writes the summary.
- **How the engine works:** it is forward chaining. On each cycle it fires the highest-priority (salience) rule whose conditions match, adds new facts, and repeats until no rule matches.

Point out that the motorist panel (₱198 saved on 40 L) and the tricycle panel (₱123.75 a week) reach the same decision with different wording and amounts.

---

## Step 6 — What-if scenarios with the advisor (2 min)

Run each one and point out how the panel changes.

**a) A confident price hike for a tricycle driver**

```bash
make advise PERSONA=tricycle PRED=1.2 CONFIDENCE=0.85
```

→ A red panel. Decision: **Buy before Tuesday**. "Refuel before Tuesday. Set aside about ₱30.00 extra this week (25 L)."

**b) The same kind of forecast, but uncertain**

```bash
uv run fuelcast advise --persona motorist --pred 0.3 --low -0.4 --high 1.0 --confidence 0.5
```

→ Decision: **Buy as usual**. "No strong signal. Refuel as you normally would."

**Say:** "The advisor doesn't tell people to act on a coin flip. When confidence is low, it says so."

**c) A geopolitical shock**

```bash
uv run fuelcast advise --persona fleet --pred 2.5 --confidence 0.9 --shock "Strait of Hormuz closure"
```

**Point out:**

- `[SHOCK WEEK]` in the headline.
- The range widened from ±₱0.50 to **+₱0.75 to +₱4.25**.
- Decision: **Partial top-up only (shock)**, instead of the normal "buy everything before Tuesday". There's also a fuel-surcharge action for fleets.
- In the reasoning line, `shock-override` fires right after classification, before any timing rule.

**Say:** "This is the override rule from the proposal. In a shock week the model's history may not apply, so the rules deliberately become more cautious."

---

## Step 7 — Stress tests (1 min)

Scroll to **Section 7 · Shock stress tests** in the `make offline` output.

**Explain:**

- **What it does:** each scenario distorts the 5 trading days leading up to the Tuesday forecast and re-runs the whole pipeline.
- **"Brent +15%" and "Brent −20%":** "Shock detected" turns to **Yes**, and the fleet decision switches to the shock-mode advice. The crash scenario deepens the rollback to −₱13.05.
- **"Peso weakens 4%":** with oil unchanged, the rollback shrinks from −₱4.95 to −₱3.05. The exchange rate alone moves pump prices.
- **"Diesel-only spike (+18%)":** Brent barely moves (+3.0%), but the forecast flips to a **+₱3.65 hike**. The model follows the diesel benchmark, not just crude oil.

---

## Step 8 — Evaluation: baselines and failure cases (2 min)

```bash
make evaluate
```

**Section 2 · Walk-forward evaluation:**

- **Walk-forward** means that for each of 352 weeks, the model is trained only on earlier weeks and then makes the Tuesday forecast for the following week, just as it would in real use.
- **Hybrid model:** **80.1%** directional accuracy, with an average error of **₱0.81/L**, one week ahead.
- **Baselines** (dimmed rows): only **51–53%** directional accuracy, with errors of **₱1.89–2.26/L**.
- The second table repeats this for the 50 shock weeks. The hybrid gets 94.0% of directions right there, because big moves are easier to call.

**Section 3 · Comparison with baselines:**

- **Error reduction 57–64%:** the hybrid makes well under half the baselines' error.
- **Weeks with smaller error 77–80%.**
- **p-values < 0.001, ✓ Significant:** the improvement is statistically real, not luck.

**Section 4 · Where the hybrid model fails** (the most interesting part). Point at the **red rows**:

| Row | Direction correct | What to say |
|---|---|---|
| Prices reversed after Tuesday | 8.6% | The pricing week turned around after our Tuesday forecast. With only 2 of 5 days known, no model can see that. This is the main cost of a one-week lead time. |
| Near-flat moves (≤ ₱0.25) | 44.4% | When the real move is tiny, up versus down is close to noise. |
| Lower-confidence forecasts | 53.8% | The model knows when it's unsure (vs 93.6% when confident), which is why the advisor relies on confidence. |
| Direction changed from last week | 69.3% | Turning points are harder than continuing trends. |

Then show the **"Worst 10 failure weeks"** table below it. Each miss has an automatically generated likely cause, for example "Prices reversed after Tuesday".

---

## Step 9 — Tests (30 s)

```bash
make test
```

→ `76 passed`.

**Say:**

- The tests cover the scoring maths, the baselines, the significance tests, that the model never sees future data, and that forecasts are made on Tuesday, one week ahead.
- They also cover bad inputs: missing or malformed DOE files, a network outage, negative prices, and holidays.
- And every combination of persona, direction, confidence, and shock, so the advisor never produces empty advice.

---

## Step 10 — Limitations and next steps (1 min, no commands)

**Say honestly:**

1. **Targets are estimated, not official.** Because the estimates are built from the same market data as the features, the 80% accuracy is an upper bound. Next step: load the official DOE diesel adjustments into `data/doe_adjustments.csv` (columns `effective_date,diesel`) and re-run `make evaluate`. No code changes are needed.
2. **The MOPS data is a substitute.** We used NYMEX ULSD diesel futures, because real MOPS Gasoil is a paid Platts feed.
3. **A one-week lead time has a cost.** Late-week reversals are the main failure mode. A mid-week update (for example, re-running on Thursday, when accuracy rises to about 94%) would let users refine their plans.

---

## Possible questions and answers

| Question | Answer |
|---|---|
| Why forecast on Tuesday? | DOE adjustments take effect every Tuesday, so forecasting on that day gives users a full week of lead time. The trade-off: only 2 of the 5 pricing days are known. Accuracy is 80% on Tuesday versus about 94% on Thursday. The day is configurable (`asof_weekday` in `config.py`). |
| Why only diesel? | Diesel is what transport operators and fleets run on, so it's where weekly swings hurt budgets most. It also keeps one clear benchmark (MOPS Gasoil). |
| Why does k-NN get 26% weight, not 50%? | Linear regression is more accurate on average, so the learned blend favors it. With only two days of data, similar past weeks add real information, so k-NN's weight is much higher than with a Thursday cutoff (3%). |
| How is "shock week" decided? | Brent moving 8% or more in 5 days, Brent volatility 2.5 standard deviations above its 1-year average, or a manual `--shock` flag. |
| What's the 80% range? | The forecast plus or minus 1.28 standard deviations of the model's uncertainty. In backtesting, it contained the actual value 74% of the time, so it's slightly too narrow one week ahead. Widening it is a possible improvement. |
| What if Yahoo Finance is down? | `--offline` reuses the cached data, and a failed download stops with a clear error instead of producing a wrong forecast. |
| Is this financial advice? | No. It's a decision-support tool, and the advice states its confidence and range. |

## If something goes wrong during the demo

| Problem | Fix |
|---|---|
| A command hangs or is slow | Open `reports/report.md` and `reports/evaluation.md`; they contain the same tables. |
| Tables wrap or look squashed | Widen the terminal or shrink the font; the output adapts to the window width. |
| `sqlite3` is missing | Skip Step 3 and use the "Conditions when the forecast was made" table from `make explain` instead. |
| Numbers differ from this script | The market data was refreshed (`make run`). The explanations still hold; read the new numbers from the screen. |
