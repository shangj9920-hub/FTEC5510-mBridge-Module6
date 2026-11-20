# -*- coding: utf-8 -*-
"""reconcile.py -- per-run reconciliation of computed metrics against the engine.

Why this exists
---------------
``calculate_metrics`` derives metrics from the four result tables, while the engine
reports its own counters in ``run_summary.json`` (settled / pending / queued /
ineligible / fx_* / closing balances). If the two agree, the tables have not drifted
from the engine's internal state and the metrics can be trusted. If they disagree,
either a column is being read wrongly or the engine failed to write something.

Three groups of checks per run:

A. **counts** -- payment status distribution, FX counts and FX cost, item by item
   against the engine summary.
B. **balances** -- the closing row of ``balances.csv`` against the engine summary.
C. **cash identity** (optional, needs the dataset):

       closing RMB = opening + credited inflows + FX received - settled amounts

   This is the check that catches double payments, double deductions and funds
   becoming available before settlement.

A sampled cross-check (``--csv-check N``) is also available: N runs are written to
disk and recomputed through ``calculate_metrics`` (CSV path), then compared with
``measure`` (engine-object path) -- proving the two independent code paths agree.

Usage
-----
    python module6/reconcile.py --repos <dir with module3/4/5> --out evidence

Outputs
-------
    reconciliation.csv          one row per run x check
    reconciliation_by_run.csv   one row per run, with a verdict
    reconciliation_summary.txt  human-readable summary for the delivery package
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from m6metrics import calculate_metrics, measure  # noqa: E402
from run_module6 import (  # noqa: E402
    SCENARIOS, SEED_SETS, STRATEGIES, find_repos, setup_paths,
)

TOL_MONEY = 0.05      # tolerance for cent-level rounding
STATUS_KEYS = ("SETTLED", "PENDING", "QUEUED", "INELIGIBLE", "NOT_ARRIVED")


def _last_balance_row(balances):
    """Closing snapshot.

    Several events in the same second each write a row (FX completion -> payment
    submission -> end of simulation). The engine's closing state is the **last row
    in file order**, not the first row carrying the maximum timestamp.
    """
    best = None
    for b in balances:
        if best is None or int(b["time"]) >= int(best["time"]):
            best = b
    return best


def _status_counts(payments) -> dict:
    counts = {k: 0 for k in STATUS_KEYS}
    for p in payments:
        status = str(p.get("final_status") or "").upper()
        counts[status] = counts.get(status, 0) + 1
    return counts


def _close(got, want, tol=TOL_MONEY) -> bool:
    try:
        return abs(float(got) - float(want)) <= tol
    except (TypeError, ValueError):
        return False


class Reconciler:
    def __init__(self, tolerance=TOL_MONEY):
        self.rows = []
        self.tolerance = tolerance

    def check(self, run_id, scenario, seed, strategy, name, computed, engine,
              tol=None):
        tol = self.tolerance if tol is None else tol
        if isinstance(computed, (int, float)) and isinstance(engine, (int, float)):
            delta = float(computed) - float(engine)
            ok = abs(delta) <= tol
        else:
            delta = ""
            ok = (computed == engine)
        self.rows.append({
            "run_id": run_id, "scenario_id": scenario, "seed": seed,
            "strategy_id": strategy, "check": name,
            "computed_from_tables": computed, "engine_reported": engine,
            "delta": delta if not isinstance(delta, str) else delta,
            "ok": "PASS" if ok else "FAIL",
        })
        return ok


def reconcile_run(rec: Reconciler, result, dataset, scenario, seed, strategy,
                  run_id, identity=True):
    summary = result.summary
    payments = result.payments
    balances = result.balances
    fx = result.fx_trades or []
    counts = _status_counts(payments)

    # ---- A. count reconciliation ------------------------------------------
    rec.check(run_id, scenario, seed, strategy, "n_payments",
              len(payments), int(summary.get("n_payments", -1)))
    rec.check(run_id, scenario, seed, strategy, "settled",
              counts.get("SETTLED", 0), int(summary.get("settled", -1)))
    rec.check(run_id, scenario, seed, strategy, "pending",
              counts.get("PENDING", 0), int(summary.get("pending", -1)))
    rec.check(run_id, scenario, seed, strategy, "queued",
              counts.get("QUEUED", 0), int(summary.get("queued", -1)))
    rec.check(run_id, scenario, seed, strategy, "ineligible",
              counts.get("INELIGIBLE", 0), int(summary.get("ineligible", -1)))

    known = counts.get("SETTLED", 0) + counts.get("PENDING", 0) + \
        counts.get("QUEUED", 0) + counts.get("INELIGIBLE", 0)
    rec.check(run_id, scenario, seed, strategy, "status_partition",
              len(payments), known)

    done = [t for t in fx if str(t.get("status")).upper() == "COMPLETED"]
    rec.check(run_id, scenario, seed, strategy, "fx_initiated",
              len(fx), int(summary.get("fx_initiated", -1)))
    rec.check(run_id, scenario, seed, strategy, "fx_completed",
              len(done), int(summary.get("fx_completed", -1)))

    # The engine books a trade's fee at initiation (even if still pending), so sum all rows
    cost_from_table = sum(float(t.get("total_cost_rmb") or 0) for t in fx)
    rec.check(run_id, scenario, seed, strategy, "fx_cost_rmb",
              cost_from_table, float(summary.get("fx_cost_rmb") or 0))

    # ---- B. balance reconciliation ----------------------------------------
    if balances:
        last = _last_balance_row(balances)
        rec.check(run_id, scenario, seed, strategy, "rmb_total_end",
                  float(last.get("rmb_total") or 0), float(summary.get("rmb_total_end") or 0))
        rec.check(run_id, scenario, seed, strategy, "hkd_total_end",
                  float(last.get("hkd_total") or 0), float(summary.get("hkd_total_end") or 0))
        rec.check(run_id, scenario, seed, strategy, "rmb_locked_end",
                  float(last.get("rmb_locked") or 0), float(summary.get("rmb_locked_end") or 0))
        times = [int(b["time"]) for b in balances]
        rec.check(run_id, scenario, seed, strategy, "balance_time_monotone",
                  True, all(a <= b for a, b in zip(times, times[1:])))

    # ---- C. cash identity -------------------------------------------------
    if identity and balances and dataset is not None:
        obs_end = int(summary["observation_end_sec"])
        cfg = dataset.config
        opening = float(cfg.get("initial_rmb_balance", 0))
        credited = sum(float(f.amount_rmb) for f in dataset.inflows
                       if int(f.arrival_time) <= obs_end)
        fx_in = sum(float(t.get("topup_rmb") or 0) for t in done)
        paid = sum(float(p["amount_rmb"]) for p in payments
                   if p.get("final_status") == "SETTLED")
        expected = opening + credited + fx_in - paid
        actual = float(_last_balance_row(balances).get("rmb_total") or 0)
        rec.check(run_id, scenario, seed, strategy, "rmb_liquidity_identity",
                  expected, actual, tol=1.0)


def write_details(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["run_id", "scenario_id", "seed", "strategy_id", "check",
              "computed_from_tables", "engine_reported", "delta", "ok"]
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 6) if isinstance(v, float) else v)
                        for k, v in r.items()})


def summarise(rows):
    """Summarise PASS/FAIL per check; returns (lines, any_failure)."""
    checks = []
    for r in rows:
        if r["check"] not in checks:
            checks.append(r["check"])
    lines = []
    any_fail = False
    width = max(len(c) for c in checks) + 2
    lines.append(f"{'check':{width}s}{'runs':>8s}{'pass':>8s}{'fail':>8s}")
    lines.append("-" * (width + 24))
    for c in checks:
        sub = [r for r in rows if r["check"] == c]
        bad = [r for r in sub if r["ok"] == "FAIL"]
        any_fail |= bool(bad)
        lines.append(f"{c:{width}s}{len(sub):>8d}{len(sub) - len(bad):>8d}{len(bad):>8d}")
    lines.append("")
    runs = {}
    for r in rows:
        runs.setdefault(r["run_id"], []).append(r["ok"])
    clean = sum(1 for v in runs.values() if all(x == "PASS" for x in v))
    lines.append(f"runs reconciled: {len(runs)}   fully clean: {clean}   "
                 f"with a failed check: {len(runs) - clean}")
    return lines, any_fail


def csv_cross_check(repos, scenarios, seeds, n, workdir=".", log=print):
    """Write real output to disk once, recompute through the CSV path, compare with the engine path."""
    from m3engine import io as m3io, load_dataset, run_dataset  # noqa: PLC0415

    log("\n" + "=" * 100)
    log("CROSS-CHECK  CSV path (calculate_metrics) vs engine path (measure)")
    log("=" * 100)
    done = 0
    bad = 0
    for scenario in scenarios:
        if done >= n:
            break
        dataset_dir = repos["fixtures"] / scenario / f"seed_{seeds[0]}"
        if not dataset_dir.is_dir():
            continue
        dataset = load_dataset(dataset_dir)
        for strategy in STRATEGIES:
            if done >= n:
                break
            result = run_dataset(dataset, strategy)
            tmp = Path(workdir) / "_csv_check" / f"{scenario}_{strategy}"
            tmp.mkdir(parents=True, exist_ok=True)
            m3io.write_outputs(result, tmp)
            from_csv = calculate_metrics(
                tmp / "payment_results.csv",
                tmp / "events.csv",
                tmp / "balances.csv",
                dataset.config,
                fx_trades=tmp / "fx_trades.csv",
            )
            from_engine = measure(result)
            keys = ["ALL.completion", "ALL.mean_delay", "ALL.p95_delay",
                    "ALL.overdue_rate", "rmb_liquidity_hours", "hkd_liquidity_hours",
                    "fx_initiated", "fx_cost_rmb"]
            diffs = []
            for k in keys:
                a, b = from_csv.get(k), from_engine.get(k)
                if a is None or b is None:
                    diffs.append(f"{k}: missing ({a!r}/{b!r})")
                elif abs(float(a) - float(b)) > 1e-6:
                    diffs.append(f"{k}: csv={a:.6f} engine={b:.6f}")
            done += 1
            status = "OK" if not diffs else "DIFF"
            bad += bool(diffs)
            log(f"  {status:5s} {scenario:20s}{strategy}  "
                + ("agrees on all 8 metrics" if not diffs else "; ".join(diffs)))
    log(f"  -> {done} runs compared, {bad} with a difference")
    return done, bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Reconcile Module 6 metrics against the engine")
    ap.add_argument("--repos", default="_repos")
    ap.add_argument("--out", default="evidence")
    ap.add_argument("--seed-set", default="formal", choices=("formal", "pilot"))
    ap.add_argument("--scenarios", default="")
    ap.add_argument("--strategies", default="S0,S1,S2,S3,S4")
    ap.add_argument("--limit", type=int, default=None, help="stop after N runs")
    ap.add_argument("--csv-check", type=int, default=0,
                    help="also cross-check N runs through the CSV path")
    a = ap.parse_args(argv)

    repos = find_repos(Path(a.repos))
    setup_paths(repos)
    from m3engine import load_dataset, run_dataset  # noqa: PLC0415

    scenarios = [s.strip() for s in a.scenarios.split(",") if s.strip()] or SCENARIOS
    strategies = [s.strip().upper() for s in a.strategies.split(",") if s.strip()]
    seeds = SEED_SETS[a.seed_set]

    lines = []

    def log(msg=""):
        print(msg)
        lines.append(str(msg))

    log("=" * 100)
    log("Module 6 -- reconciliation of computed metrics against engine-reported numbers")
    log("=" * 100)
    log(f"fixtures : {repos['fixtures']}")
    log(f"seed set : {a.seed_set} ({len(seeds)} seeds)")
    log(f"matrix   : {len(scenarios)} x {len(seeds)} x {len(strategies)}"
        f" = {len(scenarios)*len(seeds)*len(strategies)} runs")

    rec = Reconciler()
    done = 0
    for scenario in scenarios:
        for seed in seeds:
            dataset_dir = repos["fixtures"] / scenario / f"seed_{seed}"
            if not dataset_dir.is_dir():
                log(f"  ! missing dataset {dataset_dir}")
                continue
            dataset = load_dataset(dataset_dir)
            for strategy in strategies:
                result = run_dataset(dataset, strategy)
                run_id = f"{scenario}_seed{seed}_{strategy}"
                reconcile_run(rec, result, dataset, scenario, seed, strategy, run_id)
                done += 1
                if a.limit and done >= a.limit:
                    break
            if a.limit and done >= a.limit:
                break
        log(f"  [{scenario}] reconciled, cumulative {done}")
        if a.limit and done >= a.limit:
            break

    body, any_fail = summarise(rec.rows)
    log("")
    log("-" * 100)
    log("PER-CHECK SUMMARY")
    log("-" * 100)
    for line in body:
        log(line)

    failures = [r for r in rec.rows if r["ok"] == "FAIL"]
    if failures:
        log("")
        log("FIRST 10 FAILURES")
        for r in failures[:10]:
            log(f"  {r['run_id']:34s}{r['check']:24s} computed={r['computed_from_tables']}"
                f" engine={r['engine_reported']} delta={r['delta']}")

    out = Path(a.out)
    write_details(out / "reconciliation.csv", rec.rows)

    by_run = {}
    for r in rec.rows:
        by_run.setdefault(r["run_id"], {"scenario_id": r["scenario_id"],
                                        "seed": r["seed"],
                                        "strategy_id": r["strategy_id"]})
        by_run[r["run_id"]]["n_checks"] = by_run[r["run_id"]].get("n_checks", 0) + 1
        if r["ok"] == "FAIL":
            by_run[r["run_id"]]["failed"] = by_run[r["run_id"]].get("failed", 0) + 1
    out.mkdir(parents=True, exist_ok=True)
    with (out / "reconciliation_by_run.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["run_id", "scenario_id", "seed", "strategy_id",
                    "n_checks", "n_failed", "verdict"])
        for rid, d in by_run.items():
            failed = d.get("failed", 0)
            w.writerow([rid, d["scenario_id"], d["seed"], d["strategy_id"],
                        d["n_checks"], failed, "PASS" if failed == 0 else "FAIL"])

    if a.csv_check:
        n_done, n_bad = csv_cross_check(repos, scenarios, seeds, a.csv_check, Path(a.out))
        log(f"\ncsv cross-check: {n_done} runs, {n_bad} differences")
        any_fail |= bool(n_bad)

    log("")
    log("RESULT: " + ("PASS -- every computed number matches the engine"
                      if not any_fail else "FAIL -- see reconciliation.csv"))
    log(f"written: {out/'reconciliation.csv'}, {out/'reconciliation_by_run.csv'}")
    (out / "reconciliation_summary.txt").write_text("\n".join(lines), encoding="utf-8")
    return 0 if not any_fail else 2


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    sys.exit(main())
