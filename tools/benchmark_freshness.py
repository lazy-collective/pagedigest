"""Owned HTTP fixture for the frozen P1 study, not a general HTTP cache.

The original benchmark remains the exact-byte/persistent-consumer control.
This orchestration uses the reference planner plus an explicit body-validation
deadline. Logical time advances between cycles; CPU and wall time are measured.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import random
import tempfile
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from xml.etree import ElementTree as ET

import requests
from pagedigest import check_site

from benchmark_consumers import fingerprint

PACKET = (
    Path(__file__).resolve().parents[1] / "docs/benchmarks/digest-exchange-p1-20261029"
)


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class Budget:
    seconds: float = 600
    max_requests: int = 100_000
    max_bytes: int = 1 << 30
    started: float = field(default_factory=time.monotonic)
    requests: int = 0
    response_bytes: int = 0

    def admit(self):
        if (
            time.monotonic() - self.started >= self.seconds
            or self.requests >= self.max_requests
        ):
            raise BudgetExceeded("request or wall budget exhausted")
        # Every response in the fixed <=100-page fixture is below 64 KiB.
        # Reserve that upper bound before sending instead of overrunning a cap.
        if self.response_bytes + 65536 > self.max_bytes:
            raise BudgetExceeded("response byte reserve exhausted")
        self.requests += 1

    def receive(self, size):
        self.response_bytes += size
        if self.response_bytes > self.max_bytes:
            raise BudgetExceeded("response byte budget exhausted")


class Session(requests.Session):
    def __init__(self, origin, budget):
        super().__init__()
        self.trust_env = False
        self.owner, self.origin, self.budget = origin, origin.url, budget

    def request(self, method, url, **kwargs):
        if method.upper() != "GET" or not url.startswith(self.origin + "/"):
            raise ValueError("fixture session permits only its loopback GETs")
        self.budget.admit()
        kwargs["allow_redirects"] = False
        kwargs["timeout"] = min(
            5, max(0.01, self.budget.seconds - (time.monotonic() - self.budget.started))
        )
        response = super().request(method, url, **kwargs)
        # Materialize the bounded fixture response before charging its receipt.
        # iter_content() still works for the reference planner's streaming API.
        response.content
        event = self.owner.events[-1]
        self.budget.receive(event["body_bytes"] + event["header_bytes"])
        return response


class Origin:
    def __init__(self, count, budget):
        self.pages = {
            f"/p/{i}": (f"<h1>{i}</h1>" + "stable documentation " * 100).encode()
            for i in range(count)
        }
        self.revs = dict.fromkeys(self.pages, 1)
        self.site_rev = 1
        self.cycle = 0
        self.budget = budget
        self.metrics = {}
        self.metadata = {}
        self.generation = {}
        self.events = []

    def advance(self, cycle):
        self.cycle = cycle
        if cycle in {2, 3}:
            self.pages["/p/0"] += f"<p>change-{cycle}</p>".encode()
            if cycle == 2:
                self.revs["/p/0"] += 1
                self.site_rev += 1
        if cycle == 5:
            del self.pages["/p/0"]
            self.pages["/new"] = b"<h1>new</h1>"
            self.revs["/new"] = 1
            self.site_rev += 1
        if cycle in {7, 8}:
            self.site_rev += 1
        self.generation = dict.fromkeys(["sitemap", "fingerprints", "pagedigest"], 0.0)
        if cycle not in {0, 2, 5, 7, 8}:
            return
        factories = {
            "sitemap": lambda: (
                "<urlset>"
                + "".join(
                    f"<url><loc>{p}</loc><lastmod>{self.revs[p]}</lastmod></url>"
                    for p in self.pages
                )
                + "</urlset>"
            ).encode(),
            "fingerprints": lambda: json.dumps(
                {p: fingerprint(b) for p, b in self.pages.items()}
            ).encode(),
            "pagedigest": lambda: json.dumps(
                {
                    "version": 1,
                    "generated": "2026-10-29T17:00:00Z",
                    "site_rev": self.site_rev,
                    "coverage": {"mode": "prefixes", "prefixes": ["/subset/"]}
                    if cycle == 7
                    else {"mode": "complete"},
                    "entries": {}
                    if cycle == 7
                    else {
                        p: {"rev": self.revs[p], "digest": fingerprint(b)}
                        for p, b in self.pages.items()
                    },
                }
            ).encode(),
        }
        for kind, factory in factories.items():
            started = time.thread_time()
            self.metadata[kind] = factory()
            self.generation[kind] = time.thread_time() - started

    def body(self, path, language):
        body = self.pages[path]
        return body if language == "en" else b"<html lang=fr>" + body

    def start(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                started = time.thread_time()
                routes = {
                    "/sitemap.xml": "sitemap",
                    "/fingerprints.json": "fingerprints",
                    "/.well-known/pagedigest.json": "pagedigest",
                }
                language = self.headers.get("Accept-Language", "en")
                kind = routes.get(self.path)
                failed = owner.cycle == 10 and self.path == "/p/1"
                body = (
                    b"temporarily unavailable"
                    if failed
                    else owner.metadata[kind]
                    if kind
                    else owner.body(self.path, language)
                )
                etag = '"' + fingerprint(body) + '"'
                status = (
                    503
                    if failed
                    else 304
                    if self.headers.get("If-None-Match") == etag
                    else 200
                )
                compressed = "gzip" in self.headers.get("Accept-Encoding", "")
                payload = (
                    b""
                    if status == 304
                    else gzip.compress(body, mtime=0)
                    if compressed
                    else body
                )
                self.send_response(status)
                self.send_header("ETag", etag)
                self.send_header(
                    "Cache-Control",
                    "no-store"
                    if failed
                    else "max-age=0"
                    if kind
                    else "public, max-age=60",
                )
                if not kind:
                    self.send_header("Vary", "Accept-Language")
                if compressed and payload:
                    self.send_header("Content-Encoding", "gzip")
                self.send_header("Content-Length", str(len(payload)))
                headers = sum(map(len, self._headers_buffer)) + 2
                owner.metrics["requests"] += 1
                owner.metrics["response_body_wire_bytes"] += len(payload)
                owner.metrics["response_header_bytes"] += headers
                owner.events.append(
                    {
                        "path": self.path,
                        "status": status,
                        "language": language,
                        "body_bytes": len(payload),
                        "header_bytes": headers,
                    }
                )
                # Attribute preparation CPU before exposing the response; socket
                # write CPU is excluded, avoiding cross-request thread races.
                owner.metrics["publisher_serving_cpu_seconds"] += (
                    time.thread_time() - started
                )
                self.end_headers()
                if payload:
                    self.wfile.write(payload)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            kwargs={"poll_interval": 0.01},
            daemon=True,
        )
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        return self

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


def new_state(directory):
    directory.mkdir()
    return {
        "directory": directory,
        "items": {},
        "signals": {},
        "metadata": {},
        "manifest": None,
        "etag": None,
        "distrusted": False,
    }


def expire(item, now, language):
    return (
        item is None
        or item["language"] != language
        or now - item["validated"] >= 60
        or not item["path"].is_file()
    )


def run_cycle(origin, state, arm, session, cycle):
    """Return a policy-qualified snapshot; never turn a failed required GET into success."""
    now, language = cycle * 30, "fr" if cycle >= 8 else "en"
    started, cpu_started = time.perf_counter(), time.thread_time()
    bodies = {
        p: item["path"].read_bytes()
        for p, item in state["items"].items()
        if item["path"].is_file() and item["language"] == language
    }
    counters = {
        "audit_requests": 0,
        "audit_mismatches": 0,
        "fallbacks": 0,
        "cache_read_bytes": sum(map(len, bodies.values())),
        "cache_write_bytes": 0,
    }
    generation_kinds = set()

    def metadata(route, kind):
        generation_kinds.add(kind)
        prior = state["metadata"].get(route)
        r = session.get(
            origin.url + route, headers={"If-None-Match": prior[0]} if prior else {}
        )
        if r.status_code == 304 and prior:
            return prior[1]
        r.raise_for_status()
        state["metadata"][route] = (r.headers["ETag"], r.content)
        return r.content

    def inventory():
        return {
            node.findtext("loc"): node.findtext("lastmod")
            for node in ET.fromstring(metadata("/sitemap.xml", "sitemap"))
        }

    def get_body(path, audit=False, unconditional=False):
        item = state["items"].get(path)
        headers = {"Accept-Language": language}
        if audit:
            headers["Accept-Encoding"] = "identity"
            counters["audit_requests"] += 1
        if cycle == 9:
            headers["Cache-Control"] = "no-cache"
        if not unconditional and not audit and path in bodies and item:
            headers["If-None-Match"] = item["etag"]
        r = session.get(origin.url + path, headers=headers)
        if r.status_code == 304 and path not in bodies:
            r = session.get(origin.url + path, headers={"Accept-Language": language})
        if r.status_code != 304:
            r.raise_for_status()
            body = r.content
            target = (
                state["directory"]
                / hashlib.sha256((path + language).encode()).hexdigest()
            )
            target.write_bytes(body)
            counters["cache_write_bytes"] += len(body)
            bodies[path] = body
        else:
            target = item["path"]
        state["items"][path] = {
            "path": target,
            "validated": now,
            "language": language,
            "etag": r.headers["ETag"],
        }
        return bodies[path]

    complete, error, budget_stop = True, None, None
    try:
        audits, declared_digests = [], {}
        if arm == "pagedigest":
            generation_kinds.add("pagedigest")
            decision = check_site(
                origin.url,
                state["manifest"]["site_rev"] if state["manifest"] else None,
                {
                    p: state["manifest"]["entries"][p]["rev"]
                    for p in bodies
                    if state["manifest"] and p in state["manifest"]["entries"]
                },
                cached_manifest=state["manifest"],
                etag=state["etag"],
                session=session,
                sample_audit_rate=0.01,
                rng=random.Random(2000 + cycle),
            )
            if decision["fallback"]:
                signals = inventory()
                needed = set(signals)
                counters["fallbacks"] += 1
            else:
                state["manifest"], state["etag"] = (
                    decision["manifest"],
                    decision["etag"] or state["etag"],
                )
                entries = decision["manifest"]["entries"]
                signals = {p: item["rev"] for p, item in entries.items()}
                needed = set(decision["new"] + decision["changed"])
                declared_digests = {
                    p: item["digest"] for p, item in entries.items() if "digest" in item
                }
                if (
                    decision["manifest"]["coverage"]["mode"] != "complete"
                    or language != "en"
                    or state["distrusted"]
                ):
                    signals = inventory()
                    needed = set(signals)
                    counters["fallbacks"] += 1
                    declared_digests = {}
                else:
                    audits = [item["url"] for item in decision["audit_candidates"]]
        elif arm.startswith("fingerprint"):
            signals = json.loads(metadata("/fingerprints.json", "fingerprints"))
            needed = {
                p
                for p in signals
                if p not in bodies or state["signals"].get(p) != signals[p]
            }
            declared_digests = (
                signals if language == "en" and not state["distrusted"] else {}
            )
            if language != "en" or state["distrusted"]:
                needed = set(signals)
                counters["fallbacks"] += 1
            if arm.endswith("audited") and declared_digests:
                pool = sorted(set(signals) - needed)
                audits = (
                    random.Random(2000 + cycle).sample(pool, max(1, len(pool) // 100))
                    if pool
                    else []
                )
        else:
            signals = inventory()
            needed = (
                set(signals)
                if arm in {"full", "conditional-http"}
                else {p for p in signals if p not in bodies}
            )
            if arm == "sitemap-lastmod":
                needed |= {p for p in signals if state["signals"].get(p) != signals[p]}
        needed |= {p for p in signals if expire(state["items"].get(p), now, language)}
        if cycle == 9:
            needed = set(signals)
        # Audits refresh the same representation and count toward its deadline.
        for p in sorted(set(audits) - needed):
            body = get_body(p, audit=True)
            if fingerprint(body) != declared_digests[p]:
                counters["audit_mismatches"] += 1
                counters["fallbacks"] += 1
                state["distrusted"] = True
                needed = set(signals)
                break
        for p in sorted(needed):
            body = get_body(p, unconditional=arm == "full")
            if p in declared_digests and fingerprint(body) != declared_digests[p]:
                counters["audit_mismatches"] += 1
                state["distrusted"] = True
        state["signals"] = signals
        state["items"] = {p: item for p, item in state["items"].items() if p in signals}
        bodies = {p: b for p, b in bodies.items() if p in signals}
    except requests.RequestException as exc:
        complete, error = False, type(exc).__name__
    except BudgetExceeded as exc:
        complete, error, budget_stop = False, type(exc).__name__, str(exc)
    elapsed, cpu = time.perf_counter() - started, time.thread_time() - cpu_started
    # Independent fixture oracle is outside measured client work.
    violations, stale = [], []
    if complete:
        if set(bodies) != set(origin.pages):
            violations.append("wrong-inventory")
        for p, body in bodies.items():
            item = state["items"][p]
            if item["language"] != language or now - item["validated"] >= 60:
                violations.append("wrong-variant-or-expired-body:" + p)
            if body != origin.body(p, language):
                stale.append(p)
        if cycle == 10:
            violations.append("false-completion-on-required-fetch-failure")
    return {
        **counters,
        "complete": complete,
        "error": error,
        "budget_stop": budget_stop,
        "violations": violations,
        "within_deadline_stale_paths": stale,
        "consumer_cpu_seconds": cpu,
        "elapsed_seconds": elapsed,
        "generation_kinds": sorted(generation_kinds),
    }


def matrix(spec, sizes=(10, 100), client_counts=(1, 3), repeats=3, budget=None):
    budget = budget or Budget()
    rows, events, stopped = [], [], None
    try:
        with tempfile.TemporaryDirectory(prefix="pagedigest-p1-") as temp:
            for count in sizes:
                for clients in client_counts:
                    for repeat in range(repeats):
                        origin = Origin(count, budget).start()
                        sessions = []
                        try:
                            states = {}
                            for arm in spec["arms"]:
                                for client in range(clients):
                                    key = (arm, client)
                                    directory = (
                                        Path(temp)
                                        / f"{count}-{clients}-{repeat}-{arm}-{client}"
                                    )
                                    states[key] = new_state(directory)
                                    sessions.append(Session(origin, budget))
                            for cycle, scenario in enumerate(spec["scenarios"]):
                                origin.advance(cycle)
                                order = list(states)
                                random.Random(17 + repeat + cycle).shuffle(order)
                                for arm, client in order:
                                    state = states[(arm, client)]
                                    if cycle in {6, 10} and "/p/1" in state["items"]:
                                        state["items"]["/p/1"]["path"].unlink(
                                            missing_ok=True
                                        )
                                    origin.metrics = dict(
                                        requests=0,
                                        response_body_wire_bytes=0,
                                        response_header_bytes=0,
                                        publisher_serving_cpu_seconds=0.0,
                                    )
                                    origin.events = []
                                    session = sessions[
                                        list(states).index((arm, client))
                                    ]
                                    outcome = run_cycle(
                                        origin, state, arm, session, cycle
                                    )
                                    identity = dict(
                                        pages=count,
                                        clients=clients,
                                        repeat=repeat,
                                        arm=arm,
                                        client=client,
                                        cycle=cycle,
                                        scenario=scenario,
                                    )
                                    # One metadata producer serves all clients of an arm.
                                    generation = (
                                        sum(
                                            origin.generation[k]
                                            for k in outcome.pop("generation_kinds")
                                        )
                                        if client == 0
                                        else 0.0
                                    )
                                    rows.append(
                                        {
                                            **identity,
                                            **outcome,
                                            **origin.metrics,
                                            "publisher_generation_cpu_seconds": generation,
                                        }
                                    )
                                    events.extend(
                                        {**identity, **event} for event in origin.events
                                    )
                                    if outcome["budget_stop"]:
                                        raise BudgetExceeded(outcome["budget_stop"])
                        finally:
                            for session in sessions:
                                session.close()
                            origin.stop()
    except BudgetExceeded as exc:
        stopped = str(exc)
    totals = {}
    for arm in spec["arms"]:
        selected = [r for r in rows if r["arm"] == arm]
        totals[arm] = {
            key: sum(r[key] for r in selected)
            for key in [
                "requests",
                "response_body_wire_bytes",
                "response_header_bytes",
                "publisher_generation_cpu_seconds",
                "publisher_serving_cpu_seconds",
                "consumer_cpu_seconds",
                "cache_read_bytes",
                "cache_write_bytes",
            ]
        }
        totals[arm]["violations"] = sum(len(r["violations"]) for r in selected)
        totals[arm]["incomplete_cycles"] = sum(not r["complete"] for r in selected)
        totals[arm]["stale_body_observations_within_deadline"] = sum(
            len(r["within_deadline_stale_paths"]) for r in selected
        )
        totals[arm]["response_bytes"] = (
            totals[arm]["response_body_wire_bytes"]
            + totals[arm]["response_header_bytes"]
        )
    expected = (
        sum(client_counts)
        * len(sizes)
        * repeats
        * len(spec["arms"])
        * len(spec["scenarios"])
    )
    correct = (
        not stopped
        and len(rows) == expected
        and all(t["violations"] == 0 for t in totals.values())
        and all(r["complete"] == (r["cycle"] != 10) for r in rows)
    )
    best = min(
        (a for a in spec["arms"] if a != "pagedigest"),
        key=lambda a: totals[a]["response_bytes"],
    )
    reduction = (
        1 - totals["pagedigest"]["response_bytes"] / totals[best]["response_bytes"]
        if totals[best]["response_bytes"]
        else None
    )
    return {
        "experiment": spec["experiment"],
        "matrix_complete": not stopped and len(rows) == expected,
        "expected_rows": expected,
        "budget_stop": stopped,
        "correctness_pass": correct,
        "best_alternative": best,
        "response_byte_reduction": reduction,
        "economic_gate": "go"
        if correct and reduction is not None and reduction >= 0.20
        else "no-go",
        "limits": [
            "Fixture producer and logical clock; no production/CDN/adoption claim.",
            "Publisher response preparation CPU excludes socket writes and is measured separately from consumer thread CPU.",
            "Body cache I/O is measured in this experimental wrapper; the shipped persistent example remains in the original benchmark.",
            "No model calls or third-party command execution.",
        ],
        "totals": totals,
        "rows": rows,
        "events": events,
        "budget": {
            "requests": budget.requests,
            "response_bytes": budget.response_bytes,
            "wall_seconds": time.monotonic() - budget.started,
        },
    }


def run_study(output):
    raw = (PACKET / "SPEC.json").read_bytes()
    expected = (PACKET / "SPEC.sha256").read_text().split()[0]
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("frozen experiment specification changed")
    if output.exists():
        raise FileExistsError(
            "use a new output path; retained runs are never overwritten"
        )
    report = matrix(json.loads(raw))
    report["spec_sha256"] = expected
    report["code_sha256"] = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [Path(__file__), Path(__file__).with_name("benchmark_consumers.py")]
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    serialized = (json.dumps(report, indent=2) + "\n").encode()
    if len(serialized) + report["budget"]["response_bytes"] > 1 << 30:
        raise BudgetExceeded("combined response and retained output budget exhausted")
    output.write_bytes(serialized)
    print(
        json.dumps(
            {
                key: report[key]
                for key in [
                    "matrix_complete",
                    "correctness_pass",
                    "economic_gate",
                    "response_byte_reduction",
                    "budget",
                ]
            }
        )
    )
    return 0 if report["correctness_pass"] else 1
