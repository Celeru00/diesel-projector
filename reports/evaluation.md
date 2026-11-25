# Diesel Forecast Evaluation

_Generated November 25, 2026 23:16_

> ⚠ **Data note:** no official DOE history was supplied. The model is trained and scored on **estimated** adjustments computed from market prices, so accuracy figures are optimistic.

## Walk-forward evaluation

Each of the last 352 weeks was predicted using only earlier weeks.

| Model | Direction correct | Precision | Recall | F1 | MAE (₱/L) | RMSE (₱/L) | In 80% range |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Hybrid (k-NN + LR) | 93.8% | 0.79 | 0.78 | 0.79 | 0.21 | 0.34 | 85% |
| k-NN | 85.8% | 0.69 | 0.71 | 0.70 | 0.95 | 1.59 | 67% |
| **Linear regression** | 94.3% | 0.82 | 0.80 | 0.81 | 0.20 | 0.32 | 75% |
| Baseline: persistence | 52.8% | 0.39 | 0.39 | 0.39 | 2.26 | 3.53 | 76% |
| Baseline: majority class | 51.1% | 0.32 | 0.34 | 0.29 | 1.89 | 2.77 | 71% |

### Shock weeks only (57 weeks)

| Model | Direction correct | Precision | Recall | F1 | MAE (₱/L) | RMSE (₱/L) | In 80% range |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Hybrid (k-NN + LR) | 94.7% | 0.64 | 0.65 | 0.65 | 0.38 | 0.59 | 79% |
| k-NN | 89.5% | 0.61 | 0.62 | 0.61 | 1.90 | 2.68 | 56% |
| **Linear regression** | 94.7% | 0.64 | 0.65 | 0.65 | 0.36 | 0.53 | 56% |
| Baseline: persistence | 59.6% | 0.42 | 0.41 | 0.42 | 3.97 | 5.27 | 40% |
| Baseline: majority class | 49.1% | 0.33 | 0.35 | 0.32 | 3.68 | 4.66 | 33% |

## Comparison with baselines

| Model | Compared with | Direction correct | Error reduction | Weeks with smaller error | Diebold–Mariano p | McNemar p | Significant |
| --- | --- | ---: | ---: | ---: | ---: | ---: | :---: |
| Hybrid (k-NN + LR) | persistence | 93.8% vs 52.8% | 91% | 94% | < 0.001 | < 0.001 | ✓ |
| Hybrid (k-NN + LR) | majority class | 93.8% vs 51.1% | 89% | 90% | < 0.001 | < 0.001 | ✓ |
| k-NN | persistence | 85.8% vs 52.8% | 58% | 81% | < 0.001 | < 0.001 | ✓ |
| k-NN | majority class | 85.8% vs 51.1% | 50% | 81% | < 0.001 | < 0.001 | ✓ |
| Linear regression | persistence | 94.3% vs 52.8% | 91% | 95% | < 0.001 | < 0.001 | ✓ |
| Linear regression | majority class | 94.3% vs 51.1% | 89% | 90% | < 0.001 | < 0.001 | ✓ |

Error reduction = 1 − model MAE ÷ baseline MAE. Diebold–Mariano tests whether error sizes differ; McNemar tests whether directional hits differ (p < 0.05 = significant).

## Where the hybrid model fails

A failure is a wrong direction, or the right direction but an error above max(2 × MAE, ₱0.50).

| Condition | Weeks | Direction correct | Failure rate | MAE (₱/L) |
| --- | ---: | ---: | ---: | ---: |
| All weeks | 352 | 93.8% | 14.5% | 0.21 |
| Shock weeks | 57 | 94.7% | 24.6% | 0.38 |
| Normal weeks | 295 | 93.6% | 12.5% | 0.18 |
| Direction changed from last week | 166 | 89.8% | 19.9% | 0.21 |
| Same direction as last week | 186 | 97.3% | 9.7% | 0.21 |
| Near-flat moves (≤ ₱0.25) | 54 | 64.8% | 38.9% | 0.14 |
| Clear moves (> ₱0.25) | 298 | 99.0% | 10.1% | 0.22 |
| Large moves (≥ ₱1.50) | 127 | 100.0% | 18.1% | 0.31 |
| Small or moderate moves | 225 | 90.2% | 12.4% | 0.15 |
| High-confidence forecasts (≥ 75%) | 308 | 99.0% | 9.7% | 0.21 |
| Lower-confidence forecasts | 44 | 56.8% | 47.7% | 0.19 |
| Prices reversed after Thursday | 19 | 21.1% | 84.2% | 0.32 |
| No late reversal | 333 | 97.9% | 10.5% | 0.20 |

### Worst failure weeks

| Week | Failure | Actual | Forecast | Confidence | Likely cause |
| --- | --- | ---: | ---: | ---: | --- |
| 2026-10-06 | Wrong direction | −₱0.90 | +₱0.10 | 56% | Prices reversed after thursday |
| 2021-11-30 | Wrong direction | −₱0.80 | +₱0.05 | 45% | Prices reversed after thursday |
| 2026-08-04 | Wrong direction | ±₱0.00 | +₱0.45 | 74% | Tiny move (within ±₱0.25); prices reversed after thursday; shock week; direction changed from last week |
| 2023-10-17 | Wrong direction | +₱0.15 | −₱0.25 | 77% | Tiny move (within ±₱0.25); prices reversed after thursday; direction changed from last week; overconfident |
| 2025-08-05 | Wrong direction | −₱0.20 | +₱0.20 | 69% | Tiny move (within ±₱0.25); prices reversed after thursday; direction changed from last week |
| 2022-08-16 | Wrong direction | +₱0.35 | +₱0.05 | 49% | Prices reversed after thursday; direction changed from last week |
| 2024-03-19 | Wrong direction | +₱0.10 | −₱0.15 | 69% | Tiny move (within ±₱0.25); prices reversed after thursday; direction changed from last week |
| 2021-12-21 | Wrong direction | −₱0.05 | +₱0.15 | 66% | Tiny move (within ±₱0.25); prices reversed after thursday; direction changed from last week |
| 2022-02-22 | Wrong direction | ±₱0.00 | +₱0.20 | 85% | Tiny move (within ±₱0.25); prices reversed after thursday; direction changed from last week; overconfident |
| 2022-06-28 | Wrong direction | +₱0.20 | ±₱0.00 | 40% | Tiny move (within ±₱0.25); shock week |
| 2025-02-25 | Wrong direction | ±₱0.00 | +₱0.20 | 74% | Tiny move (within ±₱0.25); prices reversed after thursday; direction changed from last week |
| 2022-03-01 | Wrong direction | −₱0.20 | −₱0.05 | 55% | Tiny move (within ±₱0.25); direction changed from last week |
| 2022-08-02 | Wrong direction | −₱0.05 | +₱0.10 | 64% | Tiny move (within ±₱0.25); direction changed from last week |
| 2023-09-05 | Wrong direction | −₱0.05 | +₱0.10 | 54% | Tiny move (within ±₱0.25); prices reversed after thursday; direction changed from last week |
| 2020-04-14 | Wrong direction | −₱0.05 | −₱0.15 | 72% | Tiny move (within ±₱0.25); shock week; direction changed from last week |
| 2020-07-21 | Wrong direction | −₱0.15 | −₱0.05 | 52% | Tiny move (within ±₱0.25); direction changed from last week |
| 2021-09-14 | Wrong direction | −₱0.05 | −₱0.15 | 83% | Tiny move (within ±₱0.25); direction changed from last week; overconfident |
| 2023-04-04 | Wrong direction | −₱0.05 | −₱0.15 | 65% | Tiny move (within ±₱0.25); prices reversed after thursday; direction changed from last week |
| 2020-08-25 | Wrong direction | −₱0.10 | ±₱0.00 | 39% | Tiny move (within ±₱0.25); prices reversed after thursday |
| 2021-07-06 | Wrong direction | ±₱0.00 | −₱0.10 | 64% | Tiny move (within ±₱0.25); prices reversed after thursday; direction changed from last week |
