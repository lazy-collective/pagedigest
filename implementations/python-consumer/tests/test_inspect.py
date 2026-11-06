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

    def test_brief_projects_selected_finding_without_reducing_checks_or_changing_state(self):
        remember(self.state, "news", "Unrelated news interpretation", ["/news"], now=100)
        before = {p.name: p.read_bytes() for p in self.state.parent.rglob("*") if p.is_file()}
        with patch("pagedigest.recurring.requests.Session", side_effect=AssertionError("unexpected HTTP")):
            full = inspect_state(self.state, finding_id="python", now=110)
            brief = inspect_state(self.state, finding_id="python", brief=True, now=110)
        self.assertEqual(brief["view"], "finding-brief")
        self.assertEqual(brief["findings"], full["findings"])
        self.assertEqual(brief["findings"][0]["original_observed_at"], {"/setup": 100})
        self.assertEqual(brief["sources"], {"/setup": full["sources"]["/setup"]})
        self.assertEqual(brief["last_attempt"]["available"], ["/setup"])
        self.assertEqual(brief["local_integrity_reads"], full["local_integrity_reads"])
        self.assertEqual(brief["local_integrity_bytes"], full["local_integrity_bytes"])
        self.assertNotIn("source", brief)
        self.assertNotIn("read_guidance", full)
        self.assertNotIn("/news", json.dumps(brief))
        self.assertNotIn("Unrelated news interpretation", json.dumps(brief))
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.state.parent.rglob("*") if p.is_file()})

    def test_brief_guidance_identifies_only_changed_binding_for_reread_in_one_response(self):
        text = (
            "Claim: use Python 3.9 or newer. Task scope: local setup with the news context. "
            "Assumption: public default representation. Limitation: no inventory-wide claim. "
            "Attribution: user-authored interpretation of /setup and /news."
        )
        remember(self.state, "combined", text, ["/setup", "/news"], now=100)
        self.origin.page("/setup", b"<p>Requires Python 3.12 or newer.</p>", cache="no-cache")
        self.cycle(now=110)
        before = {p.name: p.read_bytes() for p in self.state.parent.rglob("*") if p.is_file()}
        with patch("pagedigest.recurring.requests.Session", side_effect=AssertionError("unexpected HTTP")):
            brief = inspect_state(self.state, finding_id="combined", brief=True, now=111)
            full = inspect_state(self.state, finding_id="combined", now=111)
        self.assertEqual(
            brief["read_guidance"]["dependencies"],
            {
                "/news": {"action": "no-binding-reread", "reason": "source-binding-current"},
                "/setup": {"action": "read-current-source", "reason": "source-bytes-changed"},
            },
        )
        self.assertEqual(brief["findings"], full["findings"])
        self.assertEqual(brief["findings"][0]["text"], text)
        self.assertEqual(brief["findings"][0]["created_at"], 100)
        self.assertEqual(brief["findings"][0]["original_observed_at"], {"/news": 100, "/setup": 100})
        self.assertEqual(brief["sources"], full["sources"])
        self.assertEqual(brief["sources"]["/setup"]["validated_at"], 110)
        self.assertEqual(brief["sources"]["/setup"]["validation_expires_at"], 170)
        self.assertNotEqual(brief["sources"]["/setup"]["hash"], brief["findings"][0]["sources"]["/setup"])
        self.assertIn("no separate metadata inspection", brief["read_guidance"]["review"])
        self.assertIn("do not verify interpretation", brief["read_guidance"]["review"])
        self.assertEqual(brief["local_integrity_reads"], full["local_integrity_reads"])
        self.assertEqual(brief["local_integrity_bytes"], full["local_integrity_bytes"])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.state.parent.rglob("*") if p.is_file()})
        current = inspect_state(self.state, source="/setup", now=111)
        self.assertIn("Python 3.12", current["source"]["text"])

    def test_brief_guidance_keeps_changed_context_and_unknown_sources_in_read_set(self):
        remember(self.state, "combined", "Setup conclusion with /news context.", ["/setup", "/news"], now=100)
        self.origin.page("/news", b"Context changed without mentioning Python", cache="no-cache")
        self.cycle(now=110)
        brief = inspect_state(self.state, finding_id="combined", brief=True, now=111)
        self.assertEqual(brief["read_guidance"]["dependencies"]["/news"]["action"], "read-current-source")
        self.assertEqual(brief["read_guidance"]["dependencies"]["/setup"]["action"], "no-binding-reread")
        sync(
            "https://example.com",
            self.state,
            urls=["/news"],
            session=self.origin,
            now=120,
            audit_rate=0,
            http_only=True,
            max_age=60,
        )
        brief = inspect_state(self.state, finding_id="combined", brief=True, now=121)
        self.assertEqual(brief["findings"][0]["status"], "needs_reread")
        self.assertEqual(set(brief["read_guidance"]["dependencies"]), {"/setup", "/news"})
        self.assertEqual(brief["read_guidance"]["dependencies"]["/news"]["action"], "read-current-source")
        self.assertEqual(
            brief["read_guidance"]["dependencies"]["/setup"],
            {"action": "validate-or-recover-source", "reason": "source-not-available-in-last-sync"},
        )

    def test_brief_guidance_requires_validation_before_reading_changed_stale_evidence(self):
        self.origin.page("/setup", b"<p>Requires Python 3.12 or newer.</p>", cache="no-cache")
        self.cycle(now=110)
        for now, reason in ((109, "validation-time-in-future"), (170, "validation-expired")):
            with self.subTest(now=now):
                brief = inspect_state(self.state, finding_id="python", brief=True, now=now)
                self.assertEqual(
                    brief["read_guidance"]["dependencies"]["/setup"],
                    {"action": "validate-or-recover-source", "reason": reason},
                )
                self.assertEqual(brief["findings"][0]["status"], "unknown")
                self.assertEqual(brief["sources"]["/setup"]["validated_at"], 110)
                retained = inspect_state(self.state, source="/setup", now=now)
                self.assertIn("Python 3.12", retained["source"]["text"])
                again = inspect_state(self.state, finding_id="python", brief=True, now=now)
                self.assertEqual(brief, again)

    def test_brief_guidance_requires_recovery_when_validation_time_is_missing(self):
        state = read_state(self.state)
        state["resources"]["/setup"].pop("validated_at")
        save_state(self.state, state)
        brief = inspect_state(self.state, finding_id="python", brief=True, now=110)
        self.assertEqual(
            brief["read_guidance"]["dependencies"]["/setup"],
            {"action": "validate-or-recover-source", "reason": "validation-time-missing"},
        )

    def test_brief_preserves_whole_body_change_and_freshness_rules(self):
        def assert_status(now, expected):
            brief = inspect_state(self.state, finding_id="python", brief=True, now=now)
            full = inspect_state(self.state, finding_id="python", now=now)
            self.assertEqual(brief["findings"], full["findings"])
            self.assertEqual(brief["findings"][0]["status"], expected)
            self.assertEqual(brief["findings"][0]["created_at"], 100)
            self.assertEqual(brief["findings"][0]["original_observed_at"], {"/setup": 100})

        self.origin.page("/news", b"Different news", cache="no-cache")
        self.cycle(now=110)
        assert_status(111, "usable")
        # The conclusion remains supported, but even an unrelated footer in a
        # bound page still reopens it: brief mode cannot narrow dependencies.
        self.origin.page("/setup", b"<p>Requires Python 3.9 or newer.</p><footer>Updated</footer>", cache="no-cache")
        self.cycle(now=120)
        assert_status(121, "needs_reread")
        self.origin.page("/setup", b"<p>Requires Python 3.12 or newer.</p>", cache="no-cache")
        self.cycle(now=130)
        assert_status(131, "needs_reread")
        assert_status(129, "unknown")
        assert_status(190, "unknown")

    def test_brief_preserves_failed_source_and_discloses_other_cycle_errors(self):
        self.origin.routes["/news"] = (503, b"unavailable")
        self.assertFalse(self.cycle(now=110)["complete"])
        brief = inspect_state(self.state, finding_id="python", brief=True, now=111)
        self.assertEqual(brief["findings"][0]["status"], "usable")
        self.assertFalse(brief["last_attempt"]["complete"])
        self.assertEqual(brief["last_attempt"]["other_error_count"], 1)
        self.assertEqual(brief["last_attempt"]["errors"], [])
        self.assertEqual(brief["read_guidance"]["dependencies"]["/setup"]["action"], "no-binding-reread")
        self.assertNotIn("/news", json.dumps(brief))
        self.origin.routes["/setup"] = (503, b"unavailable")
        self.assertFalse(self.cycle(now=120)["complete"])
        brief = inspect_state(self.state, finding_id="python", brief=True, now=121)
        self.assertEqual(brief["findings"][0]["status"], "unknown")
        self.assertEqual(brief["last_attempt"]["errors"][0]["url"], "/setup")
        self.assertEqual(brief["last_attempt"]["other_error_count"], 1)
        self.assertEqual(
            brief["read_guidance"]["dependencies"]["/setup"],
            {"action": "validate-or-recover-source", "reason": "source-not-available-in-last-sync"},
        )

    def test_brief_never_hides_missing_corrupt_or_differently_represented_evidence(self):
        state_bytes = self.state.read_bytes()
        state = read_state(self.state)
        path = Path(str(self.state) + ".pages") / state["pages"]["/setup"]
        body = path.read_bytes()
        for damage in ("missing", "corrupt", "representation"):
            with self.subTest(damage=damage):
                if damage == "missing":
                    path.unlink()
                elif damage == "corrupt":
                    path.write_bytes(b"corrupt")
                else:
                    state["representation"] = "another representation"
                    save_state(self.state, state)
                brief = inspect_state(self.state, finding_id="python", brief=True, now=110)
                self.assertEqual(brief["findings"][0]["status"], "unknown")
                self.assertTrue(brief["findings"][0]["problems"])
                self.assertEqual(
                    brief["read_guidance"]["dependencies"]["/setup"],
                    {
                        "action": "validate-or-recover-source",
                        "reason": "representation-changed" if damage == "representation" else "body-missing-or-corrupt",
                    },
                )
                if damage != "representation":
                    self.assertFalse(brief["sources"]["/setup"]["retained"])
                path.write_bytes(body)
                self.state.write_bytes(state_bytes)

    def test_brief_retains_global_errors_and_refuses_malformed_unselected_state(self):
        state = read_state(self.state)
        state["last_attempt"]["complete"] = False
        state["last_attempt"]["errors"] = [{"url": None, "reason": "global failure"}]
        save_state(self.state, state)
        brief = inspect_state(self.state, finding_id="python", brief=True, now=110)
        self.assertEqual(brief["last_attempt"]["errors"], [{"url": None, "reason": "global failure"}])
        self.assertEqual(brief["last_attempt"]["other_error_count"], 0)
        self.assertFalse(brief["last_attempt"]["complete"])
        self.assertEqual(brief["read_guidance"]["dependencies"]["/setup"]["action"], "no-binding-reread")
        state["resources"]["/news"]["validated_at"] = "invalid"
        save_state(self.state, state)
        before = self.state.read_bytes()
        with self.assertRaisesRegex(ValueError, "invalid-saved-resource-time"):
            inspect_state(self.state, finding_id="python", brief=True, now=110)
        self.assertEqual(before, self.state.read_bytes())

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
            (["--brief"], "brief-inspection-requires-finding-id"),
            (["--brief", "--id", "python", "--source", "/setup"], "brief-inspection-excludes-source-body"),
            (["--brief", "--id", "absent"], "finding-not-found"),
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

    def test_cli_brief_prints_selected_finding_with_integrity_and_age(self):
        out, err = io.StringIO(), io.StringIO()
        with patch("pagedigest.recurring.time.time", return_value=110):
            code = cli.main(["inspect", str(self.state), "--id", "python", "--brief"], stdout=out, stderr=err)
        self.assertEqual(code, 0)
        result = json.loads(out.getvalue())
        self.assertEqual(result["view"], "finding-brief")
        self.assertEqual(result["findings"][0]["status"], "usable")
        self.assertEqual(result["local_integrity_reads"], 2)
        self.assertEqual(result["sources"]["/setup"]["validated_at"], 100)
        self.assertEqual(set(result["sources"]), {"/setup"})
        self.assertEqual(
            result["read_guidance"]["dependencies"]["/setup"],
            {"action": "no-binding-reread", "reason": "source-binding-current"},
        )
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
