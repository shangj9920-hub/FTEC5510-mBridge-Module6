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

## 4b. Incremental effect of each mechanism (S4 vs S2, S4 vs S3)

Proposal section 4.3 asks for exactly these two contrasts: comparing **S4 with S2**
isolates what *waiting* adds on top of dynamic ordering, and comparing **S4 with S3**
isolates what *dynamic ordering* adds on top of waiting. Paired by seed, 30 seeds per
cell (`*` = 95 % CI excludes 0). Machine-readable form: `evidence/contrasts.csv`.

### S4 - S2: what waiting adds to dynamic ordering

| Metric | Unit | Normal | Low RMB | Surge | Tight due | Large | Delay in | FX shock |
|---|---|---|---|---|---|---|---|---|
| All completion | pp | -0.25 | -0.11 | -0.15 | -0.25* | -0.17 | -1.22* | -1.75 |
| All mean delay | s | +184* | +339* | +464* | +136* | +208* | +236* | +226* |
| All P95 delay | s | +1,096* | +1,647* | +1,062* | +772* | +277 | +1,312* | +1,302* |
| URGENT mean delay | s | +18* | +44* | -20 | +11* | -2 | +42* | +37* |
| NORMAL completion | pp | -0.36 | -0.20 | -0.48 | -0.40 | -0.42 | -1.50* | -2.43 |
| FX trades | trades | -8.6* | -12.4* | -15.6* | -7.6* | -5.0* | -11.3* | -10.6* |
| FX cost | RMB | -808* | -1,010* | -1,194* | -782* | -386* | -1,552* | -1,928* |
| RMB liquidity | M-hours | -0.74* | -1.35* | -0.28* | -0.67* | -0.12* | -0.89* | -0.73* |

Adding waiting to ordering **costs 136-464 s of mean delay in all seven scenarios**
and saves 5-16 FX trades, which is worth only RMB 386-1,928. Completion is
0.1-1.8 pp lower (significant in `tight_deadlines` and `delayed_inflows`). In other
words: under these parameters the second mechanism buys cheap liquidity with
expensive time.

### S4 - S3: what dynamic ordering adds to waiting

| Metric | Unit | Normal | Low RMB | Surge | Tight due | Large | Delay in | FX shock |
|---|---|---|---|---|---|---|---|---|
| All completion | pp | +0.19 | +0.61* | +2.69* | +0.06 | +1.89* | +0.50* | +0.58 |
| All mean delay | s | -58* | -101* | -815* | -58* | -631* | -56* | -72* |
| All P95 delay | s | -90 | -25 | -1,992* | -235* | -2,202* | +42 | -146 |
| URGENT mean delay | s | -171* | -337* | -1,256* | -154* | -978* | -192* | -250* |
| NORMAL completion | pp | +0.13 | +0.57 | -4.34* | -0.04 | -6.31* | +0.31 | -0.17 |
| FX trades | trades | +0.5 | +0.9 | +0.7 | +1.4* | +1.7* | +2.0* | +1.1 |
| FX cost | RMB | +143 | +195* | +307 | +117* | +460* | +323* | +416 |
| RMB liquidity | M-hours | +0.06* | +0.13* | +0.09* | +0.10* | +0.08* | +0.09* | +0.05* |

Adding ordering to waiting is what actually rescues S3: **56-815 s less mean delay in
all seven scenarios**, 154-1,256 s less urgent delay, and up to +2.7 pp completion.
The familiar cost shows up again - ordinary completion falls 4.3 / 6.3 pp in
`payment_surge` / `large_payments` - but the level is far better than S3.

### Reading the two tables together

* **Ordering is the productive mechanism.** It is worth 56-815 s when added to
  waiting (S4 - S3), while waiting is worth -136 to -464 s when added to ordering
  (S4 - S2).
* **Waiting only pays in FX cost**, and by a small amount relative to the delay it
  introduces; that is a property of the fixture parameters (HKD 15 m, 120 s FX), not
  of the rule.
* `S3 - S2` is deliberately not tabulated: it swaps both mechanisms at once, so it
  cannot attribute the difference to either one.

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

## 5b. Queue length, balance paths and delay distribution (proposal 5.2)

The proposal's deliverables table asks for a **queue-length chart**, a **liquidity
chart** and a **delay distribution**; the additional-measures paragraph also asks for
**ordinary-payment maximum queueing time** and **outstanding share**. All five are
reported here. Figures are drawn from one representative run (seed 20001) and are
regenerated by `module6/make_appendix_figures.py`; the numbers below are means over
the 30 seeds.

| Figure | Content |
|---|---|
| `figures/fig3_queue_length.png` | Queue length (arrived and not settled) over time, Normal and Payment surge |
| `figures/fig4_liquidity.png` | RMB balance held over time, Normal and Payment surge |
| `figures/fig5_delay_distribution.png` | p50/p90/p95/p99 of settlement delay, NORMAL vs URGENT, S1 vs S2 |

Both queue paths confirm the mechanism: in the Normal scenario the queue stays
below about a dozen payments and every strategy is flat; under the surge the queue
grows monotonically to 80-100 payments because arrivals (240 per run, one every
30 s) exceed what the RMB balance can settle, and the ordering strategies keep that
queue ~20 payments shorter than S0. The balance chart shows why: after about 2.5
hours the bank sits near its reserve floor and can only pay from inflows and FX, which
is the situation the whole experiment is about.

### Ordinary-payment waiting and outstanding share (payment surge)

| Strategy | Completion | Outstanding share | NORMAL max queue (s) | ALL max queue (s) |
|---|---|---|---|---|
| S0 | 0.630 | 37.0% | 10,807 | 10,902 |
| S1 | 0.683 | 31.7% | 11,461 | 12,288 |
| S2 | 0.706 | 29.4% | 13,223 | 13,418 |
| S3 | 0.677 | 32.2% | 11,504 | 11,992 |
| S4 | 0.704 | 29.6% | 13,935 | 14,121 |

### Settlement-delay quantiles (payment surge, seconds)

| Strategy | NORMAL p50 | p90 | p95 | p99 | URGENT p50 | p90 | p95 | p99 |
|---|---|---|---|---|---|---|---|---|
| S0 | 224 | 3,978 | 6,151 | 8,351 | 250 | 2,916 | 4,064 | 5,240 |
| S1 | 198 | 3,365 | 5,635 | 8,018 | 209 | 2,914 | 4,329 | 5,522 |
| S2 | 76 | 1,339 | 2,930 | 5,694 | 120 | 1,580 | 2,149 | 3,360 |
| S3 | 1,189 | 4,780 | 6,259 | 8,214 | 1,270 | 4,180 | 5,163 | 6,132 |
| S4 | 515 | 3,432 | 4,481 | 7,260 | 151 | 1,460 | 2,069 | 3,265 |

**Read the quantiles together with the completion column.** Delay statistics are
conditional on settlement: S2 leaves more ordinary payments unsettled (-4.55 pp), so
part of its apparent quantile improvement is a selection effect. That is exactly why
the work split requires delay and outstanding counts to be reported side by side - a
strategy must not be able to buy a better delay distribution by finishing fewer
payments.

### Improvement rate relative to S1 (proposal 4.5)

`improvement = (S1 - treatment) / S1` for lower-is-better metrics and the reverse for
completion, so **a positive number always means an improvement**. S2 is shown; the
same columns for S3 and S4 are in `evidence/comparison.csv`.

| Metric | Normal | Low RMB | Surge | Tight due | Large | Delay in | FX shock |
|------|---|---|---|---|---|---|
| All completion | +0.00% | +0.11% | +3.31% | +0.00% | +3.01% | +0.00% | +0.82% |
| Mean delay | +7.3% | +10.9% | +40.0% | +7.7% | +31.8% | +5.0% | +28.0% |
| P95 delay | +7.1% | +5.1% | +40.9% | +6.7% | +26.9% | +0.8% | +37.6% |
| NORMAL max queue | -22.3% | -2.5% | -15.4% | -29.5% | -6.1% | -18.7% | +18.2% |
| FX cost | -0.7% | -1.0% | -2.0% | -1.2% | -2.1% | -1.0% | -6.0% |
| RMB liquidity | -0.2% | -0.7% | -1.4% | -0.2% | -0.7% | -0.4% | -0.2% |

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
