"""Bounded recurring observation and source-bound findings, without model calls.

This is a local workflow, not a new PageDigest wire protocol or a general HTTP
cache. Findings are user-supplied interpretations; reuse means their declared
source bodies remain available under the chosen freshness policy, not truth.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
import tempfile
import time
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit

import requests

from .core import check_site, manifest_url, resolve_url_key
from .persistence import load_state, save_state

MAX_URLS = 200
MAX_FINDINGS = 200
MAX_STATE_BYTES = 4 * 1024 * 1024
MAX_PAGE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 50 * 1024 * 1024
MAX_REQUESTS = 250
MAX_CACHE_BYTES = 128 * 1024 * 1024
SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


def digest(body):
    return "sha256:" + hashlib.sha256(body).hexdigest()


@contextmanager
def locked(state_path):
    state_path.parent.mkdir(parents=True, exist_ok=True)
    lock = Path(str(state_path) + ".lock")
    descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        yield
    finally:
        os.close(descriptor)
        lock.unlink()


def read_state(path):
    if path.exists() and path.stat().st_size > MAX_STATE_BYTES:
        raise ValueError("state exceeds4MiB")
    state = load_state(path)
    if state.get("workflow") not in (None, 1):
        raise ValueError("unsupported recurring workflow state")
    for name in ("resources", "findings"):
        if not isinstance(state.get(name, {}), dict):
            raise ValueError(f"invalid {name}")
    if len(state.get("resources", {})) > MAX_URLS or len(state.get("findings", {})) > MAX_FINDINGS:
        raise ValueError("state exceeds workflow item limits")
    for finding in state.get("findings", {}).values():
        if (
            not isinstance(finding, dict)
            or not isinstance(finding.get("sources"), dict)
            or not 1 <= len(finding["sources"]) <= 16
            or not isinstance(finding.get("representation"), str)
        ):
            raise ValueError("invalid finding source binding")
    return state


class BudgetExceeded(requests.RequestException):
    pass


class Meter:
    """Count started requests and actual response-body bytes consumed, including failures."""

    def __init__(self, session, headers, max_requests, max_bytes):
        self.session, self.headers = session, headers
        self.max_requests, self.max_bytes = max_requests, max_bytes
        self.requests, self.bytes, self.events = 0, 0, []
        self.started = time.monotonic()

    def get(self, url, **kwargs):
        if time.monotonic() - self.started >= 120:
            raise BudgetExceeded("cycle-time-budget-exhausted")
        if self.requests >= self.max_requests:
            raise BudgetExceeded("request-budget-exhausted")
        self.requests += 1
        event = {"url": url, "status": None, "body_bytes": 0}
        self.events.append(event)
        if hasattr(self.session, "cookies"):
            self.session.cookies.clear()
        kwargs["headers"] = {**self.headers, **kwargs.get("headers", {})}
        response = self.session.get(url, **kwargs)
        event["status"] = response.status_code
        original = response.iter_content

        def counted(*args, **kw):
            for chunk in original(*args, **kw):
                self.bytes += len(chunk)
                event["body_bytes"] += len(chunk)
                if self.bytes > self.max_bytes:
                    raise BudgetExceeded("response-body-budget-exhausted")
                if time.monotonic() - self.started >= 120:
                    raise BudgetExceeded("cycle-time-budget-exhausted")
                yield chunk

        response.iter_content = counted
        return response


def body_bytes(response, max_bytes):
    length = response.headers.get("Content-Length")
    if length is not None and (not length.isdigit() or int(length) > max_bytes):
        raise ValueError("invalid-or-excessive-content-length")
    chunks, size = [], 0
    for chunk in response.iter_content(chunk_size=65536):
        size += len(chunk)
        if size > max_bytes:
            raise ValueError("response-body-too-large")
        chunks.append(chunk)
    return b"".join(chunks)


def response_policy(headers, now):
    if sum(len(str(k)) + len(str(v)) for k, v in headers.items()) > 16384:
        raise ValueError("response-headers-too-large-to-retain")
    policy = {}
    for part in headers.get("Cache-Control", "").split(","):
        key, _, value = part.strip().partition("=")
        policy[key.lower()] = value.strip('"')
    vary = {p.strip().lower() for p in headers.get("Vary", "").split(",") if p.strip()}
    if policy.keys() & {"private", "no-store"} or headers.get("Set-Cookie"):
        raise ValueError("response-does-not-permit-local-public-retention")
    if vary - {"accept-encoding", "accept-language"}:
        raise ValueError("unsupported-representation-vary")
    if headers.get("Content-Encoding", "identity").lower() not in ("", "identity"):
        raise ValueError("origin-did-not-serve-identity-encoding")
    # Unsupported or malformed caching instructions only make reuse stricter.
    revalidate = bool(policy.keys() & {"no-cache", "must-understand", "must-revalidate", "proxy-revalidate"})
    age = 0
    try:
        age = max(0, int(headers.get("Age", "0")))
        if headers.get("Date"):
            age = max(age, now - parsedate_to_datetime(headers["Date"]).timestamp())
        lifetime = max(0, int(policy["max-age"])) if "max-age" in policy else 0
        if "max-age" not in policy and headers.get("Expires"):
            date = parsedate_to_datetime(headers.get("Date", headers["Expires"])).timestamp()
            lifetime = max(0, parsedate_to_datetime(headers["Expires"]).timestamp() - date)
        fresh_until = now + max(0, lifetime - age)
    except (ValueError, TypeError, OverflowError):
        fresh_until, revalidate = now, True
    return {
        "fresh_until": fresh_until,
        "revalidate": revalidate,
        # Explicit HTTP freshness always takes priority over a publisher hint.
        "http_lifetime": "max-age" in policy or bool(headers.get("Expires")),
    }


def retained_body(state, key, pages_dir):
    filename = state["pages"].get(key)
    expected = state["body_hashes"].get(key)
    if not filename or not expected:
        return None
    try:
        body = (pages_dir / filename).read_bytes()
    except FileNotFoundError:
        return None
    return body if len(body) <= MAX_PAGE_BYTES and digest(body) == expected else None


def write_body(pages_dir, body):
    pages_dir.mkdir(parents=True, exist_ok=True)
    name = digest(body)[7:] + ".body"
    retained_bytes = sum(path.stat().st_size for path in cache_objects(pages_dir) if path.name != name)
    if retained_bytes + len(body) > MAX_CACHE_BYTES:
        raise ValueError("retained-body-cache-budget-exhausted")
    with tempfile.NamedTemporaryFile(dir=pages_dir, delete=False) as temp:
        temp.write(body)
        temp.flush()
        os.fsync(temp.fileno())
        temporary = Path(temp.name)
    os.replace(temporary, pages_dir / name)
    return name


def cache_objects(pages_dir):
    """Only this cache's regular content-addressed body objects are owned here."""
    if not pages_dir.exists():
        return []
    return [
        path
        for path in pages_dir.iterdir()
        if len(path.name) == 69
        and path.name.endswith(".body")
        and all(c in "0123456789abcdef" for c in path.name[:-5])
        and not path.is_symlink()
        and path.is_file()
    ]


def prune_bodies(state, pages_dir):
    """After state commit, retain current and finding-cited bodies only."""
    keep = set(state["pages"].values())
    keep.update(
        value.removeprefix("sha256:") + ".body"
        for finding in state.get("findings", {}).values()
        for value in finding["sources"].values()
    )
    for path in cache_objects(pages_dir):
        if path.name not in keep:
            path.unlink()


def sitemap_sources(base_url, key, meter, now):
    """A bounded urlset supplies discovery/change hints, never proof of absence."""
    response = meter.get(resolve_url_key(base_url, key), timeout=15, stream=True, allow_redirects=False)
    try:
        if response.status_code != 200:
            raise ValueError(f"sitemap-HTTP-{response.status_code}")
        raw = body_bytes(response, MAX_PAGE_BYTES)
        if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
            raise ValueError("sitemap-entities-not-supported")
        root = ET.fromstring(raw)
        if root.tag not in (SITEMAP_NS + "urlset", "urlset"):
            raise ValueError("only-bounded-sitemap-urlsets-supported")
        origin = urlsplit(manifest_url(base_url))
        result = {}
        for item in root:
            ns = SITEMAP_NS if item.tag.startswith(SITEMAP_NS) else ""
            location = item.findtext(ns + "loc")
            if not location:
                raise ValueError("sitemap-missing-location")
            url = urlsplit(location)
            if (url.scheme, url.netloc) != (origin.scheme, origin.netloc) or url.fragment:
                raise ValueError("sitemap-cross-origin-or-fragment")
            url_key = url.path or "/"
            if url.query:
                url_key += "?" + url.query
            if resolve_url_key(base_url, url_key) != location:
                raise ValueError("sitemap-location-normalized")
            result[url_key] = item.findtext(ns + "lastmod")
            if len(result) > MAX_URLS:
                raise ValueError("sitemap-scope-exceeds200-URLs")
        return result
    finally:
        response.close()


def findings_report(state, pages_dir, available, now):
    result = []
    for name, finding in sorted(state.get("findings", {}).items()):
        problems = []
        for key, expected in finding["sources"].items():
            if finding["representation"] != state.get("representation"):
                problems.append({"url": key, "reason": "representation-changed"})
            elif key not in available or retained_body(state, key, pages_dir) is None:
                problems.append({"url": key, "reason": "source-unavailable-or-not-currently-validated"})
            elif state["body_hashes"].get(key) != expected:
                problems.append({"url": key, "reason": "source-bytes-changed"})
        status = "needs_reread" if any(p["reason"] == "source-bytes-changed" for p in problems) else "unknown"
        result.append({"id": name, "status": status if problems else "usable", "problems": problems})
    return result


def remember(state_path, finding_id, text, source_keys, *, now=None):
    """Bind an explicit user-supplied finding to current cached source hashes."""
    now = time.time() if now is None else now
    if not isinstance(finding_id, str) or not 1 <= len(finding_id) <= 120:
        raise ValueError("finding-id-must-be1..120-characters")
    if not isinstance(text, str) or not 1 <= len(text.encode()) <= 32768:
        raise ValueError("finding-text-must-be1..32768-UTF8-bytes")
    keys = sorted(set(source_keys))
    if not 1 <= len(keys) <= 16:
        raise ValueError("a-finding-needs1..16-explicit-source-URLs")
    with locked(state_path):
        state = read_state(state_path)
        if state.get("workflow") != 1:
            raise ValueError("run-sync-before-remember")
        available = set(state.get("last_attempt", {}).get("available", []))
        for key in keys:
            record = state.get("resources", {}).get(key, {})
            if (
                key not in available
                or now < record.get("validated_at", math.inf)
                or now >= record.get("validated_at", 0) + state["max_age"]
                or retained_body(state, key, Path(str(state_path) + ".pages")) is None
            ):
                raise ValueError(f"source-must-be-synchronized-within-freshness-policy:{key}")
        findings = state.setdefault("findings", {})
        if finding_id in findings:
            raise ValueError("finding-already-exists-use-a-new-id-for-revised-work")
        if len(findings) >= MAX_FINDINGS:
            raise ValueError("finding-limit-reached")
        findings[finding_id] = {
            "text": text,
            "created_at": now,
            "sources": {key: state["body_hashes"][key] for key in keys},
            "representation": state["representation"],
            "meaning": (
                "User-supplied interpretation; source binding is not verification "
                "of the conclusion or complete dependency coverage."
            ),
        }
        if len(json.dumps(state, indent=2, sort_keys=True).encode()) + 1 > MAX_STATE_BYTES:
            raise ValueError("finding-would-exceed4MiB-state-limit")
        save_state(state_path, state)
        return {"id": finding_id, "sources": findings[finding_id]["sources"], "status": "retained"}


def sync(
    base_url,
    state_path,
    *,
    urls=None,
    sitemap=None,
    http_only=False,
    max_age=3600,
    audit_rate=0.01,
    language="",
    max_requests=MAX_REQUESTS,
    max_bytes=MAX_TOTAL_BYTES,
    session=None,
    now=None,
):
    """Run exactly one bounded cycle; a caller may schedule repeated invocations."""
    now = time.time() if now is None else now
    if not math.isfinite(now) or not math.isfinite(max_age) or max_age <= 0 or not 0 <= audit_rate <= 1:
        raise ValueError("finite-positive-max-age-and-audit-rate0..1-required")
    if type(max_requests) is not int or not 1 <= max_requests <= MAX_REQUESTS:
        raise ValueError("request-limit-must-be1..250")
    if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_TOTAL_BYTES:
        raise ValueError("response-byte-limit-must-be1..50MiB")
    origin = urlsplit(base_url)
    if origin.username or origin.password or origin.fragment:
        raise ValueError("public-origin-without-credentials-or-fragment-required")
    if not isinstance(language, str) or len(language) > 128 or any(ord(c) < 32 for c in language):
        raise ValueError("invalid-Accept-Language")
    with locked(state_path):
        client = session or requests.Session()
        if getattr(client, "auth", None) or any(
            name.lower() in {"authorization", "cookie"} for name in getattr(client, "headers", {})
        ):
            raise ValueError("authenticated-sessions-are-outside-public-recurring-workflow")
        if any(
            name.lower() not in {"user-agent", "accept", "accept-encoding", "accept-language", "connection"}
            for name in getattr(client, "headers", {})
        ):
            raise ValueError("custom-session-headers-are-outside-fixed-public-representation")
        if hasattr(client, "trust_env"):
            client.trust_env = False
        try:
            return _sync(
                base_url,
                state_path,
                urls,
                sitemap,
                http_only,
                max_age,
                audit_rate,
                language,
                max_requests,
                max_bytes,
                client,
                now,
            )
        finally:
            if session is None:
                client.close()


def _sync(
    base_url, state_path, urls, sitemap, http_only, max_age, audit_rate, language, max_requests, max_bytes, client, now
):
    state = read_state(state_path)
    origin = manifest_url(base_url)
    if state.get("origin") not in (None, origin):
        raise ValueError("state-belongs-to-another-origin")
    pages_dir = Path(str(state_path) + ".pages")
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "identity",
        "Accept-Language": language,
        "User-Agent": "PageDigest-recurring/experimental",
    }
    representation = digest(json.dumps(headers, sort_keys=True).encode())
    if state.get("representation") != representation:
        state.update(
            pages={}, body_hashes={}, resources={}, revs={}, manifest=None, site_rev=None, etag=None, last_modified=None
        )
    state.update(workflow=1, origin=origin, representation=representation, max_age=max_age)
    meter = Meter(client, headers, max_requests, max_bytes)
    resources = state.setdefault("resources", {})
    suspect = set(state.get("suspect", []))
    available = {key: retained_body(state, key, pages_dir) for key in resources}
    available = {key: body for key, body in available.items() if body is not None}
    decision = {"fallback": True, "error": "http-only", "unchanged": []}
    if not http_only:
        decision = check_site(
            base_url,
            state["site_rev"],
            {k: state["revs"][k] for k in available if k in state["revs"]},
            etag=state["etag"],
            last_modified=state["last_modified"],
            cached_manifest=state["manifest"],
            sample_audit_rate=0,
            session=meter,
            max_bytes=MAX_PAGE_BYTES,
        )
    manifest = None if decision["fallback"] else decision["manifest"]
    report = {
        "complete": False,
        "observed_at": now,
        "changed": [],
        "new": [],
        "reread": [],
        "removed": [],
        "reused": [],
        "revalidated": [],
        "errors": [],
        "findings": [],
        "signal": "http" if manifest is None else "pagedigest",
        "manifest_fallback": decision.get("error"),
        "sitemap": sitemap,
        "scope": "Explicit URLs and discovered entries only; sitemap omission is not proof of deletion.",
        "meaning": (
            "Usable means declared source dependencies remain retained under this freshness policy; "
            "it does not verify a finding or guarantee immediate change detection."
        ),
    }
    explicit = urls if urls is not None else state.get("explicit_urls", [])
    if not isinstance(explicit, list) or len(explicit) > MAX_URLS:
        raise ValueError("provide-at-most200-explicit-source-URLs")
    if any(not isinstance(key, str) or len(key) > 2048 for key in explicit):
        raise ValueError("source-URLs-must-be-bounded-strings")
    explicit = sorted(set(explicit))
    for key in explicit:
        resolve_url_key(base_url, key)
    sitemap = sitemap if sitemap is not None else state.get("sitemap")
    report["sitemap"] = sitemap
    fixed_scope = bool(explicit) and not sitemap
    scope = set(explicit)
    # Keep earlier discovered URLs until exact 404/410 or complete PageDigest
    # omission. Explicit source selection instead limits what we observe.
    if not fixed_scope:
        scope.update(state.get("scope", []))
        scope.update(resources)
        if manifest:
            scope.update(manifest["entries"])
    report["out_of_scope"] = sorted(set(resources) - scope) if fixed_scope else []
    for key in report["out_of_scope"]:
        for mapping in (resources, state["pages"], state["body_hashes"], state["revs"]):
            mapping.pop(key, None)
    if (
        state.get("distrusted")
        and manifest
        and manifest["site_rev"] <= state.get("distrust_site_rev", manifest["site_rev"])
    ):
        # A failed audit must not trap the workflow behind a bad publisher
        # signal. Continue with ordinary HTTP until a newer manifest passes.
        manifest = None
        report.update(signal="http", manifest_fallback="previous-audit-failure")
    lastmods = {}
    if sitemap:
        try:
            lastmods = sitemap_sources(base_url, sitemap, meter, now)
            scope.update(lastmods)
        except (requests.RequestException, ValueError, ET.ParseError) as exc:
            report["errors"].append({"url": sitemap, "reason": str(exc)})
    if not scope and manifest is None and not sitemap:
        report["errors"].append({"url": None, "reason": "no-source-scope-provide-urls-or-sitemap"})
    if len(scope) > MAX_URLS:
        report["errors"].append({"url": None, "reason": "scope-exceeds200-URLs-narrow-it-before-sync"})
        scope = set()
    current = set()
    removed = set()
    for key in sorted(scope):
        previous = resources.get(key, {})
        old_hash = state["body_hashes"].get(key)
        entry = manifest["entries"].get(key) if manifest else None
        if (
            manifest
            and manifest.get("coverage", {}).get("mode") == "complete"
            and entry is None
            and key not in explicit
        ):
            removed.add(key)
            continue
        valid_body = key in available
        age = now - previous.get("validated_at", 0)
        within_deadline = 0 <= age < max_age
        policy = previous.get("policy", {})
        audit_now = valid_body and audit_rate > 0 and random.random() < audit_rate
        unchanged_hint = manifest and key in decision["unchanged"] and not language and not state.get("distrusted")
        changed_hint = (manifest and entry and key not in decision["unchanged"]) or (
            key in lastmods and lastmods[key] != previous.get("sitemap_lastmod")
        )
        http_fresh = now < policy.get("fresh_until", 0)
        can_skip = (
            valid_body
            and key not in suspect
            and within_deadline
            and not audit_now
            and not changed_hint
            and not policy.get("revalidate")
            and (http_fresh or (unchanged_hint and not policy.get("http_lifetime")))
        )
        if can_skip:
            current.add(key)
            report["reused"].append(
                {"url": key, "basis": "http-freshness" if http_fresh else "pagedigest-within-deadline"}
            )
            continue
        request_headers = {}
        if valid_body and key not in suspect and not audit_now and not changed_hint and not state.get("distrusted"):
            if previous.get("etag"):
                request_headers["If-None-Match"] = previous["etag"]
            elif previous.get("last_modified"):
                request_headers["If-Modified-Since"] = previous["last_modified"]
        response = None
        try:
            response = meter.get(
                resolve_url_key(base_url, key), headers=request_headers, timeout=15, stream=True, allow_redirects=False
            )
            if response.status_code in (404, 410):
                removed.add(key)
                continue
            if response.status_code == 304:
                if not valid_body or not request_headers:
                    raise ValueError("304-without-valid-conditional-body")
                body = available[key]
                # A 304 updates only supplied fields; preserve constraints otherwise.
                retained_headers = {**previous.get("headers", {}), **dict(response.headers)}
                report["revalidated"].append(key)
            elif response.status_code == 200:
                body = body_bytes(response, MAX_PAGE_BYTES)
                retained_headers = dict(response.headers)
            else:
                raise ValueError(f"HTTP-{response.status_code}")
            new_policy = response_policy(requests.structures.CaseInsensitiveDict(retained_headers), now)
            actual = digest(body)
            if entry and not language and entry.get("digest") and entry["digest"] != actual:
                state["distrusted"] = True
                state["distrust_site_rev"] = manifest["site_rev"]
                raise ValueError("pagedigest-digest-audit-mismatch")
            if audit_now and unchanged_hint and old_hash != actual:
                state["distrusted"] = True
                state["distrust_site_rev"] = manifest["site_rev"]
                raise ValueError("pagedigest-unchanged-audit-mismatch")
            state["pages"][key] = write_body(pages_dir, body)
            state["body_hashes"][key] = actual
            resources[key] = {
                "validated_at": now,
                "etag": response.headers.get("ETag", previous.get("etag") if response.status_code == 304 else None),
                "last_modified": response.headers.get(
                    "Last-Modified", previous.get("last_modified") if response.status_code == 304 else None
                ),
                "policy": new_policy,
                "headers": {
                    k: v
                    for k, v in retained_headers.items()
                    if k.lower() in ("cache-control", "vary", "expires", "date", "age", "content-encoding")
                },
                "sitemap_lastmod": lastmods.get(key),
            }
            if entry:
                state["revs"][key] = entry["rev"]
            else:
                state["revs"].pop(key, None)
            current.add(key)
            suspect.discard(key)
            if old_hash != actual:
                report["new" if old_hash is None else "changed"].append(key)
                report["reread"].append(key)
        except (requests.RequestException, ValueError, OSError) as exc:
            suspect.add(key)
            report["errors"].append({"url": key, "reason": str(exc)})
            report["reread"].append(key)
        finally:
            if response is not None:
                response.close()
    for key in removed:
        for mapping in (resources, state["pages"], state["body_hashes"], state["revs"]):
            mapping.pop(key, None)
    report["removed"] = sorted(removed)
    if manifest and not report["errors"]:
        state.update(
            manifest=manifest,
            site_rev=manifest["site_rev"],
            etag=decision.get("etag") or state["etag"],
            last_modified=decision.get("last_modified") or state["last_modified"],
            distrusted=False,
        )
    report["complete"] = not report["errors"]
    report["findings"] = findings_report(state, pages_dir, current, now)
    report["requests"], report["response_body_bytes"] = meter.requests, meter.bytes
    report["elapsed_seconds"] = time.monotonic() - meter.started
    report["http"] = meter.events
    report["accounting"] = (
        "Counts every started request and consumed response-body byte, including failures; "
        "excludes HTTP headers, TLS, provider and physical disk costs. No model calls."
    )
    state.update(
        explicit_urls=explicit,
        sitemap=sitemap,
        scope=sorted(scope - removed),
        suspect=sorted(suspect - removed),
        last_attempt={
            "at": now,
            "complete": report["complete"],
            "available": sorted(current),
            "errors": report["errors"],
        },
    )
    if len(json.dumps(state, indent=2, sort_keys=True).encode()) + 1 <= MAX_STATE_BYTES:
        save_state(state_path, state)
        try:
            prune_bodies(state, pages_dir)
        except OSError as exc:
            report["cache_maintenance_error"] = str(exc)
    else:
        report["complete"] = False
        report["errors"].append({"url": None, "reason": "state-budget-exhausted-snapshot-not-committed"})
        previous = read_state(state_path)
        previous["last_attempt"] = {"at": now, "complete": False, "available": [], "errors": [report["errors"][-1]]}
        save_state(state_path, previous)
        report["findings"] = findings_report(previous, pages_dir, set(), now)
    return report
