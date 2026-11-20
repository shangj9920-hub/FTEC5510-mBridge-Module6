# -*- coding: utf-8 -*-
"""Command-line wrapper for ``m6metrics.calculate_metrics``.

    python module6/calculate_metrics.py --run-dir <dir>            # one row as JSON
    python module6/calculate_metrics.py --run-dir <dir> --append metrics.csv
    python module6/calculate_metrics.py --run-dir <dir> `
        --meta '{"run_id":"...","scenario_id":"baseline","seed":20001,"strategy_id":"S2"}'

The directory must contain ``payment_results.csv``; ``balances.csv``,
``events.csv``, ``fx_trades.csv`` and ``config.json`` are optional and only
degrade the affected measures. This is the entry point for anyone who wants one
number without running the simulation matrix.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from m6metrics import calculate_metrics  # noqa: E402

META_FIELDS = ["run_id", "scenario_id", "seed", "strategy_id"]


def read_config(run_dir: Path) -> dict:
    path = run_dir / "config.json"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig") as fh:
        return json.load(fh)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Calculate Module 6 metrics for one run")
    ap.add_argument("--run-dir", required=True, help="directory with the result tables")
    ap.add_argument("--meta", default="{}", help="JSON with run_id/scenario_id/seed/strategy_id")
    ap.add_argument("--append", default=None, help="append the row to this metrics.csv")
    a = ap.parse_args(argv)

    run_dir = Path(a.run_dir)
    if not run_dir.is_dir():
        raise SystemExit(f"not a directory: {run_dir}")

    metrics = calculate_metrics(
        run_dir / "payment_results.csv",
        run_dir / "events.csv" if (run_dir / "events.csv").exists() else None,
        run_dir / "balances.csv" if (run_dir / "balances.csv").exists() else None,
        read_config(run_dir),
        fx_trades=run_dir / "fx_trades.csv" if (run_dir / "fx_trades.csv").exists() else None,
    )

    row = {}
    for key in META_FIELDS:
        row[key] = json.loads(a.meta).get(key, "")
    row.update({k: v for k, v in metrics.items() if k != "warnings"})

    print(json.dumps({"metrics": row, "warnings": metrics.get("warnings", "")},
                     ensure_ascii=False, indent=2, default=str))

    if a.append:
        exists = os.path.exists(a.append)
        with open(a.append, "a", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(row))
            if not exists:
                writer.writeheader()
            writer.writerow(row)
        print(f"appended -> {a.append}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
