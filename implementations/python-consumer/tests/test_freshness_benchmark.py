"""Behavioral controls for the P1 fixture's freshness and cost boundaries."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[3] / "tools"
sys.path.insert(0, str(TOOLS))
import benchmark_freshness as study  # noqa: E402


class FreshnessStudyTests(unittest.TestCase):
    def test_all_strategies_recover_concealed_change_and_refuse_incomplete_snapshot(self):
        spec = json.loads((study.PACKET / "SPEC.json").read_text())
        report = study.matrix(spec, sizes=(10,), client_counts=(1,), repeats=1)
        self.assertTrue(report["correctness_pass"], report["totals"])
        self.assertEqual(len(report["rows"]), 84)
        for arm in spec["arms"]:
            by_cycle = {r["cycle"]: r for r in report["rows"] if r["arm"] == arm}
            self.assertFalse(by_cycle[10]["complete"])
            self.assertTrue(all(row["complete"] for cycle, row in by_cycle.items() if cycle != 10))
            self.assertTrue(by_cycle[11]["complete"])
            self.assertFalse(by_cycle[4]["within_deadline_stale_paths"])
            self.assertGreater(by_cycle[6]["requests"], 0)
            self.assertEqual(by_cycle[8]["cache_read_bytes"], 0)
        fresh = next(r for r in report["rows"] if r["arm"] == "http-freshness" and r["cycle"] == 1)
        self.assertEqual(fresh["requests"], 1)  # discovery only, no page validation
        self.assertEqual(report["budget"]["requests"], sum(r["requests"] for r in report["rows"]))
        self.assertEqual(
            report["budget"]["response_bytes"], sum(r["body_bytes"] + r["header_bytes"] for r in report["events"])
        )
        self.assertLess(max(r["body_bytes"] + r["header_bytes"] for r in report["events"]), 65536)

    def test_budgets_stop_before_network_and_keep_incomplete_denominator(self):
        spec = json.loads((study.PACKET / "SPEC.json").read_text())
        for budget in [study.Budget(max_requests=0), study.Budget(max_bytes=0), study.Budget(seconds=0)]:
            with self.subTest(budget=budget):
                result = study.matrix(spec, sizes=(10,), client_counts=(1,), repeats=1, budget=budget)
                self.assertFalse(result["matrix_complete"])
                self.assertFalse(result["correctness_pass"])
                self.assertIsNotNone(result["budget_stop"])
                self.assertEqual(result["budget"]["requests"], 0)
                self.assertEqual(result["expected_rows"], 84)

    def test_changed_frozen_spec_and_existing_results_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "SPEC.json").write_text("{}")
            (root / "SPEC.sha256").write_text("0" * 64 + "  SPEC.json\n")
            with patch.object(study, "PACKET", root):
                with self.assertRaisesRegex(ValueError, "specification changed"):
                    study.run_study(root / "result.json")
            output = root / "already.json"
            output.write_text("preserve")
            with self.assertRaises(FileExistsError):
                study.run_study(output)
            self.assertEqual(output.read_text(), "preserve")

    def test_mid_cycle_budget_stop_retains_failed_work(self):
        spec = json.loads((study.PACKET / "SPEC.json").read_text())
        report = study.matrix(spec, sizes=(10,), client_counts=(1,), repeats=1, budget=study.Budget(max_requests=2))
        self.assertFalse(report["correctness_pass"])
        self.assertFalse(report["matrix_complete"])
        self.assertEqual(report["expected_rows"], 84)
        self.assertEqual(len(report["rows"]), 1)
        self.assertEqual(report["rows"][0]["error"], "BudgetExceeded")
        self.assertFalse(report["rows"][0]["complete"])
        self.assertEqual(report["budget"]["requests"], 2)
        self.assertEqual(len(report["events"]), 2)
        self.assertEqual(report["rows"][0]["requests"], 2)


if __name__ == "__main__":
    unittest.main()
