# -*- coding: utf-8 -*-
"""Statistics helpers: paired comparison and confidence intervals.

The paired design is the one the proposal asks for (section 4.5): strategies are
compared *within the same seed*, so the only difference between two runs is the
strategy. ``paired_diffs`` therefore keys on ``(scenario_id, seed)``; using two
independent samples would inflate the variance and is not used anywhere here.
"""
from __future__ import annotations

import math
import statistics


def ci95(diffs: list) -> tuple:
    """(mean, low, high) with a normal-approximation 95% interval.

    With n = 30 paired seeds the normal approximation and the t-distribution
    differ in the third decimal; the interval is reported as an indication of
    stability, not as a formal test.
    """
    n = len(diffs)
    if n == 0:
        raise ValueError("ci95() needs at least one paired difference")
    mean = sum(diffs) / n
    if n < 2:
        return mean, mean, mean
    half = 1.96 * statistics.stdev(diffs) / math.sqrt(n)
    return mean, mean - half, mean + half


def paired_diffs(records: list, key: str, a: str, b: str,
                 scenario: str | None = None) -> list:
    """Paired differences of ``key`` between strategy ``a`` and strategy ``b``.

    ``records`` is the list of per-run metric dicts (as written to metrics.csv).
    Returns one difference per seed; seeds where either side is missing are
    skipped rather than imputed.
    """
    by_seed: dict = {}
    for r in records:
        if scenario is not None and r.get("scenario_id") != scenario:
            continue
        by_seed.setdefault((r.get("scenario_id"), r.get("seed")), {})[r.get("strategy_id")] = r.get(key)

    diffs = []
    for _key, d in by_seed.items():
        va, vb = d.get(a), d.get(b)
        if va is None or vb is None:
            continue
        diffs.append(va - vb)
    return diffs


def mean_of(records: list, scenario: str, strategy: str, key: str):
    """Mean of ``key`` over the seeds of one (scenario, strategy) cell."""
    vals = [r.get(key) for r in records
            if r.get("scenario_id") == scenario and r.get("strategy_id") == strategy]
    vals = [v for v in vals if v is not None]
    return statistics.mean(vals) if vals else None
