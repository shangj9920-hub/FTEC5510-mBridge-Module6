# -*- coding: utf-8 -*-
"""``calculate_metrics`` — the interface fixed in the team specification.

    Interface: calculate_metrics(payment_results, events, balances, config)
    Output:    one standardised metrics row for one run

This entry point deliberately does **not** import the simulation engine. It works
from the delivered result tables alone, so it can be used

  * by Module 3 in a smoke test of its own output,
  * by Module 1 to re-check a number quoted in the slides,
  * by CI, and
  * on a saved run that is copied somewhere without the engine.

Inputs may be CSV paths or already-loaded lists of dicts. Missing tables do not
raise: the affected measures become ``None`` and a note is added to
``result["warnings"]``.
"""
from __future__ import annotations

import csv
import os

from .core import PRIORITIES, block_metrics, fnum, liquidity_hours, opt_int


def _rows(source):
    """Accept a CSV path, a list of dicts, or None."""
    if source is None:
        return None
    if isinstance(source, (str, bytes, os.PathLike)):
        if not os.path.exists(source):
            return None
        with open(source, encoding="utf-8-sig", newline="") as fh:
            return list(csv.DictReader(fh))
    return list(source)


def _observation_end(config: dict, balances, payments) -> tuple:
    """Observation endpoint, in the order agreed with Module 3.

    ``observation_end_sec`` (engine summary) > ``simulation_window_sec`` +
    ``observation_drain_sec`` > last balance timestamp > latest deadline.
    """
    cfg = config or {}
    for key in ("observation_end_sec", "simulation_end_time", "observation_end_time"):
        if cfg.get(key) is not None:
            return int(cfg[key]), f"config.{key}"
    if cfg.get("simulation_window_sec") is not None:
        drain = (cfg.get("engine_parameters") or {}).get(
            "observation_drain_sec", cfg.get("observation_drain_sec", 0))
        return int(cfg["simulation_window_sec"]) + int(drain or 0), "simulation_window_sec"

    times = [opt_int(b.get("time")) for b in (balances or [])]
    times = [t for t in times if t is not None]
    if times:
        return max(times), "balances.time(max)"
    deadlines = [opt_int(p.get("deadline_time")) for p in (payments or [])]
    deadlines = [d for d in deadlines if d is not None]
    if deadlines:
        return max(deadlines), "payments.deadline_time(max)"
    return 0, "unknown"


def calculate_metrics(payment_results, events=None, balances=None, config=None,
                      fx_trades=None) -> dict:
    """Return one standardised metrics row for one run.

    ``fx_trades`` is Module 3's supplementary FX table; without it the FX cost
    falls back to ``config`` rates and a warning is recorded.
    """
    warnings = []
    payments = _rows(payment_results)
    balances = _rows(balances)
    events = _rows(events)
    fx = _rows(fx_trades)

    if not payments:
        return {"warnings": "payment_results is missing or empty"}

    obs_end, source = _observation_end(config or {}, balances, payments)
    out = {"obs_end_sec": obs_end}

    out.update({("ALL." + k): v for k, v in block_metrics(payments, obs_end).items()})
    for label in PRIORITIES:
        sub = [p for p in payments if (p.get("priority") or "").strip().upper() == label]
        out.update({(label + "." + k): v for k, v in block_metrics(sub, obs_end).items()})

    if balances:
        rmb_hours, hkd_hours = liquidity_hours(balances)
        out["rmb_liquidity_hours"] = rmb_hours
        out["hkd_liquidity_hours"] = hkd_hours
    else:
        out["rmb_liquidity_hours"] = None
        out["hkd_liquidity_hours"] = None
        warnings.append("balances is missing: liquidity hours not computed")

    cfg = config or {}
    if fx:
        done = [t for t in fx if str(t.get("status")).upper() == "COMPLETED"]
        failed = [t for t in fx if str(t.get("status")).upper() == "FAILED"]
        out["fx_initiated"] = len(fx)
        out["fx_completed"] = len(done)
        out["fx_infeasible"] = len(failed)
        # The fee is committed at initiation (the HKD is already committed), so
        # count every initiated trade, matching run_summary.fx_cost_rmb; completed
        out["fx_cost_rmb"] = sum(fnum(t.get("total_cost_rmb")) for t in fx)
        out["fx_failure_fee_rmb"] = sum(fnum(t.get("failure_fee_rmb")) for t in failed)
        out["fx_rmb_obtained"] = sum(fnum(t.get("topup_rmb")) for t in done)
        out["fx_hkd_principal"] = sum(fnum(t.get("hkd_principal")) for t in done)
    else:
        actions = [str(e.get("action", "")).upper() for e in (events or [])]
        out["fx_initiated"] = actions.count("TOP_UP") or None
        out["fx_cost_rmb"] = None
        out["fx_completed"] = None
        out["fx_infeasible"] = None
        out["fx_failure_fee_rmb"] = None
        out["fx_rmb_obtained"] = None
        out["fx_hkd_principal"] = None
        warnings.append("fx_trades is missing: FX cost and principal not computed")

    if str(obs_end) == "0":
        warnings.append("observation endpoint could not be derived from the inputs")
    out["warnings"] = "; ".join(warnings + [f"observation_end from {source}"])
    return out
