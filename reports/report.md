# Diesel Price Adjustment Forecast — Tue, Dec 1, 2026

_Generated November 26, 2026 00:52_

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
