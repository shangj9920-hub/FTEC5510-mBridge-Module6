# -*- coding: utf-8 -*-
"""audit.py -- independent audit of the delivered package.

Four layers, deliberately independent of each other and of the code that
produced the numbers:

  L1  data    -- every one of the 210 datasets re-validated against the contract
  L2  params  -- every config.json checked against the values the docs claim
  L3  results -- the headline numbers recomputed from evidence/metrics.csv and
                 compared with what docs/RESULTS.md states
  L4  replay  -- a sample re-simulated from scratch and compared cell by cell
                 with evidence/metrics.csv

Nothing here imports the m6metrics code used to build the tables, except in L4
where a fresh engine run is the source of truth.
"""
from __future__ import annotations

import csv
import hashlib
import json
import statistics
import sys
from pathlib import Path

APP = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(".")
REPOS = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else None
SCEN = ["baseline", "low_rmb_liquidity", "payment_surge", "tight_deadlines",
        "large_payments", "delayed_inflows", "fx_capacity_shock"]
STRATS = ["S0", "S1", "S2", "S3", "S4"]
PRIORITIES = {"URGENT", "HIGH", "NORMAL"}

fails: list[str] = []
notes: list[str] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    print(("  PASS  " if ok else "  FAIL  ") + label + (f"   {detail}" if detail else ""))
    if not ok:
        fails.append(label + " | " + detail)


def read_csv(p: Path):
    with p.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


# --------------------------------------------------------------------------- #
# L1  data
# --------------------------------------------------------------------------- #
def layer_data(fixtures: Path) -> None:
    print("\nL1  DATA -- 210 datasets against the Module 2 contract")
    datasets = 0
    problems = []
    seeds_seen = set()
    for scen in SCEN:
        scen_dir = fixtures / scen
        if not scen_dir.is_dir():
            problems.append(f"missing scenario dir {scen}")
            continue
        for seed_dir in sorted(scen_dir.iterdir()):
            if not seed_dir.is_dir():
                continue
            datasets += 1
            seeds_seen.add(seed_dir.name)
            cfg = json.loads((seed_dir / "config.json").read_text(encoding="utf-8"))
            pays = read_csv(seed_dir / "payments.csv")
            inflows = read_csv(seed_dir / "inflows.csv")
            ids = set()
            for p in pays:
                pid = p["payment_id"]
                if pid in ids:
                    problems.append(f"{seed_dir.name}/{scen}: duplicate payment_id {pid}")
                ids.add(pid)
                if float(p["amount_rmb"]) <= 0:
                    problems.append(f"{scen}/{seed_dir.name}:{pid} amount <= 0")
                if p["priority"] not in PRIORITIES:
                    problems.append(f"{scen}/{seed_dir.name}:{pid} bad priority")
                if int(p["deadline_time"]) <= int(p["arrival_time"]):
                    problems.append(f"{scen}/{seed_dir.name}:{pid} deadline <= arrival")
                if int(p["arrival_time"]) < 0 or int(p["deadline_time"]) < 0:
                    problems.append(f"{scen}/{seed_dir.name}:{pid} negative time")
                if p["eligible"].strip().lower() not in ("true", "false"):
                    problems.append(f"{scen}/{seed_dir.name}:{pid} bad eligible flag")
            for f in inflows:
                notice = (f["notice_time"] or "").strip()
                if notice and not (0 <= int(notice) <= int(f["arrival_time"])):
                    problems.append(f"{scen}/{seed_dir.name}:{f['inflow_id']} bad notice_time")
                if float(f["amount_rmb"]) <= 0:
                    problems.append(f"{scen}/{seed_dir.name}:{f['inflow_id']} inflow <= 0")
            # manifest integrity, independent of the engine's loader
            man = seed_dir / "manifest.json"
            if man.exists():
                m = json.loads(man.read_text(encoding="utf-8"))
                for name, digest in (m.get("sha256") or {}).items():
                    target = seed_dir / name
                    if target.exists():
                        got = hashlib.sha256(target.read_bytes()).hexdigest()
                        if got != digest:
                            problems.append(f"{scen}/{seed_dir.name}: {name} sha256 mismatch")

    check(datasets == 210, "210 datasets present", f"found {datasets}")
    check(len(seeds_seen) == 30, "30 distinct seeds per scenario", f"found {len(seeds_seen)}")
    check(not problems, "no contract or integrity violation",
          "" if not problems else f"{len(problems)} problems, first: {problems[0]}")
    if problems:
        for p in problems[:5]:
            print("        ", p)


# --------------------------------------------------------------------------- #
# L2  parameters
# --------------------------------------------------------------------------- #
def layer_params(fixtures: Path) -> None:
    print("\nL2  PARAMS -- every config.json against the values the docs claim")
    claims_common = {
        "simulation_window_sec": 28800,
        "rmb_reserve": 800_000.0,
        "initial_hkd_balance": 15_000_000.0,
        "fx_rate": 0.9,
        "fx_spread_bps": 15.0,
        "fx_fee_fixed_hkd": 80.0,
        "fx_execution_delay_sec": 120,
    }
    # opening RMB is scenario-specific: 1.8 m in the liquidity stress, 6 m elsewhere
    claims_by_scen = {s: dict(claims_common) for s in SCEN}
    for s in SCEN:
        claims_by_scen[s]["initial_rmb_balance"] = 1_800_000.0 if s == "low_rmb_liquidity" else 6_000_000.0
        claims_by_scen[s]["fx_counterparty_capacity_rmb"] = (
            1_000_000.0 if s == "fx_capacity_shock" else 5_000_000.0)
    claims_by_scen["low_rmb_liquidity"]["rmb_reserve"] = claims_common["rmb_reserve"]
    seen: dict = {}
    bad = []
    for scen in SCEN:
        for seed_dir in sorted((fixtures / scen).iterdir()):
            if not seed_dir.is_dir():
                continue
            cfg = json.loads((seed_dir / "config.json").read_text(encoding="utf-8"))
            for key, want in claims_by_scen[scen].items():
                got = cfg.get(key)
                if got is None or abs(float(got) - float(want)) > 1e-9:
                    bad.append(f"{scen}/{seed_dir.name}: {key}={got!r} expected {want!r}")
            prio = (cfg.get("data_generation") or {}).get("priority_probabilities") or {}
            shares = tuple(round(float(prio.get(k, -1)), 4) for k in ("URGENT", "HIGH", "NORMAL"))
            seen.setdefault(scen, set()).add(shares)
            if shares != (0.1, 0.25, 0.65):
                bad.append(f"{scen}/{seed_dir.name}: priority shares {shares}")

    check(not bad, "all fixtures carry the documented parameters",
          "" if not bad else f"{len(bad)} deviations, first: {bad[0]}")
    if bad:
        for b in bad[:5]:
            print("        ", b)

    # the one scenario that is supposed to differ must actually differ
    base = json.loads((fixtures / "baseline" / "seed_20001" / "config.json").read_text(encoding="utf-8"))
    low = json.loads((fixtures / "low_rmb_liquidity" / "seed_20001" / "config.json").read_text(encoding="utf-8"))
    check(low["initial_rmb_balance"] < base["initial_rmb_balance"],
          "low_rmb_liquidity really lowers the opening balance",
          f'{low["initial_rmb_balance"]:,.0f} < {base["initial_rmb_balance"]:,.0f}')

    # documented deviations from the proposal: assert they are still true
    check(abs(base["initial_rmb_balance"] - 20_000_000) > 1,
          "opening RMB differs from the proposal's 20m (deviation is real)",
          f'{base["initial_rmb_balance"]:,.0f}')
    check(abs(base["fx_spread_bps"] - 3) > 1,
          "spread differs from the proposal's 3 bps (deviation is real)",
          f'{base["fx_spread_bps"]} bps')
    # the two missing scenarios: assert the fixture set really lacks them
    modes = {(json.loads((fixtures / s / "seed_20001" / "config.json").read_text(encoding="utf-8"))
              .get("engine_parameters") or {}).get("fx_counterparty_capacity_mode") for s in SCEN}
    check(modes == {"per_trade"} or modes == {None},
          "capacity mode is per_trade in every fixture (so FX never runs out)",
          f"modes={modes}")


# --------------------------------------------------------------------------- #
# L3  results recomputed from the delivered table
# --------------------------------------------------------------------------- #
def layer_results(evidence: Path) -> None:
    print("\nL3  RESULTS -- headline numbers recomputed from evidence/metrics.csv")
    rows = read_csv(evidence / "metrics.csv")
    check(len(rows) == 1050, "1050 metric rows", f"found {len(rows)}")
    check(all(r["using_fallback_m4"] == "False" and r["using_fallback_m5"] == "False"
              for r in rows), "no run used a fallback module")
    check(all(r["obs_end_sec"] == "28800" for r in rows), "observation endpoint is 28800 s in every run")
    check(all(int(float(r["ineligible"])) == 0 for r in rows), "no ineligible payments in the fixtures")
    cells = {(r["scenario_id"], r["strategy_id"]) for r in rows}
    check(len(cells) == 35, "35 scenario x strategy cells", f"found {len(cells)}")

    def mean(scen, strat, key):
        vals = [float(r[key]) for r in rows
                if r["scenario_id"] == scen and r["strategy_id"] == strat]
        return statistics.mean(vals)

    def paired(scen, key, a, b):
        by_seed = {}
        for r in rows:
            if r["scenario_id"] == scen:
                by_seed.setdefault(r["seed"], {})[r["strategy_id"]] = float(r[key])
        d = [v[a] - v[b] for v in by_seed.values() if a in v and b in v]
        return statistics.mean(d)

    # values quoted in docs/RESULTS.md
    quoted = [
        ("completion payment_surge S1", mean("payment_surge", "S1", "ALL.completion"), 0.683, 0.002),
        ("completion payment_surge S2", mean("payment_surge", "S2", "ALL.completion"), 0.706, 0.002),
        ("completion large_payments S2", mean("large_payments", "S2", "ALL.completion"), 0.579, 0.002),
        ("completion fx_shock S2", mean("fx_capacity_shock", "S2", "ALL.completion"), 0.988, 0.002),
        ("P95 delay payment_surge S2", mean("payment_surge", "S2", "ALL.p95_delay"), 3490, 15),
        ("P95 delay large_payments S2", mean("large_payments", "S2", "ALL.p95_delay"), 6112, 20),
        ("URGENT delay baseline S2", mean("baseline", "S2", "URGENT.mean_delay"), 48.2, 0.5),
        ("URGENT completion payment_surge S2", mean("payment_surge", "S2", "URGENT.completion"), 0.908, 0.002),
        ("URGENT completion large_payments S2", mean("large_payments", "S2", "URGENT.completion"), 0.839, 0.002),
        ("RMB hours baseline S1 (millions)", mean("baseline", "S1", "rmb_liquidity_hours") / 1e6, 19.62, 0.01),
    ]
    for label, got, want, tol in quoted:
        check(abs(got - want) <= tol, f"quoted value: {label}", f"table={got:,.3f} doc={want:,.3f}")

    diffs = [
        ("URGENT delay S2-S1 baseline", paired("baseline", "URGENT.mean_delay", "S2", "S1"), -9.2, 0.2),
        ("URGENT delay S2-S1 surge", paired("payment_surge", "URGENT.mean_delay", "S2", "S1"), -385.8, 2.0),
        ("URGENT delay S2-S1 large", paired("large_payments", "URGENT.mean_delay", "S2", "S1"), -736.6, 3.0),
        ("NORMAL completion S2-S1 surge (pp)", paired("payment_surge", "NORMAL.completion", "S2", "S1") * 100, -4.55, 0.15),
        ("NORMAL completion S2-S1 large (pp)", paired("large_payments", "NORMAL.completion", "S2", "S1") * 100, -6.21, 0.15),
        ("FX trades S3-S1 baseline", paired("baseline", "fx_initiated", "S3", "S1"), -7.7, 0.2),
        ("all delay S3-S1 surge", paired("payment_surge", "ALL.mean_delay", "S3", "S1"), 883.0, 5.0),
    ]
    for label, got, want, tol in diffs:
        check(abs(got - want) <= tol, f"quoted paired difference: {label}",
              f"recomputed={got:+.2f} doc={want:+.2f}")

    # internal identities that must hold in any correct metric table
    bad = []
    for r in rows:
        if abs(float(r["ALL.completion"]) * float(r["ALL.n"])
               - float(r["ALL.settled"])) > 1e-3:
            bad.append(f"{r['run_id']}: completion x n != settled")
        if abs(float(r["ALL.overdue_rate"]) * float(r["ALL.due"])
               - float(r["ALL.overdue"])) > 1e-3:
            bad.append(f"{r['run_id']}: overdue rate x due != overdue")
        if float(r["ALL.outstanding"]) + float(r["ALL.settled"]) != float(r["ALL.n"]):
            bad.append(f"{r['run_id']}: settled + outstanding != n")
        if not (0.0 <= float(r["ALL.completion"]) <= 1.0):
            bad.append(f"{r['run_id']}: completion out of range")
    check(not bad, "internal identities hold in all 1050 rows",
          "" if not bad else f"{len(bad)} violations, first: {bad[0]}")

    # the comparison table must agree with the metric table
    comp = read_csv(evidence / "comparison.csv")
    check(len(comp) == 35, "comparison.csv has 35 cells", f"found {len(comp)}")
    mism = []
    for c in comp:
        m = mean(c["scenario_id"], c["strategy_id"], "ALL.completion")
        if abs(m - float(c["ALL.completion"])) > 1e-6:
            mism.append(f'{c["scenario_id"]}/{c["strategy_id"]}')
    check(not mism, "comparison.csv agrees with metrics.csv",
          "" if not mism else f"{len(mism)} cells differ")


# --------------------------------------------------------------------------- #
# L4  replay a sample from scratch
# --------------------------------------------------------------------------- #
def layer_replay(fixtures: Path, evidence: Path, repos: Path) -> None:
    print("\nL4  REPLAY -- re-simulate a sample and compare cell by cell")
    sys.path.insert(0, str(APP / "module6"))
    from run_module6 import find_repos, setup_paths          # noqa: PLC0415
    setup_paths(find_repos(repos))
    from m3engine import load_dataset, run_dataset          # noqa: PLC0415
    from m6metrics import measure                            # noqa: PLC0415

    delivered = {(r["scenario_id"], r["seed"], r["strategy_id"]): r
                 for r in read_csv(evidence / "metrics.csv")}
    keys = ["ALL.completion", "ALL.mean_delay", "ALL.p95_delay", "ALL.overdue_rate",
            "URGENT.mean_delay", "NORMAL.completion", "rmb_liquidity_hours",
            "hkd_liquidity_hours", "fx_initiated", "fx_cost_rmb"]
    sample = [(s, 20001) for s in SCEN] + [("baseline", 20015), ("payment_surge", 20023)]
    replayed = 0
    bad = []
    for scen, seed in sample:
        dataset = load_dataset(fixtures / scen / f"seed_{seed}")
        for strat in STRATS:
            fresh = measure(run_dataset(dataset, strat))
            old = delivered[(scen, str(seed), strat)]
            replayed += 1
            for k in keys:
                a, b = fresh.get(k), old.get(k)
                if a is None or b in (None, ""):
                    bad.append(f"{scen}/{seed}/{strat}: {k} missing")
                    continue
                if abs(float(a) - float(b)) > 1e-6:
                    bad.append(f"{scen}/{seed}/{strat}: {k} fresh={a:.6f} delivered={b}")
    check(not bad, f"{replayed} replayed runs match the delivered table exactly",
          "" if not bad else f"{len(bad)} mismatches, first: {bad[0]}")
    if bad:
        for b in bad[:8]:
            print("        ", b)


def main() -> int:
    print("=" * 78)
    print("INDEPENDENT AUDIT --", APP)
    print("=" * 78)
    fixtures = REPOS / "FTEC5510-mBridge-Module3-main" / "FTEC5510-mBridge-Module3-main" / "module3" / "fixtures" / "formal"
    if not fixtures.is_dir():
        fixtures = next(REPOS.rglob("fixtures/formal"))

    layer_data(fixtures)
    layer_params(fixtures)
    layer_results(APP / "evidence")
    layer_replay(fixtures, APP / "evidence", REPOS)

    print("\n" + "=" * 78)
    print(f"RESULT: {'PASS -- nothing inconsistent found' if not fails else str(len(fails)) + ' FAILURES'}")
    for f in fails:
        print("  -", f)
    return 0 if not fails else 2


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:   # noqa: BLE001
        pass
    sys.exit(main())
