"""Shared Lazy Collective source-status vectors (test-vectors/source-status)."""

import json
import unittest
from pathlib import Path

from pagedigest.recurring import SYNC_STATUS, source_state, source_status

VECTORS = Path(__file__).resolve().parents[3] / "test-vectors" / "source-status" / "vectors.json"


class SourceStatusVectors(unittest.TestCase):
    def test_vectors(self):
        document = json.loads(VECTORS.read_text(encoding="utf-8"))
        self.assertEqual(document["version"], 1)
        for case in document["cases"]:
            with self.subTest(case["name"]):
                states = [
                    source_state(s["bound"], s["observed"], s.get("boundBodyRetained", True)) for s in case["sources"]
                ]
                self.assertEqual(states, case["expectedSources"])
                self.assertEqual(source_status(states), case["expected"])

    def test_sync_labels_cover_the_vocabulary(self):
        self.assertEqual(set(SYNC_STATUS), {"current", "changed", "unknown"})


if __name__ == "__main__":
    unittest.main()
