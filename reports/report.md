# Diesel Price Adjustment Forecast — Tue, Dec 1, 2026

_Generated November 25, 2026 23:20_

> ⚠ **Data note:** no official DOE history was supplied. The model is trained and scored on **estimated** adjustments computed from market prices, so accuracy figures are optimistic.

## Forecast

|  |  |
| --- | --- |
| Effective | Tue, Dec 1, 2026, 6:00 AM |
| Forecast | **▼ ROLLBACK −₱4.95 per liter** |
| 80% range | −₱7.10 to −₱2.85 per liter |
| Confidence | >99% |
| k-NN / linear regression | −₱2.30 / −₱5.90 (agree) |
| Shock check | Normal week (Brent −1.9% over 5 days) |
| Forecast made | Tue, Nov 24, 2026 (runs every Tuesday, one week ahead) |
| Based on | 456 past weeks |

## Advice

### Private motorist (40 L/week)

**Diesel: rollback of about −₱4.95/L expected (range −₱7.10 to −₱2.85; high confidence)**

Decision: **Wait for the rollback**

- If your tank allows, wait until Tuesday to refuel and save about ₱198.00 on 40 L.
- This is a large move compared with typical weekly adjustments (usually under ₱1.50/L).

<sub>Reasoning: classify-confidence-high → classify-size-large → compute-impact → signal-strong → timing-wait → motorist-wait → all-large-move → emit-headline</sub>

### Tricycle operator (25 L/week)

**Diesel: rollback of about −₱4.95/L expected (range −₱7.10 to −₱2.85; high confidence)**

Decision: **Wait for the rollback**

- Refuel daily as usual and skip a full tank on Monday. The rollback saves about ₱123.75 a week.
- This is a large move compared with typical weekly adjustments (usually under ₱1.50/L).

<sub>Reasoning: classify-confidence-high → classify-size-large → compute-impact → signal-strong → timing-wait → tricycle-wait → all-large-move → emit-headline</sub>

### Fleet / logistics operator (5,000 L/week)

**Diesel: rollback of about −₱4.95/L expected (range −₱7.10 to −₱2.85; high confidence)**

Decision: **Wait for the rollback**

- Defer bulk purchases until after Tuesday's rollback to save about ₱24,750.00 on 5,000 L.
- This is a large move compared with typical weekly adjustments (usually under ₱1.50/L).

<sub>Reasoning: classify-confidence-high → classify-size-large → compute-impact → signal-strong → timing-wait → fleet-wait → all-large-move → emit-headline</sub>

## Data cleaning

2,312 trading days after cleaning; all prices converted to ₱/L.

| Series | Gaps forward-filled | Bad ticks removed |
| --- | ---: | ---: |
| Brent crude (BZ=F) | 71 | 0 |
| Diesel benchmark (HO=F) | 72 | 1 |
| USD/PHP (PHP=X) | 270 | 2 |

## Walk-forward evaluation

Each of the last 352 weeks was predicted using only earlier weeks.

| Model | Direction correct | Precision | Recall | F1 | MAE (₱/L) | RMSE (₱/L) | In 80% range |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Hybrid (k-NN + LR) | 80.1% | 0.63 | 0.63 | 0.63 | 0.81 | 1.29 | 74% |
| k-NN | 73.0% | 0.56 | 0.56 | 0.56 | 1.12 | 1.76 | 61% |
| **Linear regression** | 80.4% | 0.63 | 0.63 | 0.63 | 0.81 | 1.32 | 75% |
| Baseline: persistence | 52.8% | 0.39 | 0.39 | 0.39 | 2.26 | 3.53 | 76% |
| Baseline: majority class | 51.1% | 0.32 | 0.34 | 0.29 | 1.89 | 2.77 | 71% |

### Shock weeks only (50 weeks)

| Model | Direction correct | Precision | Recall | F1 | MAE (₱/L) | RMSE (₱/L) | In 80% range |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Hybrid (k-NN + LR) | 94.0% | 0.63 | 0.64 | 0.63 | 1.60 | 2.30 | 56% |
| k-NN | 92.0% | 0.62 | 0.63 | 0.62 | 2.21 | 2.96 | 54% |
| **Linear regression** | 94.0% | 0.63 | 0.64 | 0.63 | 1.53 | 2.39 | 52% |
| Baseline: persistence | 64.0% | 0.44 | 0.44 | 0.44 | 4.32 | 5.95 | 42% |
| Baseline: majority class | 52.0% | 0.34 | 0.35 | 0.33 | 4.16 | 5.06 | 20% |

## Comparison with baselines

| Model | Compared with | Direction correct | Error reduction | Weeks with smaller error | Diebold–Mariano p | McNemar p | Significant |
| --- | --- | ---: | ---: | ---: | ---: | ---: | :---: |
| Hybrid (k-NN + LR) | persistence | 80.1% vs 52.8% | 64% | 80% | < 0.001 | < 0.001 | ✓ |
| Hybrid (k-NN + LR) | majority class | 80.1% vs 51.1% | 57% | 77% | < 0.001 | < 0.001 | ✓ |
| k-NN | persistence | 73.0% vs 52.8% | 51% | 76% | < 0.001 | < 0.001 | ✓ |
| k-NN | majority class | 73.0% vs 51.1% | 41% | 75% | < 0.001 | < 0.001 | ✓ |
| Linear regression | persistence | 80.4% vs 52.8% | 64% | 78% | < 0.001 | < 0.001 | ✓ |
| Linear regression | majority class | 80.4% vs 51.1% | 57% | 76% | < 0.001 | < 0.001 | ✓ |

Error reduction = 1 − model MAE ÷ baseline MAE. Diebold–Mariano tests whether error sizes differ; McNemar tests whether directional hits differ (p < 0.05 = significant).

## Where the hybrid model fails

A failure is a wrong direction, or the right direction but an error above max(2 × MAE, ₱0.50).

| Condition | Weeks | Direction correct | Failure rate | MAE (₱/L) |
| --- | ---: | ---: | ---: | ---: |
| All weeks | 352 | 80.1% | 28.4% | 0.81 |
| Shock weeks | 50 | 94.0% | 36.0% | 1.60 |
| Normal weeks | 302 | 77.8% | 27.2% | 0.68 |
| Direction changed from last week | 166 | 69.3% | 35.5% | 0.75 |
| Same direction as last week | 186 | 89.8% | 22.0% | 0.86 |
| Near-flat moves (≤ ₱0.25) | 54 | 44.4% | 55.6% | 0.36 |
| Clear moves (> ₱0.25) | 298 | 86.6% | 23.5% | 0.89 |
| Large moves (≥ ₱1.50) | 127 | 94.5% | 27.6% | 1.40 |
| Small or moderate moves | 225 | 72.0% | 28.9% | 0.48 |
| High-confidence forecasts (≥ 75%) | 233 | 93.6% | 18.5% | 0.89 |
| Lower-confidence forecasts | 119 | 53.8% | 47.9% | 0.66 |
| Prices reversed after Tuesday | 58 | 8.6% | 91.4% | 1.00 |
| No late reversal | 294 | 94.2% | 16.0% | 0.77 |

### Worst failure weeks

| Week | Failure | Actual | Forecast | Confidence | Likely cause |
| --- | --- | ---: | ---: | ---: | --- |
| 2026-04-14 | Wrong direction | −₱3.95 | +₱2.80 | 99% | Prices reversed after Tuesday; shock week; direction changed from last week; overconfident |
| 2026-09-15 | Wrong direction | +₱3.65 | −₱1.05 | 75% | Prices reversed after Tuesday |
| 2022-11-01 | Wrong direction | +₱3.90 | −₱0.10 | 52% | Direction changed from last week |
| 2026-05-12 | Wrong direction | −₱2.55 | +₱0.90 | 72% | Prices reversed after Tuesday; direction changed from last week |
| 2026-04-28 | Wrong direction | +₱2.55 | −₱0.25 | 60% | Prices reversed after Tuesday; shock week; direction changed from last week |
| 2022-05-31 | Wrong direction | +₱1.55 | −₱1.10 | 94% | Direction changed from last week; overconfident |
| 2026-02-24 | Wrong direction | +₱1.30 | −₱1.20 | 83% | Prices reversed after Tuesday; direction changed from last week; overconfident |
| 2022-10-25 | Wrong direction | −₱1.00 | +₱1.30 | 86% | Prices reversed after Tuesday; direction changed from last week; overconfident |
| 2026-05-26 | Wrong direction | −₱0.55 | +₱1.65 | 86% | Prices reversed after Tuesday; direction changed from last week; overconfident |
| 2022-08-16 | Wrong direction | +₱0.35 | −₱1.60 | 98% | Prices reversed after Tuesday; direction changed from last week; overconfident |
| 2025-10-28 | Wrong direction | +₱1.95 | +₱0.05 | 51% | Direction changed from last week |
| 2022-10-04 | Wrong direction | +₱0.65 | −₱1.05 | 91% | Prices reversed after Tuesday; overconfident |
| 2025-05-06 | Wrong direction | −₱1.45 | +₱0.10 | 53% | Direction changed from last week |
| 2026-10-06 | Wrong direction | −₱0.90 | +₱0.50 | 61% | Prices reversed after Tuesday |
| 2023-07-11 | Wrong direction | +₱0.65 | −₱0.70 | 80% | Prices reversed after Tuesday; direction changed from last week; overconfident |
| 2025-09-30 | Wrong direction | +₱0.85 | −₱0.40 | 69% | Prices reversed after Tuesday |
| 2025-01-28 | Wrong direction | −₱1.05 | +₱0.15 | 54% | Direction changed from last week |
| 2024-02-13 | Wrong direction | +₱1.00 | −₱0.20 | 59% | Prices reversed after Tuesday |
| 2022-08-02 | Wrong direction | −₱0.05 | −₱1.15 | 91% | Tiny move (within ±₱0.25); direction changed from last week; overconfident |
| 2023-04-04 | Wrong direction | −₱0.05 | +₱1.05 | 89% | Tiny move (within ±₱0.25); prices reversed after Tuesday; direction changed from last week; overconfident |

## Shock stress tests

Each scenario distorts the last 5 trading days of real data and re-runs the whole pipeline.

| Scenario | Brent 5-day | Forecast | 80% range | Shock detected | Fleet decision |
| --- | ---: | ---: | ---: | --- | --- |
| Actual market (no change) | −1.9% | −₱4.95 | −₱7.10 to −₱2.85 | No | Wait for the rollback |
| Brent +15% over 5 days | +12.9% | +₱1.75 | −₱0.40 to +₱3.90 | Brent moved +12.9% in 5 days | Partial top-up only (shock) |
| Brent −20% over 5 days | −21.5% | −₱13.05 | −₱14.75 to −₱11.40 | Brent moved −21.5% in 5 days | Buy only as needed (shock) |
| Peso weakens 4% | −1.9% | −₱3.05 | −₱4.70 to −₱1.45 | No | Wait for the rollback |
| Diesel-only spike (+18%) | +3.0% | +₱3.65 | +₱1.90 to +₱5.35 | No | Buy before Tuesday |
