#!/usr/bin/env python3
"""Run three real read cycles against a tiny local website, without random audits."""

from __future__ import annotations

import hashlib
import io
import json
import tempfile
import threading
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import requests
from cache_persistence import run_cycle

from pagedigest.persistence import load_state


def main() -> None:
    bodies = {"/about": b"About this example.", "/guide": b"Guide, first edition."}
    revisions = {key: 1 for key in bodies}
    requests_seen: list[str] = []

    class Website(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            requests_seen.append(self.path)
            if self.path == "/.well-known/pagedigest.json":
                body = json.dumps(
                    {
                        "version": 1,
                        "generated": "2026-11-04T00:00:00Z",
                        "site_rev": max(revisions.values()),
                        "coverage": {"mode": "complete"},
                        "entries": {
                            key: {
                                "rev": revisions[key],
                                "digest": "sha256:" + hashlib.sha256(value).hexdigest(),
                            }
                            for key, value in bodies.items()
                        },
                    }
                ).encode()
                content_type = "application/json"
            elif self.path in bodies:
                body = bodies[self.path]
                content_type = "text/plain"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)

    with tempfile.TemporaryDirectory(prefix="pagedigest-three-visits-") as temporary:
        cache = Path(temporary)
        with ThreadingHTTPServer(("127.0.0.1", 0), Website) as website, requests.Session() as session:
            # Loopback example traffic must not be routed through an HTTP proxy.
            session.trust_env = False
            serving = threading.Thread(target=website.serve_forever, daemon=True)
            serving.start()
            try:
                for label, expected in (
                    ("First read", ["/about", "/guide"]),
                    ("Nothing changed", []),
                    ("Guide updated", ["/guide"]),
                ):
                    if label == "Guide updated":
                        bodies["/guide"] = b"Guide, revised edition."
                        revisions["/guide"] += 1
                    requests_seen.clear()
                    metrics: dict = {}
                    output = io.StringIO()
                    with redirect_stdout(output):
                        result = run_cycle(
                            f"http://127.0.0.1:{website.server_port}",
                            cache / "state.json",
                            cache / "bodies",
                            session=session,
                            sample_audit_rate=0,
                            metrics=metrics,
                        )
                    if result:
                        raise RuntimeError(output.getvalue())
                    fetched = sorted(metrics["fetched_urls"])
                    assert fetched == expected, (label, fetched, expected)
                    assert requests_seen.count("/.well-known/pagedigest.json") == 1
                    assert sorted(path for path in requests_seen if path in bodies) == expected
                    assert len(requests_seen) == 1 + len(expected)
                    state = load_state(cache / "state.json")
                    for key, value in bodies.items():
                        assert (cache / "bodies" / state["pages"][key]).read_bytes() == value
                    reused = sorted(set(bodies) - set(fetched))
                    print(
                        f"{label}: 1 manifest + {len(fetched)} page requests; "
                        f"fetched {', '.join(fetched) or 'none'}; "
                        f"reused {', '.join(reused) or 'none'}"
                    )
            finally:
                website.shutdown()
                serving.join()


if __name__ == "__main__":
    main()
