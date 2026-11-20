# Module 6 interface and handoff

## 1. What Module 6 owns

Module 6 owns the **official metric set** and everything computed from it:
the metrics table, the strategy comparison with intervals, the two figures, and
the findings/limitations text. It does not own the engine, the ordering, the
funding advice, or the data.

| Producer | Owns | Delivers to Module 6 |
|---|---|---|
| Module 2 | payments, inflows, config, seeds, scenarios | `payments.csv`, `inflows.csv`, `config.json` |
| Module 3 | execution, states, balances | `payment_results.csv`, `events.csv`, `balances.csv`, `fx_trades.csv`, `run_summary.json` |
| Module 4 | order | ordering only; no numbers feed the metric table directly |
| Module 5 | funding advice | advice only; effects arrive through Module 3's tables |
| **Module 6** | **metrics and reporting** | `metrics.csv`, `comparison.csv`, figures, findings |

A strategy module's own summary is **advice, not evidence**: only Module 3's
tables are measured.

---

## 2. The interface

### 2.1 Function

```python
from m6metrics import calculate_metrics

row = calculate_metrics(
    payment_results,   # path or list of dicts (required)
    events=None,       # optional; used only for FX action counts
    balances=None,     # optional; without it liquidity hours are None
    config=None,       # observation window, rates, scenario metadata
    fx_trades=None,    # optional; without it FX cost is None
)
```

* Accepts CSV paths **or** already-loaded row lists.
* Never raises on missing inputs: the affected measures become `None` and the
  reason is appended to `row["warnings"]`.
* Pure: no file is written, nothing is mutated.
* Importing it does not import the simulation engine, so it can be called from CI
  and from a report script.

### 2.2 One run directory

```
<run_dir>/
  payment_results.csv   payment_id, arrival_time, amount_rmb, priority,
                        deadline_time, submit_time, settle_time, final_status
  events.csv            run_id, event_seq, time, event_type, payment_id, fx_id, action, reason
  balances.csv          run_id, event_seq, time, rmb_total, rmb_reserved, rmb_locked,
                        rmb_available, hkd_total, hkd_committed, hkd_available
  fx_trades.csv         run_id, fx_id, target_payment_id, initiated_at, completed_at,
                        topup_rmb, hkd_principal, hkd_fee, spread_cost_rmb,
                        total_cost_rmb, status, reason
  config.json           observation window, rates, seed, scenario id
```

CLI: `python module6/calculate_metrics.py --run-dir <dir> --append metrics.csv`

### 2.3 `metrics.csv`

First four columns are the join keys required by the work split:
`run_id, scenario_id, seed, strategy_id`. The remaining 35 columns are grouped as

* service: `ALL.*`, `URGENT.*`, `HIGH.*`, `NORMAL.*` blocks with
  `n, settled, completion, outstanding, outstanding_amount_rmb, mean_delay,
  p95_delay, due, overdue, overdue_rate`
* resources: `rmb_liquidity_hours`, `hkd_liquidity_hours`
* FX behaviour: `fx_initiated, fx_completed, fx_infeasible, fx_cost_rmb,
  fx_rmb_obtained, fx_hkd_principal`
* provenance: `n_payments, ineligible, obs_end_sec, using_fallback_m4,
  using_fallback_m5`

### 2.4 `comparison.csv`

One row per (scenario × strategy): the cell means of 17 headline metrics, plus
`d_<metric>_vs_S1` (paired difference) and `ci_<metric>_vs_S1` (`[low,high]`).
This is the table the slides are built from.

---

## 3. Wiring Modules 3–5

`module6/run_module6.py` expects one directory that contains the three checkouts
and then puts them on `sys.path` in this priority order:

1. `Module5/vendor/` — the reviewed engine patch + `m4rank` + `module4_rank.py`
2. `Module5/` — `module5_funding.py`
3. `Module4/` — `module4_rank.py`
4. `Module3/` — original `m3engine`, used only if the vendor copy is absent

Environment variables it sets: `M3_MODULE4_MODULE=module4_rank`,
`M3_MODULE5_MODULE=module5_funding`.

The loader prints the file it actually imported:

```
engine loaded from: .../Module5/vendor/m3engine/__init__.py
```

If that line points at Module 3, S3/S4 are running on a fallback and the results
must not be reported — the runner will list those runs explicitly.

---

## 4. Upstream versions

| Module | Version used |
|---|---|
| Module 3 | commit `ea57cc82c01c86a1bd02aeae7247af4644a6df81` |
| Module 4 | commit `191bffd56a656544fa52a659d02652b42498fe80` |
| Module 5 | reviewed delivery dated 2026-11-16 (`docs/VALIDATION.md` there); git tree `5492a17c6b570a42a509934daefb1e835d576ffc` |

Module 5's copy of the engine carries a reviewed patch; the two revisions differ
in funding-review scheduling and duplicate-FX prevention, which shifts S0–S2 delay
metrics by 2–5 s. That difference is measured and documented in
`docs/VALIDATION.md`.

---

## 4b. Reconciling a number before quoting it

```powershell
python module6/reconcile.py --repos <dir> --out evidence --csv-check 7
```

Runs the matrix again and compares every computed quantity with the engine's own
counter, 14 checks per run. A single `FAIL` in `evidence/reconciliation.csv` means
the table and the engine disagree for that run, and the number must not be quoted
until it is explained. Two such disagreements were found and fixed during the
mid-term work; both are documented in `docs/VALIDATION.md` section 3b.

## 5. Reproducing the reported tables

```powershell
python module6/run_module6.py --repos <dir with module3/4/5> --out module6_out
python module6/make_figures.py --metrics module6_out/metrics.csv --out figures
```

Runtime: 1–3 minutes for 1,050 runs on a laptop CPU; memory is flat because only
the metric rows are retained.

---

## 6. Known gaps handed to whoever owns Module 6 next

1. `fx_counterparty_capacity_mode` should be switched to `cumulative` (or HKD cut)
   so that "FX cannot be executed" becomes observable — otherwise S3/S4 are tested
   on a stage where their mechanism cannot matter.
2. Two stress scenarios are missing from the fixture set (urgent-payment shock,
   higher FX fees/delays).
3. The initial-funding scan must be re-derived below the 6 m baseline (0.5–6 m).
4. `weight_funding = 1.0` sensitivity should be promoted from optional to
   required: Module 4's own analysis shows it is the only lever that improves
   fairness and urgent delay at the same time.
