"""One bounded local completed-workflow control, compared with the same HTTP cache.

Developer-defined fixture after source exposure; no independent utility, adoption,
model-token or general savings claim. Uses the real publisher and recurring cache.
"""

from __future__ import annotations

import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "implementations/python-consumer")
)
from pagedigest.recurring import digest, read_state, remember, sync  # noqa: E402
from publisher_workflow import prepare  # noqa: E402


def run():
    with tempfile.TemporaryDirectory(prefix="pagedigest-outcome-") as tmp:
        root = Path(tmp)
        build = root / "build"
        docs = build / "docs"
        docs.mkdir(parents=True)
        start = docs / "start.html"
        start.write_text("<h1>Setup</h1><p>Python 3.12 or newer. Install with uv.</p>")
        (docs / "limits.html").write_text(
            "<h1>Limits</h1><p>Public static pages only.</p>"
        )
        publisher = []

        def publish(initialize=False):
            before = time.perf_counter()
            report = prepare(
                build,
                root / "durable-state.json",
                initialize=initialize,
                coverage="complete",
                with_digest=True,
                apply=True,
            )
            assert report["applied"] and not report["clarifications"]
            publisher.append(
                {
                    "elapsedSeconds": time.perf_counter() - before,
                    "changes": report["changes"],
                    "siteRevision": report["siteRevision"],
                    "durableStateBytes": (root / "durable-state.json").stat().st_size,
                }
            )

        publish(True)
        fail = set()

        class Origin(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                key = urlsplit(self.path).path
                path = build / key.lstrip("/")
                status, body = 200, path.read_bytes() if path.is_file() else b""
                if key in fail:
                    status, body = 503, b"temporary origin failure"
                elif not path.is_file():
                    status = 404
                etag = '"' + hashlib.sha256(body).hexdigest() + '"'
                if status == 200 and self.headers.get("If-None-Match") == etag:
                    status, body = 304, b""
                self.send_response(status)
                self.send_header("Cache-Control", "no-cache")
                self.send_header("ETag", etag)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Origin)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        arms = {name: root / (name + ".json") for name in ("pagedigest", "http")}
        reports = []
        try:
            for index, label in enumerate(
                ("cold", "warm", "changed", "lost-body", "failure", "recovery")
            ):
                now = 100 + index * 10
                if label == "warm":
                    publish()
                    assert publisher[-1]["changes"] == {
                        "added": [],
                        "changed": [],
                        "removed": [],
                    }
                if label == "changed":
                    start.write_text(
                        "<h1>Setup</h1><p>Python 3.13 or newer. Install with uv.</p>"
                    )
                    publish()
                if label == "lost-body":
                    for state_path in arms.values():
                        state = read_state(state_path)
                        (
                            Path(str(state_path) + ".pages")
                            / state["pages"]["/docs/limits.html"]
                        ).unlink()
                if label == "failure":
                    fail.add("/docs/start.html")
                if label == "recovery":
                    fail.clear()
                cycle = {}
                for name, state_path in arms.items():
                    before = time.thread_time()
                    report = sync(
                        base,
                        state_path,
                        urls=["/docs/start.html", "/docs/limits.html"],
                        http_only=name == "http",
                        now=now,
                        max_age=60,
                        audit_rate=1 if label in {"failure", "recovery"} else 0,
                        max_requests=5,
                        max_bytes=1024 * 1024,
                    )
                    report["clientThreadCpuSeconds"] = time.thread_time() - before
                    assert report["complete"] is (label != "failure"), report
                    for finding in report["findings"]:
                        expected = (
                            "unknown"
                            if label == "failure" and finding["id"].startswith("setup")
                            else "needs_reread"
                            if finding["id"] == "setup-v1" and index >= 2
                            else "usable"
                        )
                        assert finding["status"] == expected, (label, finding)
                    state = read_state(state_path)
                    for key in state["last_attempt"]["available"]:
                        assert state["body_hashes"][key] == digest(
                            (build / key.lstrip("/")).read_bytes()
                        )
                    if label == "cold":
                        remember(
                            state_path,
                            "setup-v1",
                            "Python 3.12 or newer; install with uv.",
                            ["/docs/start.html"],
                            now=now,
                        )
                        remember(
                            state_path,
                            "limits",
                            "Public static pages only.",
                            ["/docs/limits.html"],
                            now=now,
                        )
                    if label == "changed":
                        remember(
                            state_path,
                            "setup-v2",
                            "Python 3.13 or newer; install with uv.",
                            ["/docs/start.html"],
                            now=now,
                        )
                    cycle[name] = report
                assert cycle["pagedigest"]["findings"] == cycle["http"]["findings"]
                reports.append({"cycle": label, "arms": cycle})
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
        totals = {
            name: {
                field: sum(c["arms"][name][field] for c in reports)
                for field in (
                    "requests",
                    "response_body_bytes",
                    "clientThreadCpuSeconds",
                )
            }
            for name in arms
        }
        return {
            "kind": "developer-defined local workflow control",
            "policy": "Same two source bodies, HTTP cache, 60-second body deadline, forced failure/recovery audits; six cycles, <=5 requests/1 MiB each, no models or external origins.",
            "outcome": "Both arms complete five cycles, retain source-bound setup/limits notes, invalidate only changed setup notes, report the failed cycle incomplete/unknown, and recover. Every available source matches the fixture's current bytes.",
            "publisher": publisher,
            "publisherEffort": "Three existing-helper preparations, each preview plus apply; initial choices: initialize, complete coverage and digests. No second page catalog. Human effort, backup/recovery operations and production deployment are unmeasured.",
            "totals": totals,
            "cycles": reports,
            "limits": "No independent tasks/reviewer/operator, task inference, dollar costs, token measurements, scale or general economic claim. Requests/consumed response-body bytes exclude headers/TLS. Fixture conclusions are supplied by this developer-defined control. Retain earlier negative studies.",
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("refusing to overwrite an earlier result")
    report = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["totals"]))


if __name__ == "__main__":
    main()
