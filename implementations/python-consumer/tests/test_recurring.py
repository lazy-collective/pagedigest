from __future__ import annotations

import contextlib
import io
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

import requests

from pagedigest import cli
from pagedigest.recurring import digest, read_state, remember, sync


class Response:
    def __init__(self, status=200, body=b"", headers=None):
        self.status_code, self.body = status, body
        self.headers = requests.structures.CaseInsensitiveDict(headers or {})
        self.closed = False

    def iter_content(self, chunk_size):
        for offset in range(0, len(self.body), chunk_size):
            yield self.body[offset : offset + chunk_size]

    def close(self):
        self.closed = True


class Origin:
    def __init__(self):
        self.routes = {}
        self.calls = []

    def get(self, url, **kwargs):
        path = urlsplit(url).path
        self.calls.append((path, kwargs))
        action = self.routes.get(path)
        if isinstance(action, Exception):
            raise action
        if callable(action):
            return action(kwargs["headers"])
        return Response(*(action or (404, b"")))

    def page(self, path, body, *, etag=None, cache="max-age=30", extra=None):
        headers = {"Cache-Control": cache, **(extra or {})}
        if etag:
            headers["ETag"] = etag

        def response(request):
            if etag and request.get("If-None-Match") == etag:
                return Response(304, headers=headers)
            return Response(200, body, headers)

        self.routes[path] = response

    def manifest(self, entries, rev=1, coverage="complete", conditional=False):
        body = json.dumps(
            {
                "version": 1,
                "generated": "2026-11-02T12:00:00Z",
                "site_rev": rev,
                "coverage": {"mode": coverage, **({"prefixes": ["/docs/"]} if coverage == "prefixes" else {})},
                "entries": entries,
            }
        ).encode()
        self.routes["/.well-known/pagedigest.json"] = lambda headers: Response(
            304 if conditional and headers.get("If-None-Match") == str(rev) else 200,
            b"" if conditional and headers.get("If-None-Match") == str(rev) else body,
            {"ETag": str(rev)},
        )


class RecurringTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name) / "cache.json"
        self.origin = Origin()

    def cycle(self, now=100, **kw):
        return sync(
            "https://example.com", self.state, session=self.origin, now=now, audit_rate=kw.pop("audit_rate", 0), **kw
        )

    def test_http_freshness_then_change_invalidates_only_affected_finding(self):
        self.origin.page("/a", b"one", etag='"a1"')
        self.origin.page("/b", b"two", etag='"b1"')
        first = self.cycle(urls=["/a", "/b"], http_only=True)
        self.assertTrue(first["complete"])
        self.assertEqual(first["new"], ["/a", "/b"])
        remember(self.state, "a-note", "A conclusion", ["/a"], now=100)
        remember(self.state, "b-note", "B conclusion", ["/b"], now=100)
        warm = self.cycle(now=110, http_only=True)
        self.assertEqual(warm["requests"], 0)
        self.assertEqual([f["status"] for f in warm["findings"]], ["usable", "usable"])
        self.origin.page("/a", b"new one", etag='"a2"')
        changed = self.cycle(now=150, http_only=True)
        self.assertEqual(changed["changed"], ["/a"])
        self.assertEqual(changed["revalidated"], ["/b"])
        self.assertEqual([f["status"] for f in changed["findings"]], ["needs_reread", "usable"])
        self.assertEqual(read_state(self.state)["findings"]["a-note"]["text"], "A conclusion")

    def test_ordinary_http_fallback_and_sitemap_discovery(self):
        self.origin.routes["/sitemap.xml"] = (
            200,
            b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.com/a</loc><lastmod>2026-11-01</lastmod></url></urlset>',
        )
        self.origin.page("/a", b"source", etag="one")
        first = self.cycle(sitemap="/sitemap.xml")
        self.assertTrue(first["complete"])
        self.assertEqual(first["signal"], "http")
        self.assertEqual(first["new"], ["/a"])
        self.assertEqual(first["requests"], 3)
        self.origin.routes["/sitemap.xml"] = (200, b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"/>')
        second = self.cycle(now=110)
        self.assertTrue(second["complete"])
        self.assertEqual(second["removed"], [])
        self.assertIn("/a", read_state(self.state)["pages"])

    def test_manifest304_never_replaces_a_missing_body(self):
        self.origin.page("/a", b"one", cache="")
        self.origin.manifest({"/a": {"rev": 1, "digest": digest(b"one")}}, conditional=True)
        self.assertTrue(self.cycle()["complete"])
        state = read_state(self.state)
        (Path(str(self.state) + ".pages") / state["pages"]["/a"]).unlink()
        report = self.cycle(now=101)
        self.assertTrue(report["complete"])
        self.assertEqual(report["requests"], 2)
        self.assertEqual(report["reused"], [])
        self.assertEqual(read_state(self.state)["body_hashes"]["/a"], digest(b"one"))

    def test_explicit_scope_does_not_expand_to_whole_large_site(self):
        self.origin.manifest({f"/doc/{index}": {"rev": 1} for index in range(400)})
        self.origin.page("/doc/7", b"selected")
        first = self.cycle(urls=["/doc/7"])
        self.assertTrue(first["complete"])
        self.assertEqual(first["new"], ["/doc/7"])
        self.assertEqual(first["requests"], 2)
        repeated = self.cycle(now=101)
        self.assertTrue(repeated["complete"])
        self.assertEqual(repeated["requests"], 1)
        self.assertEqual(set(read_state(self.state)["pages"]), {"/doc/7"})

    def test_narrowing_scope_keeps_finding_evidence_without_claiming_deletion(self):
        self.origin.page("/a", b"one")
        self.origin.page("/b", b"two")
        self.cycle(urls=["/a", "/b"], http_only=True)
        remember(self.state, "b", "B finding", ["/b"], now=100)
        report = self.cycle(now=101, urls=["/a"], http_only=True)
        self.assertTrue(report["complete"])
        self.assertEqual(report["out_of_scope"], ["/b"])
        self.assertEqual(report["removed"], [])
        self.assertEqual(report["findings"][0]["status"], "unknown")
        self.assertTrue((Path(str(self.state) + ".pages") / (digest(b"two")[7:] + ".body")).exists())

    def test_deadline_revalidates_even_with_unchanged_manifest(self):
        self.origin.page("/a", b"one", etag="a", cache="")
        self.origin.manifest({"/a": {"rev": 1}}, conditional=True)
        self.cycle(max_age=60)
        warm = self.cycle(now=120, max_age=60)
        self.assertEqual(warm["requests"], 1)
        deadline = self.cycle(now=160, max_age=60)
        self.assertEqual(deadline["requests"], 2)
        self.assertEqual(deadline["revalidated"], ["/a"])

    def test_audit_failure_marks_affected_findings_unknown_and_recovers(self):
        self.origin.page("/a", b"one", cache="")
        self.origin.page("/b", b"two", cache="")
        self.origin.manifest({"/a": {"rev": 1}, "/b": {"rev": 1}}, conditional=True)
        self.cycle()
        remember(self.state, "a-note", "One", ["/a"], now=100)
        remember(self.state, "b-note", "Two", ["/b"], now=100)
        self.origin.page("/a", b"concealed change", cache="")
        failed = self.cycle(now=101, audit_rate=1)
        self.assertFalse(failed["complete"])
        self.assertEqual([f["status"] for f in failed["findings"]], ["unknown", "usable"])
        self.assertTrue(read_state(self.state)["distrusted"])
        self.assertEqual(read_state(self.state)["body_hashes"]["/a"], digest(b"one"))
        self.origin.manifest({"/a": {"rev": 2}, "/b": {"rev": 1}}, rev=2)
        recovered = self.cycle(now=102)
        self.assertTrue(recovered["complete"])
        self.assertEqual(recovered["changed"], ["/a"])
        self.assertFalse(read_state(self.state)["distrusted"])

    def test_partial_manifest_does_not_delete_unlisted_source(self):
        self.origin.page("/a", b"one", etag="a", cache="")
        self.cycle(urls=["/a"], http_only=True)
        self.origin.manifest({"/docs/b": {"rev": 1}}, coverage="prefixes")
        self.origin.page("/docs/b", b"two", cache="")
        report = self.cycle(now=200)
        self.assertTrue(report["complete"])
        self.assertEqual(report["removed"], [])
        self.assertEqual(report["revalidated"], ["/a"])

    def test_failed_audit_cannot_restore_old_http_fresh_bytes_as_usable(self):
        self.origin.page("/a", b"one", cache="max-age=3600")
        self.origin.manifest({"/a": {"rev": 1}}, conditional=True)
        self.cycle()
        remember(self.state, "note", "From old bytes", ["/a"], now=100)
        self.origin.page("/a", b"changed", cache="max-age=3600")
        failed = self.cycle(now=101, audit_rate=1)
        self.assertFalse(failed["complete"])
        self.assertEqual(read_state(self.state)["suspect"], ["/a"])
        recovered = self.cycle(now=102)
        self.assertTrue(recovered["complete"])
        self.assertEqual(recovered["requests"], 2)
        self.assertEqual(recovered["signal"], "http")
        self.assertEqual(recovered["changed"], ["/a"])
        self.assertEqual(recovered["findings"][0]["status"], "needs_reread")
        self.assertEqual(read_state(self.state)["suspect"], [])
        self.assertTrue(read_state(self.state)["distrusted"])

    def test_failures_keep_previous_bytes_and_count_incomplete_attempts(self):
        self.origin.page("/a", b"one", cache="no-cache")
        self.cycle(urls=["/a"], http_only=True)
        remember(self.state, "a", "source-dependent", ["/a"], now=100)
        self.origin.routes["/a"] = requests.ConnectionError("offline")
        report = self.cycle(now=101, http_only=True)
        self.assertFalse(report["complete"])
        self.assertEqual(report["requests"], 1)
        self.assertEqual(report["http"][0]["status"], None)
        self.assertEqual(report["findings"][0]["status"], "unknown")
        self.assertEqual(read_state(self.state)["body_hashes"]["/a"], digest(b"one"))
        with self.assertRaisesRegex(ValueError, "source-must-be"):
            remember(self.state, "bad", "cannot claim current", ["/a"], now=101)

    def test_http_cache_restrictions_and_unsupported_variants_refuse(self):
        for headers in (
            {"Cache-Control": "no-store"},
            {"Cache-Control": "private"},
            {"Vary": "Cookie"},
            {"Set-Cookie": "x=y"},
        ):
            with self.subTest(headers=headers):
                self.origin.page("/a", b"sensitive", extra=headers)
                report = self.cycle(urls=["/a"], http_only=True)
                self.assertFalse(report["complete"])
                self.assertNotIn("/a", read_state(self.state)["pages"])

    def test_representations_never_share_findings(self):
        self.origin.page("/a", b"same text", extra={"Vary": "Accept-Language"})
        self.cycle(urls=["/a"], http_only=True, language="en")
        remember(self.state, "note", "language-bound", ["/a"], now=100)
        report = self.cycle(now=101, http_only=True, language="fr")
        self.assertTrue(report["complete"])
        self.assertEqual(report["findings"][0]["status"], "unknown")
        self.assertEqual(report["findings"][0]["problems"][0]["reason"], "representation-changed")

    def test_supplied_session_cannot_add_unbound_or_authenticated_representation(self):
        for auth, headers in (
            (("user", "secret"), {}),
            (None, {"Authorization": "secret"}),
            (None, {"Cookie": "session=secret"}),
            (None, {"X-Tenant": "private"}),
        ):
            with self.subTest(headers=headers, has_auth=bool(auth)), requests.Session() as session:
                session.auth = auth
                session.headers.update(headers)
                with self.assertRaises(ValueError):
                    sync("https://example.com", self.state, urls=["/a"], session=session)
                self.assertFalse(self.state.exists())

    def test_request_budget_preserves_partial_completion(self):
        self.origin.page("/a", b"one")
        self.origin.page("/b", b"two")
        report = self.cycle(urls=["/a", "/b"], http_only=True, max_requests=1)
        self.assertFalse(report["complete"])
        self.assertEqual(report["requests"], 1)
        self.assertEqual(report["new"], ["/a"])
        self.assertEqual(read_state(self.state)["last_attempt"]["available"], ["/a"])
        self.assertEqual(report["errors"][0]["reason"], "request-budget-exhausted")

    def test_repeated_changes_prune_unreferenced_bodies_but_keep_finding_sources(self):
        self.origin.page("/a", b"original", cache="no-cache")
        self.cycle(urls=["/a"], http_only=True)
        remember(self.state, "history", "Original observation", ["/a"], now=100)
        for index in range(4):
            self.origin.page("/a", f"change{index}".encode(), cache="no-cache")
            self.assertTrue(self.cycle(now=101 + index, http_only=True)["complete"])
        bodies = list(Path(str(self.state) + ".pages").glob("*.body"))
        self.assertEqual({path.read_bytes() for path in bodies}, {b"original", b"change3"})

    def test_retained_cache_budget_refuses_growth_without_advancing_source(self):
        self.origin.page("/a", b"one", cache="no-cache")
        self.cycle(urls=["/a"], http_only=True)
        self.origin.page("/a", b"larger", cache="no-cache")
        with patch("pagedigest.recurring.MAX_CACHE_BYTES", 5):
            report = self.cycle(now=101, http_only=True)
        self.assertFalse(report["complete"])
        self.assertEqual(report["errors"][0]["reason"], "retained-body-cache-budget-exhausted")
        self.assertEqual(read_state(self.state)["body_hashes"]["/a"], digest(b"one"))

    def test_failed_audit_or_304_does_not_renew_freshness(self):
        self.origin.page("/a", b"one", etag="a", cache="")
        self.origin.manifest({"/a": {"rev": 1, "digest": digest(b"one")}}, conditional=True)
        self.cycle()
        self.origin.routes["/a"] = (304, b"")
        report = self.cycle(now=101, audit_rate=1)
        self.assertFalse(report["complete"])
        self.assertEqual(read_state(self.state)["resources"]["/a"]["validated_at"], 100)
        self.assertEqual(report["errors"][0]["reason"], "304-without-valid-conditional-body")

    def test_exact_source_absence_invalidates_finding(self):
        self.origin.page("/a", b"one", cache="no-cache")
        self.cycle(urls=["/a"], http_only=True)
        remember(self.state, "a", "One", ["/a"], now=100)
        self.origin.routes["/a"] = (410, b"")
        report = self.cycle(now=101, http_only=True)
        self.assertEqual(report["removed"], ["/a"])
        self.assertEqual(report["findings"][0]["status"], "unknown")

    def test_cross_origin_sitemap_never_fetches_foreign_page(self):
        self.origin.routes["/sitemap.xml"] = (200, b"<urlset><url><loc>https://other.example/a</loc></url></urlset>")
        report = self.cycle(sitemap="/sitemap.xml", http_only=True)
        self.assertFalse(report["complete"])
        self.assertEqual(report["requests"], 1)
        self.assertEqual([p for p, _ in self.origin.calls], ["/sitemap.xml"])

    def test_cli_outputs_machine_readable_partial_and_saved_findings(self):
        self.origin.page("/a", b"one")
        out, err = io.StringIO(), io.StringIO()
        with patch("pagedigest.recurring.requests.Session", return_value=self.origin):
            self.origin.close = lambda: None
            code = cli.main(["sync", "https://example.com", str(self.state), "--url", "/a", "--http-only"], out, err)
        self.assertEqual(code, 0, err.getvalue())
        self.assertTrue(json.loads(out.getvalue())["complete"])
        note = Path(self.temp.name) / "note.txt"
        note.write_text("Finding from /a")
        out = io.StringIO()
        code = cli.main(
            ["remember", str(self.state), "--id", "note", "--text-file", str(note), "--source", "/a"], out, err
        )
        self.assertEqual(code, 0, err.getvalue())
        self.assertEqual(json.loads(out.getvalue())["status"], "retained")

    def test_must_revalidate_does_not_block_reuse_while_fresh(self):
        self.origin.page("/a", b"one", etag='"a1"', cache="max-age=30, must-revalidate")
        self.assertTrue(self.cycle(urls=["/a"], http_only=True)["complete"])
        warm = self.cycle(now=110, http_only=True)
        self.assertEqual(warm["requests"], 0)
        self.assertEqual(warm["reused"], [{"url": "/a", "basis": "http-freshness"}])
        stale = self.cycle(now=140, http_only=True)
        self.assertEqual(stale["requests"], 1)
        self.assertEqual(stale["revalidated"], ["/a"])

    def test_http_only_no_cache_revalidates_every_cycle(self):
        self.origin.page("/a", b"one", etag='"a1"', cache="no-cache")
        self.cycle(urls=["/a"], http_only=True)
        warm = self.cycle(now=101, http_only=True)
        self.assertEqual(warm["requests"], 1)
        self.assertEqual(warm["revalidated"], ["/a"])

    def test_unchanged_manifest_entry_is_origin_validation(self):
        # SPEC 5.1.2: an unchanged covered entry in a validated manifest is the
        # origin's validation, even for no-cache or expired must-revalidate pages.
        self.origin.page("/a", b"one", etag='"a1"', cache="no-cache")
        self.origin.page("/b", b"two", cache="max-age=30, must-revalidate")
        self.origin.manifest({"/a": {"rev": 1}, "/b": {"rev": 1}}, conditional=True)
        cold = self.cycle()
        self.assertTrue(cold["complete"])
        self.assertEqual(cold["requests"], 3)
        remember(self.state, "a-note", "A conclusion", ["/a"], now=100)
        warm = self.cycle(now=200)
        self.assertTrue(warm["complete"])
        self.assertEqual(warm["requests"], 1)
        self.assertEqual(
            warm["reused"],
            [{"url": "/a", "basis": "pagedigest-unchanged"}, {"url": "/b", "basis": "pagedigest-unchanged"}],
        )
        self.assertEqual(warm["findings"][0]["status"], "usable")
        self.origin.page("/a", b"changed", etag='"a2"', cache="no-cache")
        self.origin.manifest({"/a": {"rev": 2}, "/b": {"rev": 1}}, rev=2, conditional=True)
        changed = self.cycle(now=210)
        self.assertEqual(changed["changed"], ["/a"])
        self.assertEqual(changed["reused"], [{"url": "/b", "basis": "pagedigest-unchanged"}])
        self.assertEqual(changed["findings"][0]["status"], "needs_reread")
        self.assertEqual(changed["requests"], 2)

    def test_prefix_limits_discovery_from_a_large_manifest(self):
        entries = {f"/doc/{index}": {"rev": 1} for index in range(400)}
        entries.update({f"/api/{index}": {"rev": 1} for index in range(3)})
        self.origin.manifest(entries)
        for index in range(3):
            self.origin.page(f"/api/{index}", f"api {index}".encode())
        refused = self.cycle()
        self.assertFalse(refused["complete"])
        self.assertIn("--prefix", refused["errors"][0]["reason"])
        first = self.cycle(now=101, prefixes=["/api/"])
        self.assertTrue(first["complete"])
        self.assertEqual(first["new"], ["/api/0", "/api/1", "/api/2"])
        self.assertEqual(first["requests"], 4)
        repeated = self.cycle(now=200)
        self.assertTrue(repeated["complete"])
        self.assertEqual(repeated["prefixes"], ["/api/"])
        self.assertEqual(repeated["requests"], 1)
        self.assertEqual(len(repeated["reused"]), 3)
        with self.assertRaises(ValueError):
            self.cycle(now=201, prefixes=["api/"])

    def test_real_http_cycle_and_cli_reuses_derived_result(self):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                if self.path != "/doc":
                    self.send_response(404)
                    self.end_headers()
                    return
                body = b"Observed public document"
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "max-age=60")
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            cold = sync(base, self.state, urls=["/doc"], http_only=True, audit_rate=0)
            self.assertTrue(cold["complete"])
            self.assertEqual(cold["requests"], 1)
            remember(self.state, "real", "Read the document", ["/doc"])
            warm = sync(base, self.state, http_only=True, audit_rate=0)
            self.assertTrue(warm["complete"])
            self.assertEqual(warm["requests"], 0)
            self.assertEqual(warm["findings"][0]["status"], "usable")
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    with contextlib.redirect_stdout(io.StringIO()):
        unittest.main()
