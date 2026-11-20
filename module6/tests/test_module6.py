# -*- coding: utf-8 -*-
"""Module 6 acceptance tests.

Run from the repository root:

    python -m unittest discover -s module6/tests -v

The suite covers three levels:

1. the metric definitions on a hand-checkable fixture (every number in
   ``fixtures/fixed_demo/expected_metrics.json`` can be recomputed by hand);
2. the statistics helper (P95 interpolation, paired differences, 95% CI);
3. the interface contract ``calculate_metrics(payment_results, events, balances,
   config)`` — including that missing tables degrade to ``None`` instead of
   raising, and that blank times are never coerced to 0.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent                      # module6/
ROOT = PKG.parent                      # repository root
sys.path.insert(0, str(PKG))

from m6metrics import (  # noqa: E402
    calculate_metrics, ci95, liquidity_hours, measure, paired_diffs, p95,
)

FIXTURE = PKG / "fixtures" / "fixed_demo"


def load_fixture():
    with (FIXTURE / "expected_metrics.json").open(encoding="utf-8") as fh:
        return json.load(fh)


class FixedCaseMetrics(unittest.TestCase):
    """The five payments in fixtures/fixed_demo, checked against hand arithmetic."""

    @classmethod
    def setUpClass(cls):
        with (FIXTURE / "config.json").open(encoding="utf-8") as fh:
            cls.config = json.load(fh)
        cls.metrics = calculate_metrics(
            FIXTURE / "payment_results.csv",
            FIXTURE / "events.csv",
            FIXTURE / "balances.csv",
            cls.config,
            fx_trades=FIXTURE / "fx_trades.csv",
        )
        cls.expected = load_fixture()

    def test_completion_and_outstanding(self):
        self.assertEqual(self.metrics["ALL.n"], 5)
        self.assertEqual(self.metrics["ALL.settled"], 2)
        self.assertAlmostEqual(self.metrics["ALL.completion"], 0.4, places=9)
        self.assertEqual(self.metrics["ALL.outstanding"], 3)
        self.assertAlmostEqual(self.metrics["ALL.outstanding_amount_rmb"], 7_500_000.0, places=2)

    def test_delay_only_counts_settled_payments(self):
        # P1 150 s and P2 350 s are the only settled payments; P3/P4/P5 stay blank
        self.assertAlmostEqual(self.metrics["ALL.mean_delay"], 250.0, places=9)
        self.assertAlmostEqual(self.metrics["ALL.p95_delay"], 340.0, places=9)

    def test_overdue_includes_outstanding_payments_past_deadline(self):
        # due (deadline <= 1000): P1, P2, P3, P5 ; overdue: P2 (late), P3, P5
        self.assertEqual(self.metrics["ALL.due"], 4)
        self.assertEqual(self.metrics["ALL.overdue"], 3)
        self.assertAlmostEqual(self.metrics["ALL.overdue_rate"], 0.75, places=9)
        # P4 is outstanding but not yet due, so it must not be counted as overdue
        self.assertEqual(self.metrics["HIGH.overdue"], 0)

    def test_priority_blocks(self):
        self.assertAlmostEqual(self.metrics["URGENT.completion"], 1.0, places=9)
        self.assertAlmostEqual(self.metrics["URGENT.mean_delay"], 150.0, places=9)
        self.assertAlmostEqual(self.metrics["NORMAL.completion"], 1 / 3, places=9)
        self.assertAlmostEqual(self.metrics["NORMAL.overdue_rate"], 1.0, places=9)
        self.assertAlmostEqual(self.metrics["HIGH.completion"], 0.0, places=9)

    def test_liquidity_hours_are_a_time_integral(self):
        # 20,000,000 RMB held for 1,000 s = 20,000,000 * 1000 / 3600 hours
        self.assertAlmostEqual(self.metrics["rmb_liquidity_hours"], 20e6 * 1000 / 3600, places=4)
        self.assertAlmostEqual(self.metrics["hkd_liquidity_hours"], 100e6 * 1000 / 3600, places=4)

    def test_fx_behaviour_and_cost(self):
        self.assertEqual(self.metrics["fx_initiated"], 1)
        self.assertEqual(self.metrics["fx_completed"], 1)
        self.assertAlmostEqual(self.metrics["fx_cost_rmb"], 500.0, places=2)
        self.assertAlmostEqual(self.metrics["fx_rmb_obtained"], 1_000_000.0, places=2)

    def test_every_expected_value_matches(self):
        for key, want in self.expected.items():
            with self.subTest(key=key):
                got = self.metrics[key]
                self.assertIsNotNone(got, f"{key} missing")
                self.assertAlmostEqual(float(got), float(want), places=6)

    def test_observation_end_comes_from_config(self):
        self.assertEqual(self.metrics["obs_end_sec"], 1000)


class ObservationEndpoint(unittest.TestCase):
    def test_window_plus_drain(self):
        cfg = {"simulation_window_sec": 28800,
               "engine_parameters": {"observation_drain_sec": 600}}
        m = calculate_metrics(FIXTURE / "payment_results.csv", None,
                              FIXTURE / "balances.csv", cfg)
        self.assertEqual(m["obs_end_sec"], 29400)

    def test_falls_back_to_last_balance_timestamp(self):
        m = calculate_metrics(FIXTURE / "payment_results.csv", None,
                              FIXTURE / "balances.csv", {})
        self.assertEqual(m["obs_end_sec"], 1000)


class DegradedInputs(unittest.TestCase):
    def test_missing_balances_and_fx_do_not_raise(self):
        m = calculate_metrics(FIXTURE / "payment_results.csv", None, None,
                              {"observation_end_sec": 1000})
        self.assertIsNone(m["rmb_liquidity_hours"])
        self.assertIsNone(m["fx_cost_rmb"])
        self.assertIn("balances is missing", m["warnings"])
        self.assertAlmostEqual(m["ALL.completion"], 0.4, places=9)

    def test_empty_payment_results_is_reported(self):
        m = calculate_metrics([], None, None, {})
        self.assertIn("missing or empty", m["warnings"])


class Statistics(unittest.TestCase):
    def test_p95_interpolation(self):
        self.assertEqual(p95([100]), 100.0)
        self.assertAlmostEqual(p95([150, 350]), 340.0, places=9)
        self.assertAlmostEqual(p95(list(range(1, 101))), 95.05, places=9)

    def test_ci_is_symmetric_and_collapses_for_one_observation(self):
        mean, low, high = ci95([2.0])
        self.assertEqual((mean, low, high), (2.0, 2.0, 2.0))
        mean, low, high = ci95([1.0, 2.0, 3.0])
        self.assertAlmostEqual(mean, 2.0)
        self.assertAlmostEqual(mean - low, high - mean)

    def test_paired_differences_are_formed_within_a_seed(self):
        records = [
            {"scenario_id": "s", "seed": 1, "strategy_id": "S1", "d": 100.0},
            {"scenario_id": "s", "seed": 1, "strategy_id": "S2", "d": 90.0},
            {"scenario_id": "s", "seed": 2, "strategy_id": "S1", "d": 200.0},
            {"scenario_id": "s", "seed": 2, "strategy_id": "S2", "d": 150.0},
            {"scenario_id": "s", "seed": 3, "strategy_id": "S1", "d": 50.0},   # unpaired
        ]
        diffs = paired_diffs(records, "d", "S2", "S1")
        self.assertEqual(sorted(diffs), [-50.0, -10.0])


class EngineResultPath(unittest.TestCase):
    """measure() must accept any object with the engine's result shape."""

    def test_measure_matches_calculate_metrics(self):
        import types

        def rows(path):
            import csv
            with open(path, encoding="utf-8-sig", newline="") as fh:
                return list(csv.DictReader(fh))

        with (FIXTURE / "config.json").open(encoding="utf-8") as fh:
            cfg = json.load(fh)
        payments = rows(FIXTURE / "payment_results.csv")
        for p in payments:
            p["amount_rmb"] = float(p["amount_rmb"])
        summary = {
            "observation_end_sec": 1000, "n_payments": len(payments),
            "fx_initiated": 1, "fx_completed": 1, "fx_infeasible": 0,
            "fx_cost_rmb": "500.00", "ineligible": 0,
            "using_fallback_module4": False, "using_fallback_module5": False,
        }
        result = types.SimpleNamespace(
            summary=summary, payments=payments,
            balances=rows(FIXTURE / "balances.csv"),
            fx_trades=rows(FIXTURE / "fx_trades.csv"),
        )
        live = measure(result)
        self.assertAlmostEqual(live["ALL.completion"], 0.4, places=9)
        self.assertAlmostEqual(live["rmb_liquidity_hours"], 20e6 * 1000 / 3600, places=4)
        self.assertFalse(live["using_fallback_m4"])

    def test_balance_integral_ignores_out_of_order_rows(self):
        rows = [{"time": "100", "rmb_total": "10", "hkd_total": "0"},
                {"time": "0", "rmb_total": "10", "hkd_total": "0"}]
        rmb, hkd = liquidity_hours(rows)
        self.assertAlmostEqual(rmb, 10 * 100 / 3600, places=9)
        self.assertEqual(hkd, 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
