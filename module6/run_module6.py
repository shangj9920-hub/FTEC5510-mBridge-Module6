#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Module 6 -- experiment runs and metric calculation (standard library only).

Design rules, kept identical to Modules 3-5:

* no pandas / numpy; the standard library only;
* metric definitions are a direct re-implementation of ``measure()`` in Module 4's
  ``analysis/check_alignment.py``, so the two modules cannot drift apart and the
  report never contains two versions of the same number;
* the engine is called in-process through ``m3engine.load_dataset / run_dataset``
  (an order of magnitude faster than the CLI), one dataset load per
  (scenario, seed) shared by all five strategies;
* every run is checked for ``using_fallback_module4 / using_fallback_module5``;
  a single ``true`` disqualifies the numbers for the report.

This file covers steps 1-4 of the Module 6 work split: fixed-case check, batch
run, metric calculation, comparison table with 95% confidence intervals.

Usage (run from the repository root):

    # 0) smoke test: 1 scenario x 2 seeds x 5 strategies, about 10 s
    python module6/run_module6.py --repos <dir> --smoke

    # 1) full matrix: 7 scenarios x 30 formal seeds x 5 strategies = 1050 runs
    python module6/run_module6.py --repos <dir> --out module6_out

    # 2) pilot seeds only (7 x 3 = 21 datasets, 105 runs)
    python module6/run_module6.py --repos <dir> --seed-set pilot

Outputs (default ``module6_out/``):

    metrics.csv      one row per run (run_id, scenario, seed, strategy + metrics)
    comparison.csv   one row per scenario x strategy (mean, paired difference, CI)
    run_log.txt      full console record of this run
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
import sys
from pathlib import Path

import bisect

# --------------------------------------------------------------------------- #
# Constants matching the delivered repository layout
# --------------------------------------------------------------------------- #
SCENARIOS = [
    "baseline",            # 0 normal
    "low_rmb_liquidity",   # 1 low RMB liquidity
    "payment_surge",       # 2 concentrated arrivals
    "tight_deadlines",     # 3 tight deadlines
    "large_payments",      # 4 large payments
    "delayed_inflows",     # 5 delayed inflows
    "fx_capacity_shock",   # 6 FX capacity shock
]
SEED_SETS = {"formal": list(range(20001, 20031)), "pilot": [1001, 1002, 1003]}

#: (scenario, seed) pairs whose time series are exported for the appendix figures
SERIES_TARGETS = {("baseline", 20001), ("payment_surge", 20001)}
STRATEGIES = ["S0", "S1", "S2", "S3", "S4"]

#: Published Module 4 values, used to prove the metric definitions agree
EXPECTED = {
    # scenario: (metric, strategy a, strategy b, expected mean difference)
    "baseline": ("URGENT.mean_delay", "S2", "S1", -11.1),
    "low_rmb_liquidity": ("URGENT.mean_delay", "S2", "S1", -24.1),
    "payment_surge": ("NORMAL.completion", "S2", "S1", -0.048),
    "large_payments": ("NORMAL.completion", "S2", "S1", -0.062),
}
TOLERANCE = {"URGENT.mean_delay": 0.6, "NORMAL.completion": 0.004}


# --------------------------------------------------------------------------- #
# Dependency: metrics and statistics live in m6metrics; this script only schedules
# --------------------------------------------------------------------------- #
from m6metrics import (  # noqa: E402
    PRIORITIES, block_metrics, ci95, fnum, liquidity_hours, mean_of, measure,
    opt_int, paired_diffs, p95,
)


# --------------------------------------------------------------------------- #
# Locate the three repositories under --repos
# --------------------------------------------------------------------------- #
def find_repos(root: Path) -> dict:
    """Return {'engine': .., 'module4': .., 'module5': .., 'fixtures': ..}"""
    root = root.resolve()
    engine_candidates, node4, node5 = [], None, None
    for p in root.rglob("__init__.py"):
        if p.parent.name == "m3engine":
            engine_candidates.append(p.parent.parent)   # module3/ or vendor/
    for p in root.rglob("module4_rank.py"):
        node4 = p.parent
    for p in root.rglob("module5_funding.py"):
        node5 = p.parent

    # Prefer module3/ at the repository root (the real fixture source) over the vendor copy
    engine = None
    for cand in engine_candidates:
        if (cand / "fixtures").is_dir() or cand.name == "module3":
            engine = cand
            break
    if engine is None and engine_candidates:
        engine = engine_candidates[0]

    if engine is None:
        raise SystemExit(
            f"[x] no m3engine/ found under {root} (module3 repository)\n"
            "    make sure the three repositories are cloned there, with module3/ inside")
    if node4 is None or node5 is None:
        raise SystemExit(
            f"[x] module4_rank.py or module5_funding.py not found\n"
            f"    module4={node4}  module5={node5}")

    # Prefer Module 5's vendor/m3engine (it carries the reviewed patch S3/S4 need),
    # otherwise fall back to Module 3's own engine (S3/S4 then use fallbacks and are flagged).
    patched = None
    for p in root.rglob("m3engine"):
        if p.is_dir() and (p.parent / "module4_rank.py").exists() or \
           (p.is_dir() and p.parent.name == "vendor"):
            patched = p.parent
            break

    fixtures = engine / "fixtures" / "formal"
    if not fixtures.is_dir():
        alt = [p for p in root.rglob("fixtures") if (p / "formal").is_dir()]
        fixtures = (alt[0] / "formal") if alt else fixtures

    return {"engine": engine, "module4": node4, "module5": node5,
            "patched": patched, "fixtures": fixtures}


def setup_paths(repos: dict) -> None:
    # Priority: patched engine (vendor) > module5 > module4 > original module3
    # reversed + insert(0) keeps the list order equal to the priority order
    order = [repos.get("patched"), repos["module5"], repos["module4"], repos["engine"]]
    for p in reversed([p for p in order if p]):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    os.environ.setdefault("M3_MODULE4_MODULE", "module4_rank")
    os.environ.setdefault("M3_MODULE5_MODULE", "module5_funding")
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


# Batch run
# --------------------------------------------------------------------------- #
def run_matrix(repos: dict, scenarios, seeds, strategies, limit=None, log=print):
    setup_paths(repos)
    try:
        from m3engine import load_dataset, run_dataset  # noqa: PLC0415
    except Exception as exc:                          # noqa: BLE001
        raise SystemExit(
            "[x] cannot import m3engine: %r\n"
            "    check that --repos contains module3/ and that Python is 3.10 or newer" % (exc,))

    fixtures = repos["fixtures"]
    records = []
    series = []
    total = len(scenarios) * len(seeds) * len(strategies)
    done = 0
    fallback_runs = []
    import m3engine                                  # noqa: PLC0415
    log(f"  engine loaded from: {m3engine.__file__}")

    for scenario in scenarios:
        for seed in seeds:
            dataset_dir = fixtures / scenario / f"seed_{seed}"
            if not dataset_dir.is_dir():
                log(f"  ! missing dataset {dataset_dir}, skipped")
                continue
            dataset = load_dataset(dataset_dir)
            for strategy in strategies:
                try:
                    result = run_dataset(dataset, strategy)
                except Exception as exc:              # noqa: BLE001
                    log(f"  ! {scenario} seed{seed} {strategy} failed: {exc!r}")
                    continue
                m = measure(result)
                m.update({"run_id": f"{scenario}_seed{seed}_{strategy}",
                          "scenario_id": scenario, "seed": seed,
                          "strategy_id": strategy})
                records.append(m)
                if (scenario, seed) in SERIES_TARGETS:
                    series.extend(series_rows(result, scenario, seed, strategy))
                if m["using_fallback_m4"] or m["using_fallback_m5"]:
                    fallback_runs.append(m["run_id"])
                done += 1
                if limit and done >= limit:
                    return records, fallback_runs, series
        log(f"  [{scenario}] {len(strategies) * len(seeds)} runs done, "
            f"{done}/{total} cumulative")
    return records, fallback_runs, series



def series_rows(result, scenario, seed, strategy):
    """Queue length and balance paths on the balance-snapshot time grid.

    Queue length = payments that have arrived and are not settled yet (ineligible
    ones excluded). This is what the proposal's queue-length chart plots.
    """
    payments = result.payments
    arrivals = sorted(int(float(r["arrival_time"])) for r in payments
                      if str(r.get("final_status")).upper() != "INELIGIBLE")
    settles = sorted(int(float(r["settle_time"])) for r in payments
                     if r.get("final_status") == "SETTLED"
                     and opt_int(r.get("settle_time")) is not None)
    out = []
    for b in result.balances:
        t = int(b["time"])
        out.append({"run_id": f"{scenario}_seed{seed}_{strategy}",
                    "scenario_id": scenario, "seed": seed, "strategy_id": strategy,
                    "time": t,
                    "queue_len": bisect.bisect_right(arrivals, t) - bisect.bisect_right(settles, t),
                    "rmb_total": fnum(b.get("rmb_total")),
                    "rmb_available": fnum(b.get("rmb_available")),
                    "hkd_total": fnum(b.get("hkd_total"))})
    return out


# --------------------------------------------------------------------------- #
# Aggregation and printing
# --------------------------------------------------------------------------- #
METRIC_COLUMNS = ["run_id", "scenario_id", "seed", "strategy_id", "n_payments",
                  "ALL.n", "ALL.settled", "ALL.completion", "ALL.outstanding",
                  "ALL.outstanding_amount_rmb", "ALL.mean_delay", "ALL.p95_delay",
                  "ALL.due", "ALL.overdue", "ALL.overdue_rate",
                  "ALL.p50_delay", "ALL.p90_delay", "ALL.p99_delay",
                  "ALL.max_queue_s", "ALL.mean_queue_s", "ALL.outstanding_share",
                  "URGENT.completion", "URGENT.mean_delay", "URGENT.p95_delay",
                  "URGENT.overdue_rate", "URGENT.p50_delay", "URGENT.p90_delay",
                  "URGENT.p99_delay",
                  "HIGH.completion", "HIGH.mean_delay", "HIGH.p95_delay", "HIGH.overdue_rate",
                  "NORMAL.completion", "NORMAL.mean_delay", "NORMAL.p95_delay",
                  "NORMAL.overdue_rate", "NORMAL.p50_delay", "NORMAL.p90_delay",
                  "NORMAL.p99_delay", "NORMAL.max_queue_s",
                  "rmb_liquidity_hours", "hkd_liquidity_hours",
                  "fx_initiated", "fx_completed", "fx_infeasible", "fx_cost_rmb",
                  "fx_rmb_obtained", "fx_hkd_principal",
                  "ineligible", "obs_end_sec", "using_fallback_m4", "using_fallback_m5"]


def write_metrics(path: Path, records: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=METRIC_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for r in sorted(records, key=lambda x: (x["scenario_id"], x["seed"], x["strategy_id"])):
            row = {}
            for k in METRIC_COLUMNS:
                v = r.get(k)
                row[k] = "" if v is None else (round(v, 6) if isinstance(v, float) else v)
            writer.writerow(row)


def paired(records, scenario, key, a, b):
    """Paired differences within a seed; see m6metrics.stats.paired_diffs."""
    return paired_diffs(records, key, a, b, scenario=scenario)


def fmt(v, nd=1, suffix=""):
    if v is None:
        return "-"
    return f"{v:,.{nd}f}{suffix}"


def print_tables(records, log=print):
    """Table headers are kept ASCII so any Windows code page can display them."""
    scen_present = sorted({r["scenario_id"] for r in records},
                          key=lambda s: SCENARIOS.index(s) if s in SCENARIOS else 99)
    strats = [s for s in STRATEGIES if any(r["strategy_id"] == s for r in records)]

    log("\n" + "=" * 100)
    log("TABLE 1  overall service (mean over seeds)")
    log("=" * 100)
    log(f"{'scenario':22s}{'strategy':10s}{'completion':>12s}{'overdue':>10s}"
        f"{'P95(s)':>10s}{'mean(s)':>10s}{'RMB hrs':>12s}")
    for sc in scen_present:
        for st in strats:
            c = mean_of(records, sc, st, "ALL.completion")
            od = mean_of(records, sc, st, "ALL.overdue_rate")
            p95 = mean_of(records, sc, st, "ALL.p95_delay")
            md = mean_of(records, sc, st, "ALL.mean_delay")
            lh = mean_of(records, sc, st, "rmb_liquidity_hours")
            log(f"{sc:22s}{st:10s}{fmt(c,3):>12s}{fmt(od,3):>10s}"
                f"{fmt(p95,0):>10s}{fmt(md,0):>10s}{fmt(lh,0):>12s}")

    log("\n" + "=" * 100)
    log("TABLE 2  completion by priority, S1 -> S2  (* = 95% CI excludes 0)")
    log("=" * 100)
    log(f"{'scenario':22s}{'URGENT':>20s}{'HIGH':>20s}{'NORMAL':>20s}")
    for sc in scen_present:
        cells = []
        for label in PRIORITIES:
            c1 = mean_of(records, sc, "S1", f"{label}.completion")
            c2 = mean_of(records, sc, "S2", f"{label}.completion")
            d = paired(records, sc, f"{label}.completion", "S2", "S1")
            star = ""
            if d and len(d) >= 3:
                _, low, high = ci95(d)
                star = "*" if (low > 0 or high < 0) else " "
            cells.append(f"{fmt(c1,3)}->{fmt(c2,3)}{star}")
        log(f"{sc:22s}{cells[0]:>20s}{cells[1]:>20s}{cells[2]:>20s}")

    log("\n" + "=" * 100)
    log("TABLE 3  paired differences S2 vs S1 (same seed), mean  (* = CI excludes 0)")
    log("=" * 100)
    log(f"{'metric':26s}" + "".join(f"{sc[:12]:>14s}" for sc in scen_present))
    for key, scale, nd in (("URGENT.mean_delay", 1, 1), ("URGENT.p95_delay", 1, 1),
                           ("NORMAL.completion", 100, 2), ("NORMAL.overdue_rate", 100, 2),
                           ("ALL.completion", 100, 2), ("fx_initiated", 1, 1)):
        cells = []
        for sc in scen_present:
            d = paired(records, sc, key, "S2", "S1")
            if not d:
                cells.append("-")
                continue
            m, low, high = ci95(d)
            mark = "*" if (low > 0 or high < 0) else ""
            cells.append(f"{m*scale:+.{nd}f}{mark}")
        log(f"{key:26s}" + "".join(f"{c:>14s}" for c in cells))

    log("\n" + "=" * 100)
    log("TABLE 4  other contrasts (delay in s, completion in pp)")
    log("=" * 100)
    for key in ("fx_initiated", "ALL.completion", "ALL.mean_delay"):
        for a, b in (("S1", "S0"), ("S3", "S1"), ("S4", "S1"), ("S4", "S2"), ("S4", "S3")):
            if a not in strats or b not in strats:
                continue
            cells = []
            for sc in scen_present:
                d = paired(records, sc, key, a, b)
                if not d:
                    cells.append("-")
                    continue
                m, low, high = ci95(d)
                mark = "*" if (low > 0 or high < 0) else ""
                scale = 100 if "completion" in key else 1
                nd = 2 if scale == 100 else 1
                cells.append(f"{m*scale:+.{nd}f}{mark}")
            log(f"{key:18s}{a}v{b:6s}" + "".join(f"{c:>12s}" for c in cells))

    log("\n" + "=" * 100)
    log("TABLE 5  resources and FX cost (mean)")
    log("=" * 100)
    log(f"{'scenario':22s}{'strategy':9s}{'RMB hrs':>12s}{'HKD hrs':>13s}"
        f"{'FX cnt':>8s}{'FX cost':>10s}{'FX RMB':>13s}")
    for sc in scen_present:
        for st in strats:
            log(f"{sc:22s}{st:9s}"
                f"{fmt(mean_of(records,sc,st,'rmb_liquidity_hours'),0):>12s}"
                f"{fmt(mean_of(records,sc,st,'hkd_liquidity_hours'),0):>13s}"
                f"{fmt(mean_of(records,sc,st,'fx_initiated'),1):>8s}"
                f"{fmt(mean_of(records,sc,st,'fx_cost_rmb'),1):>10s}"
                f"{fmt(mean_of(records,sc,st,'fx_rmb_obtained'),0):>13s}")


def validate_against_module4(records, log=print) -> bool:
    """Three-level verdict:
    MATCH         the value is inside the tolerance (same engine, identical definition)
    DIRECTION-OK  same sign and the 95% CI excludes 0 (engine revision shifts the level)
    DIFF          opposite sign, or no longer significant -- not usable
    """
    log("\n" + "=" * 100)
    log("VALIDATION  does my pipeline reproduce Module 4's published numbers?")
    log("=" * 100)
    ok = True
    for scenario, (key, a, b, expected) in EXPECTED.items():
        d = paired(records, scenario, key, a, b)
        if not d:
            log(f"  SKIP        {scenario} {key} (scenario not in this run)")
            continue
        m, low, high = ci95(d)
        tol = TOLERANCE.get(key.split(".")[-1], 0.01)
        significant = (low > 0 or high < 0)
        if abs(m - expected) <= tol:
            verdict = "MATCH      "
        elif significant and (m > 0) == (expected > 0):
            verdict = "DIRECTION-OK"
        else:
            verdict = "DIFF       "
            ok = False
        log(f"  {verdict} {scenario:20s}{key:18s}{a}-{b} = {m:+.4f}  "
            f"[CI {low:+.4f},{high:+.4f}]  M4 doc {expected:+.4f}")
    log("  RESULT: " + ("PASS" if ok else "MISMATCH - do not use these numbers yet"))
    return ok


#: metrics for which the proposal's improvement rate is reported, and its direction
IMPROVE = [("ALL.completion", +1), ("ALL.mean_delay", -1), ("ALL.p95_delay", -1),
           ("ALL.overdue_rate", -1), ("URGENT.mean_delay", -1),
           ("NORMAL.completion", +1), ("NORMAL.max_queue_s", -1),
           ("fx_cost_rmb", -1), ("rmb_liquidity_hours", -1)]


def improvement(records, scenario, strategy, key, sign):
    """Proposal 4.5: (baseline - treatment) / baseline for lower-is-better metrics,
    reversed when higher is better. Positive always means an improvement."""
    base = mean_of(records, scenario, "S1", key)
    value = mean_of(records, scenario, strategy, key)
    if base in (None, 0) or value is None:
        return None
    return sign * (value - base) / base


def write_comparison(path: Path, records: list) -> None:
    """One row per scenario x strategy: cell means plus the paired difference vs S1."""
    keys = ["ALL.completion", "ALL.overdue_rate", "ALL.mean_delay", "ALL.p95_delay",
            "ALL.outstanding", "ALL.outstanding_amount_rmb",
            "URGENT.completion", "URGENT.mean_delay", "URGENT.p95_delay",
            "NORMAL.completion", "NORMAL.mean_delay", "NORMAL.p95_delay",
            "NORMAL.overdue_rate", "rmb_liquidity_hours", "hkd_liquidity_hours",
            "fx_initiated", "fx_cost_rmb"]
    header = ["scenario_id", "strategy_id", "n_seeds"] + keys
    for k in keys:
        header += [f"d_{k}_vs_S1", f"ci_{k}_vs_S1"]
    header += [f"impr_{k}_vs_S1" for k, _sign in IMPROVE]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        for sc in sorted({r["scenario_id"] for r in records}):
            for st in STRATEGIES:
                row = [sc, st, len({r["seed"] for r in records
                                    if r["scenario_id"] == sc and r["strategy_id"] == st})]
                for k in keys:
                    v = mean_of(records, sc, st, k)
                    row.append("" if v is None else round(v, 6))
                for k in keys:
                    d = paired(records, sc, k, st, "S1") if st != "S1" else None
                    if not d:
                        row += ["", ""]
                    else:
                        m, low, high = ci95(d)
                        row += [round(m, 6), f"[{low:.4f},{high:.4f}]"]
                for k, sign in IMPROVE:
                    v = improvement(records, sc, st, k, sign)
                    row.append("" if v is None else round(v, 6))
                w.writerow(row)


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
CONTRAST_KEYS = [
    ("ALL.completion", "pp", 100),
    ("ALL.mean_delay", "s", 1),
    ("ALL.p95_delay", "s", 1),
    ("URGENT.mean_delay", "s", 1),
    ("NORMAL.completion", "pp", 100),
    ("fx_initiated", "trades", 1),
    ("fx_cost_rmb", "RMB", 1),
    ("rmb_liquidity_hours", "M-hours", 1e-6),
]
#: proposal 4.3 -- comparing S4 with S2 and S3 isolates the incremental effect of
#: adding the other mechanism. S4-S2 = value of waiting on top of ordering;
#: S4-S3 = value of ordering on top of waiting.
CONTRASTS = [("S4", "S2"), ("S4", "S3")]


def write_contrasts(path: Path, records: list) -> None:
    """One row per (scenario, contrast, metric) with a paired 95% CI."""
    path.parent.mkdir(parents=True, exist_ok=True)
    header = ["scenario_id", "contrast", "metric", "unit", "n_seeds",
              "mean", "ci_low", "ci_high", "significant"]
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        for sc in sorted({r["scenario_id"] for r in records}):
            for a, b in CONTRASTS:
                for key, unit, scale in CONTRAST_KEYS:
                    d = paired(records, sc, key, a, b)
                    if not d:
                        continue
                    m, low, high = ci95(d)
                    w.writerow([sc, f"{a}-{b}", key, unit, len(d),
                                round(m * scale, 6), round(low * scale, 6),
                                round(high * scale, 6),
                                "yes" if (low > 0 or high < 0) else "no"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Module 6 batch runs and metrics")
    ap.add_argument("--repos", default="_repos", help="directory holding module3/4/5")
    ap.add_argument("--out", default="module6_out")
    ap.add_argument("--seed-set", default="formal", choices=("formal", "pilot"))
    ap.add_argument("--scenarios", default="", help="comma separated; default all seven")
    ap.add_argument("--strategies", default="S0,S1,S2,S3,S4")
    ap.add_argument("--smoke", action="store_true", help="1 scenario x 2 seeds x 5 strategies")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args(argv)

    repos = find_repos(Path(a.repos))
    scenarios = [s.strip() for s in a.scenarios.split(",") if s.strip()] or SCENARIOS
    strategies = [s.strip().upper() for s in a.strategies.split(",") if s.strip()]
    seeds = SEED_SETS[a.seed_set]
    if a.smoke:
        scenarios, seeds = scenarios[:1], seeds[:2]
        strategies = STRATEGIES[:]

    lines = []

    def log(msg=""):
        print(msg)
        lines.append(str(msg))

    log("=" * 100)
    log("Module 6 -- batch runs and metrics")
    log("=" * 100)
    log(f"engine dir : {repos['engine']}")
    log(f"module 4   : {repos['module4']}")
    log(f"module 5   : {repos['module5']}")
    log(f"patched    : {repos.get('patched') or '(no vendor/m3engine; S3/S4 may use fallback)'}")
    log(f"fixtures   : {repos['fixtures']}")
    log(f"matrix     : {len(scenarios)} scenarios x {len(seeds)} seeds x {len(strategies)} "
        f"strategies = {len(scenarios)*len(seeds)*len(strategies)} runs")

    records, fallbacks, series = run_matrix(repos, scenarios, seeds, strategies,
                                            limit=a.limit, log=log)

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    write_metrics(out / "metrics.csv", records)
    write_comparison(out / "comparison.csv", records)
    write_contrasts(out / "contrasts.csv", records)
    if series:
        with (out / "series.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(series[0]))
            w.writeheader()
            for row in series:
                w.writerow({k: (round(v, 4) if isinstance(v, float) else v)
                            for k, v in row.items()})
    log(f"\nfinished {len(records)} runs -> {out/'metrics.csv'}")
    log("  also wrote comparison.csv (vs S1) and contrasts.csv (S4-S2, S4-S3)")

    if fallbacks:
        log(f"\n[!] {len(fallbacks)} runs used a fallback module; those numbers must not "
            f"go into the report:")
        for rid in fallbacks[:10]:
            log("    " + rid)
        if len(fallbacks) > 10:
            log(f"    ... and {len(fallbacks)-10} more")
    else:
        log("\n[OK] every run has using_fallback_module4/5 == false")

    print_tables(records, log=log)
    ok = validate_against_module4(records, log=log)

    log(f"\noutputs: {out/'metrics.csv'}  {out/'comparison.csv'}")
    log("Next: module6/make_figures.py for the two figures, module6/reconcile.py "
        "for the reconciliation record.")
    (out / "run_log.txt").write_text("\n".join(lines), encoding="utf-8")
    return 0 if ok else 2


if __name__ == "__main__":
    try:                     # keep the Windows console code page from raising
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:        # noqa: BLE001
        pass
    sys.exit(main())
