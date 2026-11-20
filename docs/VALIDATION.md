# Validation record

Date of the reported run: 2026-11-19.
Everything below was executed, not asserted.

---

## 1. Test suite

```
python -m unittest discover -s module6/tests -v
Ran 17 tests in 0.011s
OK
```

Coverage:

| Area | Tests |
|---|---|
| Hand-checkable fixture (5 payments, every number recomputed by hand) | 8 |
| Observation endpoint derivation (`observation_end_sec`, window + drain, last balance) | 2 |
| Degraded inputs (no balances, no fx, empty payment_results) | 2 |
| Statistics (P95 interpolation, CI symmetry, pairing by seed) | 3 |
| Engine-result path `measure()` agrees with `calculate_metrics()` | 1 |
| Balance integral tolerates out-of-order rows | 1 |

The fixture encodes the three measurement traps the work split warns about:
delay is computed on settled payments only (2 of 5), an overdue *outstanding*
payment counts as a breach while an outstanding payment that is not yet due does
not, and a blank `settle_time` never becomes 0.

---

## 2. Full matrix

| Check | Result |
|---|---|
| Runs attempted / completed | 1,050 / **1,050** |
| Failures | 0 |
| `using_fallback_module4/5 == false` | **1,050 / 1,050** |
| `ineligible` payments | 0 (all fixtures have `eligible_probability = 1.0`) |
| `obs_end_sec` | 28,800 in every run |
| Scenarios × seeds × strategies | 7 × 30 × 5, 150 runs per scenario |
| Same event path per seed | yes — the dataset is loaded once per (scenario, seed) and reused by all five strategies |

---

## 3. Metric definitions cross-checked against Module 4

Module 4's `analysis/check_alignment.py` already published 30-seed paired numbers.
The pipeline here was required to reproduce them; a mismatch would mean the
definitions had drifted.

| Scenario | Metric | This module | Module 4 doc | Verdict |
|---|---|---|---|---|
| `payment_surge` | NORMAL completion S2−S1 | −4.55 pp [−5.51, −3.58] | −4.80 pp | **MATCH** |
| `large_payments` | NORMAL completion S2−S1 | −6.21 pp [−7.35, −5.07] | −6.20 pp | **MATCH** |
| `baseline` | URGENT mean delay S2−S1 | −9.19 s [−13.87, −4.51] | −11.10 s | DIRECTION-OK |
| `low_rmb_liquidity` | URGENT mean delay S2−S1 | −29.26 s | −24.10 s | DIRECTION-OK |

Result line printed by the runner: `RESULT: PASS`.

### Why the two delay rows differ, and why that is not a definition error

The reported run uses **Module 5's reviewed engine patch** (it is the only version
that runs S3/S4 correctly). Module 4's document predates that patch.

Experiment: re-run `baseline`, 30 seeds, S0/S1/S2, with the **unpatched** Module 3
engine and the same metric code:

```
URGENT mean delay  S0 59.51 s   S1 53.18 s   S2 42.03 s
S2-S1 = -11.15 s  [95% CI -15.86, -6.44]      Module 4 doc: -11.1 s [-15.9, -6.4]
```

The unpatched engine reproduces Module 4's number to the decimal, so the 2–5 s
shift comes from the engine revision (the patch changes funding-review scheduling
and duplicate-FX prevention), not from the metric definitions. The report must
state which engine produced the table.

---

## 3b. Reconciliation against the engine's own counters

`module6/reconcile.py` re-runs the matrix and compares, for **every** run, the
numbers Module 6 derives from the four tables with the numbers the engine reports
in its summary. Fourteen checks per run, 14,700 checks in total:

| Check | What it catches | Result |
|---|---|---|
| `n_payments`, `settled`, `pending`, `queued`, `ineligible`, `status_partition` | a payment silently missing from a table, or a status the table cannot represent | 1,050 / 1,050 |
| `fx_initiated`, `fx_completed`, `fx_cost_rmb` | FX rows lost, or cost computed from the wrong subset | 1,050 / 1,050 |
| `rmb_total_end`, `hkd_total_end`, `rmb_locked_end` | the final balance snapshot not being the last event of the second | 1,050 / 1,050 |
| `balance_time_monotone` | out-of-order snapshots | 1,050 / 1,050 |
| `rmb_liquidity_identity` — `opening + inflows + FX received − settled = closing` | double payment, double deduction, funds usable before settlement | 1,050 / 1,050 |

Plus a cross-check of the two independent code paths: seven runs are written to
disk and recomputed through `calculate_metrics` (CSV path) and compared with
`measure` (engine-object path) — **7/7 agree on all eight headline metrics**.

**The reconciliation found two real defects, both fixed:**

1. *FX cost was summed over completed trades only*, while the engine books the fee
   at initiation. 195 runs disagreed by the cost of one still-pending trade
   (e.g. −311.23 RMB). The table-side sum now covers all initiated trades, and
   `docs/METRICS_SPEC.md` §3.3 records the reasoning. The batch table already read
   the cost from the engine summary, so no published number moved.
2. *The final balance row was taken as the first row with the maximum timestamp.*
   At `t = T_end` the engine may write several snapshots in the same second
   (FX completion → payment submission → end of simulation), so the lock could be
   read before the last submission. 11 runs disagreed (682,267.80 RMB). The row is
   now taken as the **last row in file order**, matching the engine's final state.

Neither defect changed a published figure: after the fixes the matrix was re-run and
the resulting `metrics.csv` is identical to the previous one (1,050 rows × 39
columns, 0 differing cells). Both were caught by the reconciliation rather than by
the results, and both produced numbers that would have looked perfectly plausible in
a slide — which is exactly why this check exists.

## 4. Reproducibility

* Same fixtures + same seeds + same engine → identical `metrics.csv`. The runner
  writes no timestamps into the metrics and performs no random sampling.
* Every row carries `run_id`, `scenario_id`, `seed`, `strategy_id`,
  `obs_end_sec`, `using_fallback_m4`, `using_fallback_m5`, so any figure can be
  traced back to a configuration and a run.
* `evidence/run_log.txt` is the untouched console record of the run that produced
  `evidence/metrics.csv`.

---

## 5. What was NOT validated

* No `cumulative` counterparty-capacity run, so "FX cannot be executed" is
  unobserved.
* No FX failure scenario: the engine's pilot failure probability is 0.
* No initial-funding scan (the proposal's 10–40 m grid does not bracket the
  delivered 6 m baseline).
* Only one engine revision was exercised for the reported table.
* Passing tests do not prove the absence of defects; they prove the definitions
  behave as specified on a hand-checkable case and on 1,050 runs without error.
