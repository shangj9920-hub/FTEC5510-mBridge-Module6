# -*- coding: utf-8 -*-
"""Core metric definitions for Module 6.

These definitions are a strict re-implementation of Module 4's
``analysis/check_alignment.py::measure()`` so that the two modules cannot drift
apart. Anything Module 4 already computes is computed the same way here; Module 6
only *adds* the measures Module 4 does not report:

    * RMB / HKD liquidity hours (time-integral of the balance paths)
    * outstanding amount in RMB, outstanding share
    * FX behaviour counts and the RMB obtained / HKD principal actually traded

Measurement rules (agreed with Module 1 in ``docs/METRICS_SPEC.md``):

1. completion = payments whose ``final_status`` is ``SETTLED`` / all payments
2. delay      = ``settle_time - arrival_time`` for **settled** payments only
3. overdue    = among payments whose ``deadline_time <= observation_end_sec``:
                not settled, or settled after the deadline
4. liquidity hours = trapezoidal integral of ``rmb_total`` / ``hkd_total``
                over event time, divided by 3600 (RMB and HKD reported apart)
5. blank times stay blank; a missing time is never treated as 0
"""
from __future__ import annotations

PRIORITIES = ("URGENT", "HIGH", "NORMAL")


def fnum(value):
    """float or NaN; never raises."""
    if value is None:
        return float("nan")
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def opt_int(value):
    """Optional integer: blank -> None (never 0)."""
    if value in (None, "", "None"):
        return None
    return int(float(value))


def block_metrics(subset: list, obs_end: int) -> dict:
    """Service measures for one subset of payments (all, or one priority)."""
    settled = [r for r in subset if r.get("final_status") == "SETTLED"]

    delays = []
    for r in settled:
        st = opt_int(r.get("settle_time"))
        if st is not None:
            delays.append(st - int(float(r["arrival_time"])))

    due = [r for r in subset if int(float(r["deadline_time"])) <= obs_end]

    def is_overdue(r) -> bool:
        if r.get("final_status") != "SETTLED":
            return True
        st = opt_int(r.get("settle_time"))
        return st is not None and st > int(float(r["deadline_time"]))

    overdue = [r for r in due if is_overdue(r)]
    outstanding_amount = sum(fnum(r.get("amount_rmb")) for r in subset
                             if r.get("final_status") != "SETTLED")

    # Queue waiting time (proposal 4.5: "maximum time spent queued up to submission
    # or the observation endpoint"): submitted payments stop the clock at submission,
    # the rest are censored at the observation endpoint.
    waits = []
    for r in subset:
        submitted = opt_int(r.get("submit_time"))
        waits.append(submitted - int(float(r["arrival_time"])) if submitted is not None
                     else obs_end - int(float(r["arrival_time"])))

    return {
        "n": len(subset),
        "settled": len(settled),
        "completion": (len(settled) / len(subset)) if subset else None,
        "outstanding": len(subset) - len(settled),
        "outstanding_amount_rmb": outstanding_amount,
        "total_amount_rmb": sum(fnum(r.get("amount_rmb")) for r in subset),
        "mean_delay": (sum(delays) / len(delays)) if delays else None,
        "p50_delay": pctl(delays, 0.50),
        "p90_delay": pctl(delays, 0.90),
        "p95_delay": p95(delays),
        "p99_delay": pctl(delays, 0.99),
        "max_queue_s": max(waits) if waits else None,
        "mean_queue_s": (sum(waits) / len(waits)) if waits else None,
        "outstanding_share": (len(subset) - len(settled)) / len(subset) if subset else None,
        "due": len(due),
        "overdue": len(overdue),
        "overdue_rate": (len(overdue) / len(due)) if due else None,
    }


def pctl(values: list, q: float):
    """Arbitrary percentile with linear interpolation (same rule as p95)."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * q
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def p95(values: list):
    """95th percentile with linear interpolation (same as Module 4's pct)."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * 0.95
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def liquidity_hours(balances: list) -> tuple:
    """Trapezoidal integral of rmb_total / hkd_total over event time.

    ``balances`` is the row list of ``balances.csv`` (one snapshot per event).
    Returns ``(rmb_hours, hkd_hours)``; both balances are reported separately
    because the proposal requires RMB and HKD resource use not to be mixed.
    """
    rows = []
    for b in balances:
        t = opt_int(b.get("time"))
        if t is None:
            continue
        rows.append((t, fnum(b.get("rmb_total")), fnum(b.get("hkd_total"))))
    rows.sort(key=lambda r: r[0])

    rmb = hkd = 0.0
    for (t0, r0, h0), (t1, r1, h1) in zip(rows, rows[1:]):
        dt = t1 - t0
        if dt <= 0:
            continue
        rmb += (r0 + r1) / 2.0 * dt
        hkd += (h0 + h1) / 2.0 * dt
    return rmb / 3600.0, hkd / 3600.0


def measure(result) -> dict:
    """All Module 6 metrics for one engine result object.

    ``result`` is whatever ``m3engine.run_dataset`` returns: it exposes
    ``.summary``, ``.payments``, ``.events``, ``.balances`` and ``.fx_trades``.
    """
    summary = result.summary
    obs_end = int(summary["observation_end_sec"])
    rows = result.payments

    out = {}
    out.update({("ALL." + k): v for k, v in block_metrics(rows, obs_end).items()})
    for label in PRIORITIES:
        sub = [r for r in rows if r.get("priority") == label]
        out.update({(label + "." + k): v for k, v in block_metrics(sub, obs_end).items()})

    fx = result.fx_trades or []
    completed = [t for t in fx if str(t.get("status")).upper() == "COMPLETED"]
    out["fx_initiated"] = int(summary.get("fx_initiated", len(fx)))
    out["fx_completed"] = int(summary.get("fx_completed", len(completed)))
    out["fx_infeasible"] = int(summary.get("fx_infeasible", 0))
    out["fx_cost_rmb"] = fnum(summary.get("fx_cost_rmb"))
    out["fx_rmb_obtained"] = sum(fnum(t.get("topup_rmb")) for t in completed)
    out["fx_hkd_principal"] = sum(fnum(t.get("hkd_principal")) for t in completed)

    rmb_hours, hkd_hours = liquidity_hours(result.balances)
    out["rmb_liquidity_hours"] = rmb_hours
    out["hkd_liquidity_hours"] = hkd_hours

    # traceability: every row must say which engine/config produced it
    out["obs_end_sec"] = obs_end
    out["using_fallback_m4"] = bool(summary.get("using_fallback_module4", True))
    out["using_fallback_m5"] = bool(summary.get("using_fallback_module5", True))
    out["n_payments"] = int(summary.get("n_payments", len(rows)))
    out["ineligible"] = int(summary.get("ineligible", 0))
    return out
