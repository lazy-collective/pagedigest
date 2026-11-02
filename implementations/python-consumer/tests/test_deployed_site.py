from __future__ import annotations

import hashlib
import io
import json
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from test_core import load_tool


class DeploymentGateTests(unittest.TestCase):
    def setUp(self):
        self.tool = load_tool("verify_deployed_site")
        self.body = b"<html>intended content</html>"
        self.manifest = {
            "version": 1,
            "generated": "2026-11-02T00:00:00Z",
            "site_rev": 14,
            "coverage": {"mode": "complete"},
            "entries": {"/": {"rev": 12, "digest": "sha256:" + hashlib.sha256(self.body).hexdigest()}},
        }
        self.expected = json.dumps(self.manifest).encode()
        self.served_manifest = self.expected
        self.bodies = [self.body] * 6
        self.page_status = 200
        self.encoding = None
        self.no_transform = True
        self.inject_without_accept = False
        self.requests = []
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                fixture.requests.append((self.path, self.headers.get("Accept-Encoding"), self.headers.get("Accept")))
                is_manifest = self.path == "/.well-known/pagedigest.json"
                body = fixture.served_manifest if is_manifest else fixture.bodies.pop(0)
                if not is_manifest and fixture.inject_without_accept and self.headers.get("Accept") is None:
                    body += b"<script>injected</script>"
                self.send_response(200 if is_manifest else fixture.page_status)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Content-Type", "application/json" if is_manifest else "text/html; charset=utf-8")
                if fixture.no_transform:
                    self.send_header("Cache-Control", "public, no-transform")
                if not is_manifest and fixture.encoding:
                    self.send_header("Content-Encoding", fixture.encoding)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close)
        self.origin = f"http://127.0.0.1:{self.server.server_port}"

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_exact_complete_snapshot_twice(self):
        result = self.tool.verify(self.origin, self.expected)
        self.assertEqual(result["site_rev"], 14)
        self.assertEqual(len(result["observations"]), 6)
        self.assertEqual(len(self.requests), 15)
        self.assertTrue(all(encoding == "identity" for _, encoding, _ in self.requests))
        self.assertEqual({accept for _, _, accept in self.requests}, {None, "*/*", "text/html"})

    def test_accept_dependent_injection_is_not_hidden_by_default_client(self):
        self.inject_without_accept = True
        with self.assertRaisesRegex(ValueError, "audit-no-accept:.*digest mismatch"):
            self.tool.verify(self.origin, self.expected)

    def test_matching_html_still_requires_prevention_header(self):
        self.no_transform = False
        with self.assertRaisesRegex(ValueError, "no-transform"):
            self.tool.verify(self.origin, self.expected)

    def test_same_revision_is_not_exact_manifest_identity(self):
        self.served_manifest = self.expected + b"\n"
        with self.assertRaisesRegex(ValueError, "exact intended manifest"):
            self.tool.verify(self.origin, self.expected)
        self.assertEqual(len(self.requests), 1)

    def test_new_manifest_with_old_page_fails(self):
        self.bodies = [b"<html>old content</html>"]
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            self.tool.verify(self.origin, self.expected)

    def test_second_pass_mismatch_cannot_hide_behind_first_match(self):
        self.bodies[1] += b"<script>edge transform</script>"
        with self.assertRaisesRegex(ValueError, "pass 2"):
            self.tool.verify(self.origin, self.expected)

    def test_missing_digest_or_partial_coverage_fails_before_requests(self):
        for change in ("digest", "coverage"):
            manifest = json.loads(self.expected)
            if change == "digest":
                del manifest["entries"]["/"]["digest"]
            else:
                del manifest["coverage"]
            with self.assertRaises(ValueError):
                self.tool.verify(self.origin, json.dumps(manifest).encode())
        self.assertEqual(self.requests, [])

    def test_redirect_failure_and_encoding_are_not_verified(self):
        for status, encoding in [(302, None), (503, None), (200, "gzip")]:
            self.page_status, self.encoding = status, encoding
            self.bodies = [self.body]
            with self.assertRaises(ValueError):
                self.tool.verify(self.origin, self.expected)

    def test_size_limit_is_a_failure(self):
        self.bodies = [b"x" * (len(self.expected) + 1)]
        with patch.object(self.tool, "MAX_BYTES", len(self.expected)):
            with self.assertRaisesRegex(ValueError, "exceeds"):
                self.tool.verify(self.origin, self.expected)


class ReconcileObservationsTests(unittest.TestCase):
    def test_first_matching_observation_still_requires_second(self):
        tool = load_tool("reconcile_served_digests")
        for second, status in [("sha256:a", "match"), ("sha256:b", "unstable"), (None, "inconclusive")]:
            with patch.object(
                tool, "fetch_identity_digest", side_effect=[("sha256:a", "ok"), (second, "test")]
            ) as fetch:
                result = tool.reconcile_entry("https://example.com", "/", "sha256:a", 15)
            self.assertEqual(result.status, status)
            self.assertEqual(fetch.call_count, 2)

    def test_inconclusive_does_not_partially_apply(self):
        tool = load_tool("reconcile_served_digests")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            manifest = {
                "version": 1,
                "site_rev": 13,
                "generated": "2026-11-02T00:00:00Z",
                "entries": {key: {"rev": 1, "digest": "sha256:" + "a" * 64} for key in ("/", "/two")},
            }
            path.write_text(json.dumps(manifest))
            before = path.read_bytes()
            outcomes = [
                tool.Reconciliation("/", "stable-transform", "test", "sha256:" + "b" * 64),
                tool.Reconciliation("/two", "inconclusive", "HTTP 503"),
            ]
            with (
                patch("sys.argv", ["reconcile", str(path), "--base-url", "https://example.com", "--apply"]),
                patch.object(tool, "reconcile_entry", side_effect=outcomes),
                redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(tool.main(), 2)
            self.assertEqual(path.read_bytes(), before)
