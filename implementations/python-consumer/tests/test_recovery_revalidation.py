from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from test_recurring import Origin, Response, entry

from pagedigest.recurring import digest, read_state, remember, sync


class RecoveryRevalidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.case = 0

    def prime(self, etag='"a1"', extra=None, two_pages=False):
        self.case += 1
        self.state = Path(self.temp.name) / f"case-{self.case}.json"
        self.origin = Origin()
        self.origin.page("/a", b"one", etag=etag, extra=extra, cache="no-cache")
        entries = {"/a": entry(1, b"one")}
        if two_pages:
            self.origin.page("/b", b"two", etag='"b1"', cache="no-cache")
            entries["/b"] = entry(1, b"two")
        self.origin.manifest(entries, conditional=True)
        self.assertTrue(self.cycle()["complete"])
        for key in entries:
            remember(self.state, key, f"Original {key}", [key], now=100)
        self.original = read_state(self.state)

    def cycle(self, now=100, **kwargs):
        return sync(
            "https://example.com",
            self.state,
            session=self.origin,
            now=now,
            audit_rate=kwargs.pop("audit_rate", 0),
            **kwargs,
        )

    def page_headers(self, key):
        return [kwargs["headers"] for path, kwargs in self.origin.calls if path == key][-1]

    def assert_original_findings(self):
        self.assertEqual(read_state(self.state)["findings"], self.original["findings"])

    def fail_changed_deployment(self):
        self.origin.manifest({"/a": entry(2, b"new one"), "/b": entry(1, b"two")}, rev=2)
        failed = self.cycle(now=101)
        self.assertFalse(failed["complete"])
        self.assertEqual(failed["errors"], [{"url": "/a", "reason": "pagedigest-digest-audit-mismatch"}])
        self.assertNotIn("/a", failed["revalidated"])
        self.assertEqual([finding["status"] for finding in failed["findings"]], ["unknown", "usable"])
        state = read_state(self.state)
        self.assertEqual(state["resources"]["/a"]["validated_at"], 100)
        self.assertEqual(state["body_hashes"]["/a"], digest(b"one"))
        self.assertEqual(state["suspect"], ["/a"])
        self.assertTrue(state["distrusted"])
        self.assertEqual(state["distrust_site_rev"], 2)
        self.assertEqual(state["site_rev"], 1)
        self.assert_original_findings()
        return failed

    def test_strong304_detects_failed_deployment_and_avoids_unaffected_recovery_bodies(self):
        self.prime(two_pages=True)
        failed = self.fail_changed_deployment()
        self.assertEqual(self.page_headers("/a").get("If-None-Match"), '"a1"')
        # /a's failure sets global distrust before /b is visited in this cycle.
        self.assertEqual(self.page_headers("/b").get("If-None-Match"), '"b1"')
        self.assertEqual([event["status"] for event in failed["http"]], [200, 304, 304])
        self.assertEqual(failed["response_body_bytes"], failed["http"][0]["body_bytes"])

        self.origin.page("/a", b"new one", etag='"a2"', cache="no-cache")
        self.origin.manifest({"/a": entry(3, b"new one"), "/b": entry(1, b"two")}, rev=3)
        recovered = self.cycle(now=102)
        self.assertTrue(recovered["complete"])
        self.assertNotIn("If-None-Match", self.page_headers("/a"))
        self.assertEqual(self.page_headers("/b").get("If-None-Match"), '"b1"')
        self.assertEqual([event["status"] for event in recovered["http"]], [200, 200, 304])
        self.assertEqual(recovered["response_body_bytes"], recovered["http"][0]["body_bytes"] + len(b"new one"))
        self.assertEqual([finding["status"] for finding in recovered["findings"]], ["needs_reread", "usable"])
        self.assertEqual(read_state(self.state)["suspect"], [])
        self.assertFalse(read_state(self.state)["distrusted"])
        self.assert_original_findings()

    def test_same_distrusted_revision_falls_back_to_http_without_restoring_manifest_trust(self):
        self.prime(two_pages=True)
        self.fail_changed_deployment()
        self.origin.page("/a", b"new one", etag='"a2"', cache="no-cache")
        fallback = self.cycle(now=102)
        self.assertTrue(fallback["complete"])
        self.assertEqual(fallback["manifest_fallback"], "previous-audit-failure")
        self.assertEqual(fallback["signal"], "http")
        self.assertNotIn("If-None-Match", self.page_headers("/a"))
        self.assertEqual(self.page_headers("/b").get("If-None-Match"), '"b1"')
        self.assertEqual(fallback["revalidated"], ["/b"])
        self.assertTrue(read_state(self.state)["distrusted"])
        self.assertEqual(read_state(self.state)["site_rev"], 1)
        self.assert_original_findings()

    def test_digestless_revision_bump_can_validate_intact_body_with_strong_etag(self):
        self.prime()
        self.origin.manifest({"/a": {"rev": 2}}, rev=2)
        report = self.cycle(now=101)
        self.assertTrue(report["complete"])
        self.assertEqual(report["revalidated"], ["/a"])
        self.assertEqual(report["changed"], [])
        self.assertEqual(report["findings"][0]["status"], "usable")
        self.assert_original_findings()

    def test_changed_or_distrusted_source_does_not_newly_use_weak_or_malformed_validators(self):
        for distrusted in (False, True):
            for etag in (None, 'W/"semantic"', "bare", '"unclosed', '"has"quote"', '"line\nbreak"', '"delete\x7f"'):
                with self.subTest(distrusted=distrusted, etag=etag):
                    modified = {"Last-Modified": "Wed, 04 Nov 2026 12:00:00 GMT"}
                    self.prime(etag=etag, extra=modified)
                    if distrusted:
                        state = read_state(self.state)
                        state.update(distrusted=True, distrust_site_rev=1)
                        self.state.write_text(json.dumps(state))
                    self.origin.manifest({"/a": entry(2, b"new one")}, rev=2)

                    def serve(headers):
                        # Weak semantic tags and coarse modification times can
                        # legitimately retain validators when exact bytes change.
                        if headers.get("If-None-Match") or headers.get("If-Modified-Since"):
                            return Response(304, headers=modified)
                        return Response(200, b"new one", {"Cache-Control": "no-cache", **modified})

                    self.origin.routes["/a"] = serve
                    report = self.cycle(now=101)
                    self.assertTrue(report["complete"])
                    self.assertEqual(report["changed"], ["/a"])
                    self.assertNotIn("If-None-Match", self.page_headers("/a"))
                    self.assertNotIn("If-Modified-Since", self.page_headers("/a"))
                    self.assert_original_findings()

    def test_changed_hint_audit_still_requires_full_body_and_rejects_unsolicited304(self):
        self.prime()
        self.origin.manifest({"/a": entry(2, b"one")}, rev=2)
        self.origin.routes["/a"] = (304, b"")
        report = self.cycle(now=101, audit_rate=1)
        self.assertFalse(report["complete"])
        self.assertNotIn("If-None-Match", self.page_headers("/a"))
        self.assertEqual(report["errors"][0]["reason"], "304-without-valid-conditional-body")
        self.assertEqual(read_state(self.state)["resources"]["/a"]["validated_at"], 100)
        self.assert_original_findings()

    def test_new_conditional304_without_matching_strong_response_etag_fetches_actual_bytes(self):
        for with_digest in (True, False):
            for response_etag in (None, 'W/"a1"', '"different"', "malformed"):
                with self.subTest(with_digest=with_digest, response_etag=response_etag):
                    self.prime()
                    changed_entry = entry(2, b"new one") if with_digest else {"rev": 2}
                    self.origin.manifest({"/a": changed_entry}, rev=2)

                    def serve(headers):
                        if headers.get("If-None-Match"):
                            response_headers = {"ETag": response_etag} if response_etag is not None else {}
                            return Response(304, headers=response_headers)
                        return Response(200, b"new one", {"ETag": '"a2"', "Cache-Control": "no-cache"})

                    self.origin.routes["/a"] = serve
                    report = self.cycle(now=101)
                    self.assertTrue(report["complete"])
                    self.assertEqual(report["requests"], 3)
                    self.assertEqual([event["status"] for event in report["http"]], [200, 304, 200])
                    self.assertNotIn("If-None-Match", self.page_headers("/a"))
                    self.assertEqual(report["changed"], ["/a"])
                    self.assertEqual(report["findings"][0]["status"], "needs_reread")
                    self.assertEqual(read_state(self.state)["body_hashes"]["/a"], digest(b"new one"))
                    self.assert_original_findings()

    def test_new_conditional304_fallback_is_bounded_and_cannot_accept_another304(self):
        for max_requests, expected_reason in (
            (2, "request-budget-exhausted"),
            (3, "304-without-valid-conditional-body"),
        ):
            with self.subTest(max_requests=max_requests):
                self.prime()
                self.origin.manifest({"/a": {"rev": 2}}, rev=2)
                self.origin.routes["/a"] = (304, b"", {"ETag": 'W/"a1"'})
                report = self.cycle(now=101, max_requests=max_requests)
                self.assertFalse(report["complete"])
                self.assertEqual(report["requests"], max_requests)
                self.assertEqual(report["errors"][0]["reason"], expected_reason)
                self.assertEqual(report["findings"][0]["status"], "unknown")
                self.assertEqual(read_state(self.state)["resources"]["/a"]["validated_at"], 100)
                self.assert_original_findings()
                if max_requests == 3:
                    self.assertNotIn("If-None-Match", self.page_headers("/a"))

    def test_lost_or_corrupt_body_cannot_be_restored_by_strong304(self):
        for missing in (True, False):
            with self.subTest(missing=missing):
                self.prime()
                body_path = Path(str(self.state) + ".pages") / self.original["pages"]["/a"]
                if missing:
                    body_path.unlink()
                else:
                    body_path.write_bytes(b"corrupt")
                self.origin.manifest({"/a": entry(2, b"one")}, rev=2)
                self.origin.routes["/a"] = (304, b"")
                refused = self.cycle(now=101)
                self.assertFalse(refused["complete"])
                self.assertNotIn("If-None-Match", self.page_headers("/a"))
                self.assertEqual(refused["findings"][0]["status"], "unknown")
                self.origin.page("/a", b"one", etag='"a1"', cache="no-cache")
                recovered = self.cycle(now=102)
                self.assertTrue(recovered["complete"])
                self.assertNotIn("If-None-Match", self.page_headers("/a"))
                self.assertEqual(recovered["findings"][0]["status"], "usable")
                self.assert_original_findings()

    def test_new_conditional304_still_enforces_response_retention_policy(self):
        for headers in (
            {"Cache-Control": "no-store"},
            {"Cache-Control": "private"},
            {"Set-Cookie": "private=value"},
            {"Vary": "Cookie"},
        ):
            with self.subTest(headers=headers):
                self.prime()
                self.origin.manifest({"/a": entry(2, b"one")}, rev=2)
                self.origin.routes["/a"] = (304, b"", headers)
                report = self.cycle(now=101)
                self.assertFalse(report["complete"])
                self.assertEqual(self.page_headers("/a").get("If-None-Match"), '"a1"')
                self.assertNotEqual(report["errors"][0]["reason"], "304-without-valid-conditional-body")
                self.assertEqual(read_state(self.state)["resources"]["/a"]["validated_at"], 100)
                self.assertEqual(report["findings"][0]["status"], "unknown")
                self.assertEqual(report["revalidated"], [])
                self.assert_original_findings()

    def test_changed_hint_revalidation_keeps_request_budget_and_deadline(self):
        self.prime()
        self.origin.manifest({"/a": entry(2, b"one")}, rev=2)
        refused = self.cycle(now=3701, max_requests=1)
        self.assertFalse(refused["complete"])
        self.assertEqual(refused["requests"], 1)
        self.assertEqual(refused["errors"][0]["reason"], "request-budget-exhausted")
        self.assertEqual(read_state(self.state)["resources"]["/a"]["validated_at"], 100)
        self.assertEqual(refused["findings"][0]["status"], "unknown")
        self.assert_original_findings()


if __name__ == "__main__":
    unittest.main()
