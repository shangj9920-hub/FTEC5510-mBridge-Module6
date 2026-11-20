# Metric specification (Module 6)

This file is the authoritative definition of every number Module 6 reports. It
also records the two decisions Module 3's README explicitly left to Module 6.

---

## 1. Source data

| Table | Producer | Used for |
|---|---|---|
| `payment_results.csv` | Module 3 | completion, delay, overdue, outstanding |
| `balances.csv` | Module 3 | RMB / HKD liquidity hours |
| `events.csv` | Module 3 | fallback FX action counts, audit trail |
| `fx_trades.csv` | Module 3 (supplementary) | FX count, principal, economic cost |
| `config.json` | Module 2 | observation window, rates, seeds, scenario id |

Column names are fixed by the team specification and are not aliased.

---

## 2. Definitions

Let `T_end = observation_end_sec` (Module 3's summary; derived from
`simulation_window_sec + engine_parameters.observation_drain_sec` when absent).

| # | Metric | Definition | Notes |
|---|---|---|---|
| 1 | Completion rate | `#{final_status = SETTLED} / #payments` | denominator includes payments still queued at `T_end` |
| 2 | Settlement delay | `settle_time − arrival_time`, **settled payments only** | mean and P95; P95 by linear interpolation at position `(n−1)·0.95` |
| 3 | Deadline breach (overdue) rate | numerator: payments with `deadline_time ≤ T_end` that are **not settled** or settled **after** the deadline; denominator: `#{deadline_time ≤ T_end}` | overdue outstanding payments are counted, as required by the work split |
| 4 | Outstanding | count and `amount_rmb` of payments not settled at `T_end` | reported next to delay, never instead of it |
| 5 | RMB / HKD liquidity hours | trapezoidal integral of `rmb_total` / `hkd_total` over event time ÷ 3600 | `rmb_total` already contains reserve and locks, so nothing is double counted; RMB and HKD are reported separately |
| 6 | FX economic cost (RMB) | Σ `total_cost_rmb` over **all initiated trades** (a trade's fee is committed at initiation, so a trade still pending at `T_end` has already incurred it); `fx_completed` reports how many settled | exchange **principal** is excluded and reported separately as `fx_hkd_principal`, which counts **completed** trades only (funds actually received) |
| 7 | FX failure fee | Σ `failure_fee_rmb` | reported separately from economic cost |

Rules that follow from the work split:

* blank `submit_time` / `settle_time` stay blank; they are never coerced to 0, so
  "not yet submitted" cannot be mistaken for "submitted at t = 0";
* delay is only ever computed on settled payments, and is always printed next to
  completion and outstanding counts;
* a payment whose deadline has not yet passed at `T_end` is **not** late.

---

## 3. Decisions Module 6 had to make

### 3.1 `eligible = false` payments

Module 3's README asks whether ineligible payments belong in the completion-rate
denominator and in the breach-rate numerator.

**Decision: exclude them from both, and report them in their own column
(`ineligible`).** Rationale: eligibility is a property of the instruction, not of
the policy under test; including them would dilute every strategy equally and
hide differences between policies.

**Impact on the reported results: none.** All 210 delivered datasets have
`eligible_probability = 1.0` and the engine reports `ineligible = 0` in all 1,050
runs, so the two conventions give identical numbers. The rule is recorded here for
future datasets that do contain ineligible instructions.

### 3.2 `fx_counterparty_capacity_rmb` semantics

The engine defaults to `per_trade` (a ceiling on one trade). **Module 6 keeps the
default for the reported run but flags the consequence**: with `per_trade`,
counterparty capacity can never be exhausted, so "FX cannot be executed" never
occurs, and scenario 6 (`fx_capacity_shock`) only changes trade size limits.
A `cumulative` run is required before S3/S4 can be evaluated on their intended
stage; it is listed as a next step, not presented as a result.

---

### 3.3 FX cost: initiated or completed only?

The engine books the fee when a trade is initiated (the HKD fee is committed at
that moment) and its `run_summary.fx_cost_rmb` therefore covers **initiated**
trades. Module 6 follows the engine; otherwise the CSV path and the engine path
would disagree on any run that ends with a trade still pending — which happens in
195 of the 1,050 runs.

`fx_rmb_obtained` and `fx_hkd_principal` deliberately stay on **completed** trades:
they describe liquidity actually received, not a commitment.

Scope note: the batch table (`evidence/metrics.csv`) takes `fx_cost_rmb` straight
from the engine summary, so the published figures were already on this basis. The
clarification above aligns the **standalone CSV path** (`calculate_metrics`, used by
anyone recomputing a run from the four tables) with the engine. Re-running the whole
matrix after the change produced a `metrics.csv` identical to the previous one.

## 4. Aggregation and inference

* Every cell in a table is the mean over 30 formal seeds (`20001–20030`).
* Strategy differences are **paired by seed**: within one seed all five strategies
  share the same payment arrivals, inflow stream, FX conditions and confirmation
  delays, so the only difference is the policy.
* Intervals are `mean ± 1.96 · sd / √n` over the 30 paired differences. This is a
  stability indicator, not a formal hypothesis test; with n = 30 the normal and t
  approximations differ in the third decimal.
* Improvement rates are only computed where the S1 reference is non-zero.

---

## 5. Reproducing a single number

```powershell
python module6/calculate_metrics.py --run-dir <run dir> `
  --meta '{"run_id":"baseline_seed20001_S2","scenario_id":"baseline","seed":20001,"strategy_id":"S2"}'
```

The row it prints is exactly the row that appears in `evidence/metrics.csv` for
that run, and `evidence/metrics.csv` is what both figures are drawn from.
