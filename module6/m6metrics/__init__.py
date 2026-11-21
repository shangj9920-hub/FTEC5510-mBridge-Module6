# -*- coding: utf-8 -*-
"""m6metrics — Module 6 metric set (pure standard library).

Public API
----------
calculate_metrics(payment_results, events, balances, config, fx_trades=None)
    One standardised metrics row for one run, from the delivered tables only.
measure(result)
    Same metrics computed from a live ``m3engine`` result object.
block_metrics(payments, obs_end), liquidity_hours(balances)
    The individual pieces, for reuse in a report or a notebook.
paired_diffs(records, key, a, b), ci95(diffs), mean_of(records, ...)
    Paired statistics used for the strategy comparison.

Nothing here imports pandas, numpy or matplotlib, matching the team convention
that every module is standard-library only.
"""
from .api import calculate_metrics
from .core import (
    PRIORITIES,
    block_metrics,
    fnum,
    liquidity_hours,
    measure,
    opt_int,
    p95,
    pctl,
)
from .stats import ci95, mean_of, paired_diffs

__all__ = [
    "calculate_metrics",
    "measure",
    "block_metrics",
    "liquidity_hours",
    "p95",
    "pctl",
    "fnum",
    "opt_int",
    "PRIORITIES",
    "paired_diffs",
    "ci95",
    "mean_of",
]
