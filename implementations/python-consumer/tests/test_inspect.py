from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_recurring import Origin, entry

from pagedigest import cli
from pagedigest.persistence import empty_state, save_state
from pagedigest.recurring import digest, inspect_state, read_state, remember, sync


class InspectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name) / "cache.json"
        self.origin = Origin()
        self.origin.page("/setup", b"<p>Requires Python 3.9 or newer.</p>", cache="no-cache")
        self.origin.page("/news", b"<p>News</p>", cache="no-cache")
        self.cycle()
        remember(self.state, "python", "Use Python 3.9 or newer.", ["/setup"], now=100)

    def cycle(self, now=100):
        return sync(
            "https://example.com",
            self.state,
            urls=["/setup", "/news"],
            session=self.origin,
            now=now,
            audit_rate=0,
            http_only=True,
            max_age=60,
        )

    def test_restart_inspection_reads_text_and_preserves_all_state_bytes_and_age(self):
        before = {p.name: p.read_bytes() for p in self.state.parent.rglob("*") if p.is_file()}
        with patch("pagedigest.recurring.requests.Session", side_effect=AssertionError("unexpected HTTP")):
            result = inspect_state(self.state, finding_id="python", source="/setup", now=110)
        self.assertEqual(result["schema"], 1)
        finding = result["findings"][0]
        self.assertEqual(finding["text"], "Use Python 3.9 or newer.")
        self.assertEqual(finding["created_at"], 100)
        self.assertEqual(finding["sources"], {"/setup": digest(b"<p>Requires Python 3.9 or newer.</p>")})
        self.assertEqual(finding["sourceStatus"], "current")
        self.assertEqual(result["source"]["text"], "<p>Requires Python 3.9 or newer.</p>")
        self.assertEqual(result["source"]["validated_at"], 100)
        self.assertEqual(result["source"]["validation_expires_at"], 160)
        self.assertEqual(result["local_integrity_reads"], 2)
        after = {p.name: p.read_bytes() for p in self.state.parent.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_expired_or_clock_rollback_never_labels_finding_usable(self):
        for now in (99, 160, 200):
            with self.subTest(now=now):
                result = inspect_state(self.state, now=now)
                self.assertEqual(result["findings"][0]["status"], "unknown")
                self.assertTrue(result["sources"]["/setup"]["retained"])

    def test_unrelated_change_preserves_finding_relevant_change_requires_reread(self):
        self.origin.page("/news", b"<p>New news</p>", cache="no-cache")
        self.cycle(now=110)
        self.assertEqual(inspect_state(self.state, now=111)["findings"][0]["status"], "usable")
        self.origin.page("/setup", b"<p>Requires Python 3.12 or newer.</p>", cache="no-cache")
        self.cycle(now=120)
        result = inspect_state(self.state, source="/setup", now=121)
        self.assertEqual(result["findings"][0]["status"], "needs_reread")
        self.assertEqual(result["findings"][0]["created_at"], 100)
        self.assertIn("Python 3.12", result["source"]["text"])

    def test_missing_or_corrupt_body_is_unknown_then_sync_recovers(self):
        path = Path(str(self.state) + ".pages") / read_state(self.state)["pages"]["/setup"]
        for damage in ("missing", "corrupt"):
            with self.subTest(damage=damage):
                if damage == "missing":
                    path.unlink()
                else:
                    path.write_bytes(b"corrupt")
                result = inspect_state(self.state, source="/setup", now=110)
                self.assertEqual(result["findings"][0]["status"], "unknown")
                self.assertFalse(result["source"]["retained"])
                self.assertIsNone(result["source"]["text"])
                self.cycle(now=111)
                self.assertEqual(inspect_state(self.state, now=112)["findings"][0]["status"], "usable")

    def test_failed_sync_does_not_let_retained_bytes_hide_failed_source(self):
        self.origin.routes["/setup"] = (503, b"try later")
        self.assertFalse(self.cycle(now=110)["complete"])
        result = inspect_state(self.state, now=111)
        self.assertTrue(result["sources"]["/setup"]["retained"])
        self.assertEqual(result["findings"][0]["sourceStatus"], "unknown")

    def test_legacy_cache_inspection_requires_sync_without_silent_migration(self):
        legacy = empty_state()
        legacy.update(site_rev=1, etag='"legacy"')
        save_state(self.state, legacy)
        before = self.state.read_bytes()
        with self.assertRaisesRegex(ValueError, "run-sync-before-inspect-legacy-cache"):
            inspect_state(self.state, now=110)
        self.assertEqual(self.state.read_bytes(), before)
        self.origin.manifest({"/setup": entry(1, b"<p>Requires Python 3.9 or newer.</p>")})
        self.assertTrue(self.cycle(now=110)["complete"])
        self.assertEqual(inspect_state(self.state, now=111)["findings"], [])
        self.assertIn("/setup", inspect_state(self.state, now=111)["sources"])

    def test_cli_errors_are_clear_and_do_not_create_or_replace_state(self):
        cases = [
            (["--id", "absent"], "finding-not-found"),
            (["--source", "/absent"], "source-not-found"),
        ]
        for extra, message in cases:
            out, err = io.StringIO(), io.StringIO()
            code = cli.main(["inspect", str(self.state), *extra], stdout=out, stderr=err)
            self.assertEqual(code, 1)
            self.assertIn(message, err.getvalue())
            self.assertEqual(out.getvalue(), "")
        self.state.write_text("{broken")
        out, err = io.StringIO(), io.StringIO()
        self.assertEqual(cli.main(["inspect", str(self.state)], stdout=out, stderr=err), 1)
        self.assertEqual(self.state.read_text(), "{broken")
        self.state.unlink()
        self.assertEqual(cli.main(["inspect", str(self.state)], stdout=out, stderr=err), 1)
        self.assertFalse(self.state.exists())

    def test_cli_prints_saved_answer_as_json(self):
        out, err = io.StringIO(), io.StringIO()
        with patch("pagedigest.recurring.time.time", return_value=110):
            code = cli.main(["inspect", str(self.state), "--id", "python"], stdout=out, stderr=err)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())["findings"][0]["status"], "usable")
        self.assertEqual(err.getvalue(), "")

    def test_malformed_saved_policy_resource_or_finding_refuses_without_writes(self):
        original = self.state.read_bytes()
        mutations = [
            lambda state: state.update(max_age="60"),
            lambda state: state["resources"]["/setup"].update(validated_at=True),
            lambda state: state["findings"]["python"].update(created_at="yesterday"),
            lambda state: state["findings"]["python"]["sources"].update({"/setup": "sha256:broken"}),
            lambda state: state.update(last_attempt=None),
        ]
        for mutation in mutations:
            state = json.loads(original)
            mutation(state)
            self.state.write_text(json.dumps(state))
            before = self.state.read_bytes()
            with self.assertRaises(ValueError):
                inspect_state(self.state, now=110)
            self.assertEqual(self.state.read_bytes(), before)

    def test_active_writer_lock_refuses_without_changing_it(self):
        lock = Path(str(self.state) + ".lock")
        lock.write_text("another writer")
        with self.assertRaisesRegex(ValueError, "workflow-is-being-written"):
            inspect_state(self.state, now=110)
        self.assertEqual(lock.read_text(), "another writer")


if __name__ == "__main__":
    unittest.main()
