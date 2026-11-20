# Module 6 — Experiment Runs, Metrics and Result Analysis

FTEC5510 Advanced Financial Infrastructure · Group 12 ·
*Liquidity-Aware HKD/RMB Cross-Border Settlement: An mBridge-Based Simulation*

This module owns the last mile of the project: it runs the five strategies on the
formal fixture set, turns the transaction-level output into one standardised
metrics table, and reports what the numbers actually say — including the parts that
are uncomfortable for the proposed policy.

Python **standard library only** — no third-party packages, same as Modules 3–5.

---

## 1. What is delivered

| Deliverable (from the team work split) | Where |
|---|---|
| Metric calculation program (`calculate_metrics`) | `module6/m6metrics/api.py` |
| Reconciliation record (computed vs engine-reported) | `evidence/reconciliation*.csv`, `docs/VALIDATION.md` §3b |
| Metric calculation program (`calculate_metrics`) | `module6/m6metrics/api.py` |
| Batch experiment runner (7 scenarios × 30 seeds × 5 strategies) | `module6/run_module6.py` |
| Strategy comparison table with 95% confidence intervals | `evidence/comparison.csv` |
| Two core figures | `evidence/figures/` |
| Findings, limitations and next steps | `docs/RESULTS.md`, `docs/PRESENTATION.md` |
| Metric definitions and the decisions Module 6 had to make | `docs/METRICS_SPEC.md` |

---

## 2. Quick start

```powershell
# 1) the metric definitions, on a hand-checkable five-payment fixture
python -m unittest discover -s module6/tests -v

# 2) reproduce the whole result set (needs the three module repositories)
python module6/run_module6.py --repos <path-with-module3/4/5> --out module6_out

# 3) regenerate the two figures from metrics.csv
python module6/make_figures.py --metrics module6_out/metrics.csv --out figures

# 4) independent audit: data contract, parameters, quoted numbers, 45-run replay
python module6/audit.py . <path-with-module3/4/5>
```

`--repos` is a directory that contains the Module 3, 4 and 5 checkouts (this
module searches recursively for `m3engine/`, `module4_rank.py` and
`module5_funding.py`, so a folder with three extracted ZIPs works as-is).
A ten-run smoke test is available before committing to the full matrix:

```powershell
python module6/run_module6.py --repos <path> --smoke
```

---

## 3. Results in one paragraph

Across 7 scenarios × 30 formal seeds × 5 strategies (1,050 runs, no fallbacks),
dynamic scheduling (S2) lowers the mean settlement delay of **urgent** payments in
all seven scenarios — by 386 s in `payment_surge` and 737 s in `large_payments` —
and raises urgent completion from 0.670 to 0.908 (surge) and 0.565 to 0.839
(large). The gain is a **reallocation**: ordinary-payment completion falls 4.55 pp
and 6.21 pp in those two scenarios. Waiting for inflows (S3/S4) cuts FX trades by
20–30 % and FX cost by 6–14 %, but raises mean delay by 190–883 s, because with
HKD 15 m of capacity and a 120 s FX completion time, waiting saves money that is
worth less than the time it costs. Full tables: `docs/RESULTS.md`.

---

## 4. Layout

```
module6/
├── run_module6.py            batch runner: engine loading, matrix, tables, validation
├── make_figures.py           two core figures from metrics.csv (Pillow, no matplotlib)
├── calculate_metrics.py      thin CLI wrapper around m6metrics.calculate_metrics
├── m6metrics/
│   ├── core.py               block_metrics, liquidity_hours, measure
│   ├── stats.py              paired_diffs, ci95, mean_of
│   ├── api.py                calculate_metrics(payment_results, events, balances, config)
│   └── __init__.py           public surface
├── fixtures/fixed_demo/      five payments, every metric checkable by hand
└── tests/test_module6.py     17 acceptance tests
docs/
├── METRICS_SPEC.md           definitions, measurement rules, open decisions
├── RESULTS.md                all tables, findings, limitations
├── VALIDATION.md             what was actually executed and what it proved
├── HANDOFF.md                interface, upstream pins, how to wire Modules 3–5
└── PRESENTATION.md           three slides and the 2.5-minute script
evidence/
├── metrics.csv               1,050 rows × 39 columns
├── comparison.csv            35 rows: cell means + paired difference vs S1 + 95% CI
├── run_log.txt               console record of the reported run
└── figures/                  fig1_benefit.png, fig2_fairness.png
```

---

## 5. Verification status

| Check | Result |
|---|---|
| Acceptance tests | **17/17 pass** in ~0.01 s |
| Metric definitions reproduce Module 4's published values | completion metrics **exact**; delay metrics within 2–5 s (engine revision, see below) |
| Full matrix | 7 × 30 × 5 = **1,050 runs, 0 failures** |
| `using_fallback_module4/5` | **false in all 1,050 runs** |
| Ineligible payments in the delivered fixtures | 0, so the denominator decision does not move any number |
| Reproducibility | same fixtures + same seeds reproduce every figure exactly |
| Reconciliation vs engine counters | **14,700 checks, 0 failures** (14 per run); CSV path and engine path agree on 7/7 sampled runs |
| Independent audit (`module6/audit.py`) | 210 datasets re-validated, parameters re-checked, quoted numbers re-derived, **45 runs replayed cell by cell: 0 mismatches** |

---

## 6. Known limitations

1. **Engine revision.** Results use Module 5's reviewed engine patch (required for a
   correct S3/S4). S0–S2 delay metrics therefore differ from Module 4's published
   table by 2–5 s; directions and significance are unchanged. Re-running with the
   unpatched Module 3 engine reproduces Module 4's numbers exactly (−11.15 s vs
   their −11.1 s). See `docs/VALIDATION.md`.
2. **`tight_deadlines` barely binds.** At a 0.4x deadline multiplier, completion,
   delay, liquidity hours and FX counts are unchanged to the fourth decimal; only
   the overdue rate moves (0.00 % -> 0.37 %). It is a deadline-accounting test
   rather than a pressure test.
3. **`fx_counterparty_capacity_mode = per_trade`** means counterparty capacity is
   never exhausted, so "FX cannot be executed" never occurs; S3/S4 therefore have
   no stage for their headline behaviour.
4. **Two of the proposal's six stress scenarios are missing** from the fixture set
   (urgent-payment shock, higher FX fees/delays).
5. **Parameter deviations** from the proposal are listed in `docs/RESULTS.md` §6;
   they must be quoted whenever the proposal's 20 m / 100 m / 3 bps / 20 s are
   mentioned.
6. FX failure fees and the proposal's proportional fee model are not implemented;
   FX economic cost = spread + fixed fee × rate.
7. Synthetic data and teaching assumptions: results are not a performance forecast
   for real banks or for the real mBridge network.
