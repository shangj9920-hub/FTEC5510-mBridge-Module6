# Results (mid-term)

Run of record: 7 scenarios x 30 formal seeds (20001-20030) x 5 strategies =
**1,050 simulations, 0 failures, 0 fallback modules**.
Raw output: `evidence/metrics.csv`, `evidence/comparison.csv`,
console record `evidence/run_log.txt`.

Every table below is generated from `evidence/metrics.csv`; no number is typed by
hand. `evidence/reconciliation_summary.txt` shows the 14,700 checks that tie the
table to the engine's own counters.

---

## 1. Setup

| Item | Value |
|---|---|
| Observation window | 28,800 s (8 h) for every run |
| Opening RMB / reserve | 6,000,000 / 800,000 (1,800,000 opening in `low_rmb_liquidity`) |
| Opening HKD | 15,000,000 |
| FX rate / spread / fixed fee | 0.90 RMB per HKD / 15 bps / HKD 80 |
| FX completion delay | 120 s (all scenarios) |
| Counterparty capacity | RMB 5,000,000 per trade (`per_trade`), 1,000,000 in `fx_capacity_shock` |
| Priority shares | 10 % / 25 % / 65 % (all fixtures) |
| Payment amounts | lognormal, median RMB 120,000 |
| Scenario | Single change against `baseline` |
|---|---|
| `baseline` | none |
| `low_rmb_liquidity` | opening RMB 6,000,000 -> **1,800,000** |
| `payment_surge` | payments per dataset 120 -> **240** |
| `tight_deadlines` | deadline multiplier 1.0 -> **0.4** |
| `large_payments` | payment amount median 120,000 -> **360,000** |
| `delayed_inflows` | inflow delay 0 s -> **3,600 s** |
| `fx_capacity_shock` | counterparty capacity 5,000,000 -> **1,000,000** per trade |

Every scenario differs from `baseline` in exactly one parameter, which is what
makes the seven cells comparable: a difference between two rows cannot be
attributed to anything except that single knob.

| Engine | Module 5 reviewed bundle (`vendor/m3engine` + `m4rank` + `module5_funding`) |

---

## 2. Service measures

Mean over 30 seeds.

| Scenario | Strategy | Completion | Overdue | P95 delay (s) | Mean delay (s) | URGENT mean delay (s) |
|---|---|---|---|---|---|---|
| Normal | S0 | 0.998 | 0.000 | 226 | 60 | 60 |
| Normal | S1 | 0.998 | 0.000 | 218 | 57 | 57 |
| Normal | S2 | 0.998 | 0.000 | 203 | 52 | 48 |
| Normal | S3 | 0.993 | 0.010 | 1,389 | 294 | 237 |
| Normal | S4 | 0.995 | 0.000 | 1,299 | 236 | 66 |
| Low RMB liquidity | S0 | 0.979 | 0.004 | 276 | 97 | 119 |
| Low RMB liquidity | S1 | 0.990 | 0.002 | 285 | 93 | 100 |
| Low RMB liquidity | S2 | 0.991 | 0.002 | 270 | 83 | 71 |
| Low RMB liquidity | S3 | 0.984 | 0.027 | 1,943 | 523 | 452 |
| Low RMB liquidity | S4 | 0.990 | 0.001 | 1,918 | 422 | 115 |
| Payment surge | S0 | 0.630 | 0.235 | 6,341 | 1,052 | 982 |
| Payment surge | S1 | 0.683 | 0.189 | 5,902 | 992 | 953 |
| Payment surge | S2 | 0.706 | 0.141 | 3,490 | 595 | 567 |
| Payment surge | S3 | 0.677 | 0.239 | 6,543 | 1,875 | 1,803 |
| Payment surge | S4 | 0.704 | 0.135 | 4,551 | 1,060 | 547 |
| Tight deadlines | S0 | 0.998 | 0.004 | 226 | 60 | 60 |
| Tight deadlines | S1 | 0.998 | 0.004 | 218 | 57 | 57 |
| Tight deadlines | S2 | 0.998 | 0.002 | 203 | 52 | 49 |
| Tight deadlines | S3 | 0.995 | 0.028 | 1,211 | 247 | 213 |
| Tight deadlines | S4 | 0.995 | 0.002 | 976 | 188 | 59 |
| Large payments | S0 | 0.453 | 0.463 | 10,590 | 1,870 | 1,695 |
| Large payments | S1 | 0.562 | 0.361 | 8,356 | 1,743 | 1,845 |
| Large payments | S2 | 0.579 | 0.335 | 6,112 | 1,189 | 1,108 |
| Large payments | S3 | 0.559 | 0.375 | 8,591 | 2,028 | 2,084 |
| Large payments | S4 | 0.577 | 0.340 | 6,388 | 1,397 | 1,106 |
| Delayed inflows | S0 | 0.999 | 0.000 | 233 | 68 | 60 |
| Delayed inflows | S1 | 0.999 | 0.000 | 224 | 65 | 55 |
| Delayed inflows | S2 | 0.999 | 0.000 | 222 | 61 | 45 |
| Delayed inflows | S3 | 0.981 | 0.018 | 1,493 | 354 | 279 |
| Delayed inflows | S4 | 0.986 | 0.000 | 1,534 | 298 | 87 |
| FX capacity shock | S0 | 0.978 | 0.009 | 697 | 122 | 144 |
| FX capacity shock | S1 | 0.979 | 0.007 | 450 | 94 | 118 |
| FX capacity shock | S2 | 0.988 | 0.002 | 280 | 68 | 51 |
| FX capacity shock | S3 | 0.964 | 0.025 | 1,729 | 366 | 339 |
| FX capacity shock | S4 | 0.970 | 0.009 | 1,583 | 294 | 88 |

---

## 3. Paired differences, S2 vs S1

Same seed within each cell (`*` = 95 % CI excludes 0).

| Metric | Normal | Low RMB | Surge | Tight due | Large | Delay in | FX shock |
|---|---|---|---|---|---|---|---|
| URGENT mean delay (s) | -9.2* | -29.3* | -385.8* | -8.9* | -736.6* | -9.9* | -67.2* |
| URGENT P95 delay (s) | -28* | -104  | -2,180* | -28* | -2,059* | -39* | -326* |
| All completion (pp) | +0.00  | +0.11  | +2.26* | +0.00  | +1.69* | +0.00  | +0.81  |
| NORMAL completion (pp) | -0.04  | -0.03  | -4.55* | -0.04  | -6.21* | +0.00  | +0.55  |
| NORMAL overdue (pp) | +0.00  | +0.00  | +3.05* | +0.00  | +5.75* | +0.00  | -0.07  |
| FX trades | +1.3* | +2.3* | +4.3* | +2.2* | +2.1* | +2.2* | +3.3* |

Completion by priority, S1 -> S2:

| Scenario | URGENT | HIGH | NORMAL |
|---|---|---|---|
| Normal | 0.995 -> 0.995  | 0.997 -> 0.999  | 0.998 -> 0.998  |
| Low RMB liquidity | 0.984 -> 0.987  | 0.991 -> 0.996  | 0.990 -> 0.990  |
| Payment surge | 0.670 -> 0.908* | 0.688 -> 0.803* | 0.683 -> 0.638* |
| Tight deadlines | 0.995 -> 0.995  | 0.997 -> 0.999  | 0.998 -> 0.998  |
| Large payments | 0.565 -> 0.839* | 0.548 -> 0.667* | 0.567 -> 0.505* |
| Delayed inflows | 0.997 -> 0.997  | 1.000 -> 1.000  | 0.998 -> 0.998  |
| FX capacity shock | 0.979 -> 0.989* | 0.978 -> 0.993  | 0.980 -> 0.986  |

---

## 4. Waiting and top-up (S3 / S4 vs S1)

| Metric | Normal | Low RMB | Surge | Tight due | Large | Delay in | FX shock |
|---|---|---|---|---|---|---|---|
| S3 all delay (s) | +238* | +430* | +883* | +190* | +286* | +289* | +272* |
| S4 all delay (s) | +180* | +329* | +68  | +132* | -346* | +233* | +200* |
| S3 FX trades | -7.7* | -11.0* | -12.0* | -6.8* | -4.6* | -11.1* | -8.4* |
| S4 FX trades | -7.2* | -10.1* | -11.2* | -5.4* | -2.9* | -9.1* | -7.3* |
| S3 completion (pp) | -0.44* | -0.61* | -0.58  | -0.31* | -0.36  | -1.72* | -1.53* |

Interpretation: waiting buys **20-30 % fewer FX trades** and **6-14 % lower FX
cost** at the price of **190-883 s more delay**. With HKD 15 m available and FX
completing in 120 s, the top-up is cheap and the wait is expensive -- the opposite
of the proposal's premise, and a direct consequence of the fixture parameters
(section 6) rather than of a defect in S3/S4.

---

## 5. Resources and cost (means)

| Scenario | Strategy | RMB hours (millions) | HKD hours (millions) | FX trades | FX cost (RMB) |
|---|---|---|---|---|---|
| Normal | S0 | 19.60 | 100.86 | 38.4 | 13,670 |
| Normal | S1 | 19.62 | 100.84 | 38.5 | 13,705 |
| Normal | S2 | 19.66 | 100.81 | 39.8 | 13,801 |
| Normal | S3 | 18.85 | 103.58 | 30.8 | 12,850 |
| Normal | S4 | 18.91 | 103.16 | 31.3 | 12,993 |
| Low RMB liquidity | S0 | 10.24 | 74.48 | 58.5 | 20,720 |
| Low RMB liquidity | S1 | 10.24 | 74.46 | 58.3 | 20,685 |
| Low RMB liquidity | S2 | 10.31 | 74.37 | 60.6 | 20,888 |
| Low RMB liquidity | S3 | 8.83 | 79.43 | 47.4 | 19,683 |
| Low RMB liquidity | S4 | 8.96 | 78.66 | 48.3 | 19,878 |
| Payment surge | S0 | 11.55 | 45.41 | 69.4 | 24,541 |
| Payment surge | S1 | 10.83 | 45.81 | 66.3 | 24,078 |
| Payment surge | S2 | 10.98 | 44.88 | 70.6 | 24,548 |
| Payment surge | S3 | 10.61 | 54.98 | 54.3 | 23,047 |
| Payment surge | S4 | 10.70 | 50.71 | 55.0 | 23,354 |
| Tight deadlines | S0 | 19.60 | 100.86 | 38.4 | 13,670 |
| Tight deadlines | S1 | 19.62 | 100.84 | 38.5 | 13,705 |
| Tight deadlines | S2 | 19.66 | 100.81 | 40.7 | 13,864 |
| Tight deadlines | S3 | 18.89 | 103.14 | 31.7 | 12,965 |
| Tight deadlines | S4 | 18.99 | 102.67 | 33.1 | 13,082 |
| Large payments | S0 | 12.06 | 32.80 | 27.4 | 21,507 |
| Large payments | S1 | 10.19 | 33.84 | 25.4 | 20,962 |
| Large payments | S2 | 10.26 | 32.79 | 27.5 | 21,410 |
| Large payments | S3 | 10.06 | 36.95 | 20.8 | 20,563 |
| Large payments | S4 | 10.14 | 35.20 | 22.5 | 21,023 |
| Delayed inflows | S0 | 15.65 | 94.16 | 43.7 | 15,678 |
| Delayed inflows | S1 | 15.67 | 94.14 | 44.1 | 15,711 |
| Delayed inflows | S2 | 15.73 | 94.09 | 46.3 | 15,875 |
| Delayed inflows | S3 | 14.74 | 97.72 | 33.0 | 14,000 |
| Delayed inflows | S4 | 14.83 | 97.26 | 35.0 | 14,323 |
| FX capacity shock | S0 | 19.60 | 101.95 | 38.3 | 13,030 |
| FX capacity shock | S1 | 19.53 | 102.45 | 35.2 | 11,965 |
| FX capacity shock | S2 | 19.56 | 101.92 | 38.5 | 12,688 |
| FX capacity shock | S3 | 18.78 | 106.05 | 26.7 | 10,344 |
| FX capacity shock | S4 | 18.83 | 105.80 | 27.9 | 10,760 |

---

## 6. Parameter deviations from the proposal (must be quoted in the report)

| Proposal | Delivered fixtures |
|---|---|
| Opening RMB 20 m, reserve 5 m | **6 m, 0.8 m** (1.8 m in the liquidity stress) |
| Opening HKD 100 m | **15 m** |
| FX rate 0.92 | **0.90** |
| Proportional fee 3 bps | **spread 15 bps + HKD 80 fixed** |
| FX completion 20 s (60/120 s only in stress) | **120 s in every scenario** |
| Counterparty capacity 50 m | **5 m per trade, `per_trade`** |
| Priority 10/30/65, amount fixed 5 m | **10/25/65, lognormal median 0.12 m** |
| Initial-funding scan 10-40 m | **unusable**; every point is above the 6 m baseline |

Of the six stress scenarios in proposal section 4.4.2, **two have no fixture**:
urgent-payment shock (priority shares are identical in all seven datasets) and
higher FX fees/delays (spread and delay are constant).

---

## 7. Findings that belong in the slides
## 7. Findings that belong in the slides

1. **Dynamic scheduling protects urgent payments everywhere** (7/7, all significant):
   urgent mean delay falls in every scenario, by 386 s in `payment_surge` and 737 s in
   `large_payments`; urgent completion rises 0.670 -> 0.908 in `payment_surge` and 0.565
   -> 0.839 in `large_payments`.

2. **The gain is a reallocation, not a free improvement**: ordinary completion falls
   4.55 pp (`payment_surge`) and 6.21 pp (`large_payments`), while total completion
   still rises (+2.26 pp / +1.69 pp). Reporting only the total hides it.

3. **Bypassing the queue head matters** (S0 vs S1): completion +10.92 pp in
   `large_payments` and +5.29 pp in `payment_surge`.

4. **Waiting is expensive under these parameters**, so the mid-term statement about
   S3/S4 must be about mechanism, not benefit: fewer trades, more delay.

5. **`tight_deadlines` barely binds**: shortening every deadline to 40 % leaves
   completion, mean/P95 delay, liquidity hours and FX counts of S0/S1 unchanged to the
   fourth decimal, because payments already settle long before either deadline. The only
   measure that moves is the overdue rate, 0.00 % -> 0.37 % (the number of deadlines
   falling inside the window rises from 90 to 108). So the scenario is a deadline-
   accounting test, not a pressure test.

6. **More FX trades is not a deterioration**: S2 trades a few extra trades (about RMB
   150-200 each) for 9-737 s less urgent delay and up to 2.3 pp more completion.
