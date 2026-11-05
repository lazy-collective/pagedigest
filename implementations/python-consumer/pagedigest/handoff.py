"""Experimental offline finding exchange; source bindings do not verify claims."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

from .core import manifest_url, resolve_url_key
from .recurring import MAX_STATE_BYTES, inspect_state, source_status

FORMAT = "lazycollective.finding-handoff/1"
MAX_ENVELOPE = 65536
MAX_OBJECTS = 128
MAX_STORE_BYTES = 16 * 1024 * 1024
HEX = re.compile(r"[0-9a-f]{64}\Z")
MEANING = "Unverified user interpretation; declared source bindings confer no execution or semantic authority."


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _dump(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate-JSON-key")
        result[key] = value
    return result


def _integer(value):
    result = int(value)
    try:
        finite = math.isfinite(result)
    except OverflowError as exc:
        raise ValueError("JSON-integer-out-of-range") from exc
    if not finite:
        raise ValueError("nonfinite-JSON-number")
    return result


def _float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("nonfinite-JSON-number")
    return result


def _json(raw, limit=MAX_ENVELOPE):
    if len(raw) > limit:
        raise ValueError("JSON-byte-limit-exceeded")
    try:
        result = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_float=_float,
            parse_int=_integer,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite-JSON")),
        )
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("invalid-UTF8-or-JSON-depth") from exc
    if not isinstance(result, dict):
        raise ValueError("JSON-object-required")
    return result


def _read(path, limit=MAX_ENVELOPE):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("regular-nonsymlink-input-required")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    _json(raw, limit)
    return raw


def _fields(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields.split()):
        raise ValueError("invalid-object-fields")


def _text(value, maximum=2048, nullable=False):
    if nullable and value is None:
        return
    if (
        not isinstance(value, str)
        or not value.strip()
        or not 1 <= len(value.encode("utf-8")) <= maximum
        or any(ord(c) < 32 and c not in "\n\t" for c in value)
    ):
        raise ValueError("invalid-bounded-text")


def _texts(value):
    if not isinstance(value, list) or len(value) > 32:
        raise ValueError("bounded-text-list-required")
    for item in value:
        _text(item)


def _digest(value):
    if not isinstance(value, str) or not HEX.fullmatch(value):
        raise ValueError("plain-lowercase-SHA256-required")


def _epoch(value):
    try:
        finite = type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite or value < 0:
        raise ValueError("finite-nonnegative-time-required")
    try:
        datetime.fromtimestamp(value, timezone.utc)
    except (OverflowError, OSError, ValueError) as exc:
        raise ValueError("time-out-of-range") from exc
    return value


def _stamp(value):
    # Keep sub-microsecond precision present in existing Unix float receipts.
    decimal = Decimal(str(_epoch(value)))
    seconds = int(decimal)
    fraction = "" if decimal == seconds else format(decimal - seconds, "f").removeprefix("0").rstrip("0")
    return datetime.fromtimestamp(seconds, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + fraction + "Z"


def _date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?Z", value):
        raise ValueError("UTC-RFC3339-time-required")
    try:
        whole, _, fraction = value[:-1].partition(".")
        seconds = datetime.fromisoformat(whole + "+00:00").timestamp()
        return _epoch(float(Decimal(str(seconds)) + (Decimal("0." + fraction) if fraction else 0)))
    except ValueError as exc:
        raise ValueError("invalid-UTC-time") from exc


def _url(value):
    _text(value)
    parsed = urlsplit(value)
    if (
        parsed.scheme not in ("https", "http")
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or any(c.isspace() for c in value)
    ):
        raise ValueError("exact-public-URL-required")
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError("invalid-URL-port") from exc
    key = parsed.path or "/"
    if parsed.query:
        key += "?" + parsed.query
    if resolve_url_key(value, key) != value:
        raise ValueError("URL-normalization-refused")
    return key


def validate_envelope(value):
    _fields(
        value,
        "format id origin claim taskScope limitations sources assumptions attribution "
        "findingCreatedAt exportedAt originEvidence meaning",
    )
    if value["format"] != FORMAT:
        raise ValueError("unsupported-handoff-format")
    _text(value["id"], 120)
    _fields(value["origin"], "product url")
    if value["origin"]["product"] != "pagedigest":
        raise ValueError("only-page-findings-supported")
    origin = value["origin"]["url"]
    _url(origin)
    if manifest_url(origin) != origin:
        raise ValueError("original-pagedigest-origin-required")
    _fields(value["claim"], "text")
    _text(value["claim"]["text"], 32768)
    _text(value["taskScope"], 4096)
    _texts(value["limitations"])
    _texts(value["assumptions"])
    _fields(value["attribution"], "author product recordId originProduct originRecordId originRecordHash")
    attribution = value["attribution"]
    _text(attribution["author"], nullable=True)
    _text(attribution["product"])
    if attribution["recordId"] != value["id"]:
        raise ValueError("attribution-record-id-mismatch")
    if attribution["originProduct"] != "pagedigest" or attribution["originRecordId"] != value["id"]:
        raise ValueError("attribution-origin-binding-mismatch")
    _digest(attribution["originRecordHash"])
    created, exported = _date(value["findingCreatedAt"]), _date(value["exportedAt"])
    if exported < created:
        raise ValueError("export-precedes-finding")
    sources = value["sources"]
    if not isinstance(sources, list) or not 1 <= len(sources) <= 16:
        raise ValueError("one-to-sixteen-sources-required")
    ids, urls = set(), set()
    for source in sources:
        _fields(source, "id kind url hash representation revision range originalObservedAt originalObservedAtReason")
        _text(source["id"], 120)
        if source["kind"] != "page":
            raise ValueError("only-page-sources-supported")
        _url(source["url"])
        if manifest_url(source["url"]) != origin:
            raise ValueError("source-origin-mismatch")
        if source["id"] in ids or source["url"] in urls:
            raise ValueError("duplicate-source-identity")
        ids.add(source["id"])
        urls.add(source["url"])
        _digest(source["hash"])
        # Preserve the opaque identity used by the actual recurring finding.
        if not isinstance(source["representation"], str) or not source["representation"].startswith("sha256:"):
            raise ValueError("pagedigest-representation-required")
        _digest(source["representation"][7:])
        if source["revision"] is not None or source["range"] is not None:
            raise ValueError("unsupported-source-revision-or-range")
        if source["originalObservedAt"] is None:
            _text(source["originalObservedAtReason"])
        elif _date(source["originalObservedAt"]) > created or source["originalObservedAtReason"] is not None:
            raise ValueError("invalid-original-source-time")
    _fields(value["originEvidence"], "locator hash originalReceipt")
    evidence = value["originEvidence"]
    _digest(evidence["hash"])
    if evidence["locator"] != "objects/" + evidence["hash"] + ".json":
        raise ValueError("invalid-origin-evidence-locator")
    if evidence["originalReceipt"] is not None:
        _fields(evidence["originalReceipt"], "locator hash")
        _text(evidence["originalReceipt"]["locator"])
        _digest(evidence["originalReceipt"]["hash"])
        _relative(evidence["originalReceipt"]["locator"])
    if value["meaning"] != MEANING:
        raise ValueError("interpretation-boundary-required")
    if len(_dump(value)) > MAX_ENVELOPE:
        raise ValueError("envelope-exceeds64KiB")
    return value


def _relative(value):
    path = Path(value)
    if (
        path.is_absolute()
        or "\\" in value
        or any(ord(c) < 32 for c in value)
        or any(p in ("", ".", "..") for p in value.split("/"))
    ):
        raise ValueError("safe-relative-evidence-path-required")
    return path


def _snapshot(state_path, now):
    state_path = Path(state_path)
    raw = _read(state_path, MAX_STATE_BYTES)
    # Strict parsing supplements the existing state and body-integrity validator.
    state = _json(raw, MAX_STATE_BYTES)
    pages = Path(str(state_path) + ".pages")
    if pages.is_symlink():
        raise ValueError("symlink-source-store-refused")
    if not isinstance(state.get("pages", {}), dict):
        raise ValueError("invalid-saved-page-map")
    for name in state.get("pages", {}).values():
        if not isinstance(name, str) or not re.fullmatch(r"[0-9a-f]{64}\.body", name):
            raise ValueError("unsafe-body-path")
        if (pages / name).is_symlink():
            raise ValueError("symlink-source-body-refused")
    inspected = inspect_state(state_path, now=now)
    if state_path.read_bytes() != raw or Path(str(state_path) + ".lock").exists():
        raise ValueError("state-changed-during-inspection")
    return state, inspected


def _original_times(finding, finding_id, state, evidence_root, original_receipt, now):
    created = _epoch(finding["created_at"])
    times = finding.get("original_observed_at", {})
    if not isinstance(times, dict) or set(times) - set(finding["sources"]):
        raise ValueError("invalid-original-observation-map")
    times = dict(times)
    for value in times.values():
        if _epoch(value) > created:
            raise ValueError("original-observation-after-finding")
    proof = None
    if (evidence_root is None) != (original_receipt is None):
        raise ValueError("evidence-root-and-original-receipt-required-together")
    if original_receipt is not None:
        relative = _relative(str(original_receipt))
        root = Path(evidence_root).resolve(strict=True)
        candidate = root / relative
        if any((root / Path(*relative.parts[:i])).is_symlink() for i in range(1, len(relative.parts) + 1)):
            raise ValueError("symlink-original-receipt-refused")
        candidate.resolve(strict=True).relative_to(root)
        raw = _read(candidate, MAX_STATE_BYTES)
        receipt = _json(raw, MAX_STATE_BYTES)
        if receipt.get("workflow") == 1:
            if any(
                not isinstance(receipt.get(field), dict)
                for field in ("findings", "resources", "last_attempt", "body_hashes")
            ):
                raise ValueError("invalid-original-state-receipt")
            original = receipt["findings"].get(finding_id)
            observed = receipt.get("resources", {})
            receipt_at = receipt.get("last_attempt", {}).get("at")
            if _epoch(receipt_at) > created:
                raise ValueError("original-state-is-later-than-finding")
        else:
            if (
                not isinstance(receipt.get("findings"), list)
                or any(not isinstance(f, dict) for f in receipt["findings"])
                or not isinstance(receipt.get("sources"), dict)
            ):
                raise ValueError("invalid-original-inspect-receipt")
            matched = [f for f in receipt["findings"] if f.get("id") == finding_id]
            original = matched[0] if len(matched) == 1 else None
            observed = receipt.get("sources", {})
            receipt_at = _epoch(receipt.get("inspected_at"))
            if not created <= receipt_at <= created + 60:
                raise ValueError("inspect-receipt-not-contemporaneous-with-finding")
        if _epoch(receipt_at) > now:
            raise ValueError("future-original-receipt")
        if receipt.get("origin") != state["origin"] or receipt.get("representation") != finding["representation"]:
            raise ValueError("original-receipt-identity-mismatch")
        if not isinstance(original, dict) or any(
            original.get(k) != finding[k] for k in ("text", "created_at", "sources", "representation")
        ):
            raise ValueError("original-receipt-finding-mismatch")
        for key, expected in finding["sources"].items():
            record = observed.get(key, {})
            if not isinstance(record, dict):
                raise ValueError("invalid-original-source-record")
            actual = receipt.get("body_hashes", {}).get(key) if receipt.get("workflow") == 1 else record.get("hash")
            validated = _epoch(record.get("validated_at"))
            if actual != expected or validated > created or validated > receipt_at:
                raise ValueError("original-receipt-source-binding-mismatch")
            if key in times and times[key] != validated:
                raise ValueError("original-receipt-time-conflicts-with-finding")
            times[key] = validated
        proof = {"locator": str(relative), "hash": _hash(raw)}
    return times, proof


def _inventory(target):
    """Validate the entire bounded content-addressed store before any append."""
    if target.is_symlink():
        raise ValueError("symlink-sidecar-objects-refused")
    existing = {}
    if not target.exists():
        return existing
    for path in target.iterdir():
        if path.is_symlink() or not path.is_file() or not re.fullmatch(r"[0-9a-f]{64}\.json", path.name):
            raise ValueError("unexpected-sidecar-object")
        size = path.stat().st_size
        if size > MAX_STATE_BYTES:
            raise ValueError("sidecar-object-byte-limit-exceeded")
        existing[path.stem] = size
        if len(existing) > MAX_OBJECTS or sum(existing.values()) > MAX_STORE_BYTES:
            raise ValueError("sidecar-existing-capacity-exceeded")
    # Bounds are established before integrity reads; bytes are never repaired.
    for key in existing:
        try:
            raw = _read(target / (key + ".json"), MAX_STATE_BYTES)
        except ValueError as exc:
            raise ValueError("sidecar-object-integrity-failure") from exc
        if _hash(raw) != key:
            raise ValueError("sidecar-object-integrity-failure")
    return existing


def _capacity(existing, pending):
    if len(set(existing) | set(pending)) > MAX_OBJECTS:
        raise ValueError("sidecar-object-capacity-exceeded")
    if sum(existing.values()) + sum(len(v) for k, v in pending.items() if k not in existing) > MAX_STORE_BYTES:
        raise ValueError("sidecar-byte-capacity-exceeded")


def _store(store, objects):
    """Append only digest-named objects under an operator-chosen bounded directory."""
    store = Path(store)
    if store.is_symlink():
        raise ValueError("symlink-sidecar-store-refused")
    pending = {_hash(raw): raw for raw in objects}
    for raw in pending.values():
        _json(raw, MAX_STATE_BYTES)
    target = store / "objects"
    # Refuse corruption/capacity errors before creating an output directory or lock.
    existing = _inventory(target)
    _capacity(existing, pending)
    store.mkdir(parents=True, exist_ok=True)
    lock = store / ".lock"
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        target.mkdir(exist_ok=True)
        # Recheck the entire store while holding the single-writer lock.
        existing = _inventory(target)
        _capacity(existing, pending)
        for key, raw in pending.items():
            path = target / (key + ".json")
            if key in existing:
                if path.read_bytes() != raw:
                    raise ValueError("sidecar-object-integrity-failure")
                continue
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(descriptor, "wb") as output:
                output.write(raw)
                output.flush()
                os.fsync(output.fileno())
    finally:
        os.close(fd)
        lock.unlink()
    return {key: str(target / (key + ".json")) for key in pending}


def export_finding(
    state_path, finding_id, metadata_file, store, *, evidence_root=None, original_receipt=None, now=None
):
    now = _epoch(time.time() if now is None else now)
    meta = _json(_read(metadata_file))
    _fields(meta, "taskScope assumptions limitations attribution")
    attribution = meta["attribution"]
    if (
        not isinstance(attribution, dict)
        or "author" not in attribution
        or set(attribution) - {"author", "product", "recordId"}
    ):
        raise ValueError("invalid-metadata-attribution")
    if attribution.get("recordId", finding_id) != finding_id:
        raise ValueError("metadata-record-id-mismatch")
    state, inspected = _snapshot(state_path, now)
    if finding_id not in state.get("findings", {}):
        raise ValueError("finding-not-found")
    finding = state["findings"][finding_id]
    times, proof = _original_times(finding, finding_id, state, evidence_root, original_receipt, now)
    # The provenance snapshot is a selected finding, not unrelated user findings.
    inspected["findings"] = [f for f in inspected["findings"] if f["id"] == finding_id]
    inspected["sources"] = {k: v for k, v in inspected["sources"].items() if k in finding["sources"]}
    snapshot = _dump(inspected)
    sources = []
    for index, (key, bound) in enumerate(sorted(finding["sources"].items())):
        sources.append(
            {
                "id": "s" + str(index + 1),
                "kind": "page",
                "url": resolve_url_key(state["origin"], key),
                "hash": bound[7:],
                "representation": finding["representation"],
                "revision": None,
                "range": None,
                "originalObservedAt": _stamp(times[key]) if key in times else None,
                "originalObservedAtReason": None if key in times else "not-retained-in-original-finding",
            }
        )
    envelope = {
        "format": FORMAT,
        "id": finding_id,
        "origin": {"product": "pagedigest", "url": state["origin"]},
        "claim": {"text": finding["text"]},
        "taskScope": meta["taskScope"],
        "limitations": meta["limitations"],
        "sources": sources,
        "assumptions": meta["assumptions"],
        "attribution": {
            "author": attribution["author"],
            "product": attribution.get("product", "pagedigest"),
            "recordId": attribution.get("recordId", finding_id),
            "originProduct": "pagedigest",
            "originRecordId": finding_id,
            "originRecordHash": _hash(_dump(finding)),
        },
        "findingCreatedAt": _stamp(finding["created_at"]),
        "exportedAt": _stamp(now),
        "originEvidence": {
            "locator": "objects/" + _hash(snapshot) + ".json",
            "hash": _hash(snapshot),
            "originalReceipt": proof,
        },
        "meaning": MEANING,
    }
    validate_envelope(envelope)
    raw = _dump(envelope)
    paths = _store(store, [snapshot, raw])
    return {
        "envelopeDigest": _hash(raw),
        "envelope": paths[_hash(raw)],
        "originEvidence": paths[_hash(snapshot)],
        "originalTimeUnknown": any(k not in times for k in finding["sources"]),
    }


def receive_finding(state_path, envelope_file, scope, policy_id, max_age, store, *, review_file=None, now=None):
    now = _epoch(time.time() if now is None else now)
    _text(scope, 4096)
    _text(policy_id, 120)
    try:
        valid_age = type(max_age) in (int, float) and math.isfinite(max_age) and max_age > 0
    except OverflowError:
        valid_age = False
    if not valid_age:
        raise ValueError("finite-positive-recipient-max-age-required")
    raw = _read(envelope_file)
    envelope = validate_envelope(_json(raw))
    if _date(envelope["exportedAt"]) > now:
        raise ValueError("future-envelope-export")
    state, inspected = _snapshot(state_path, now)
    source_reports = []
    for source in envelope["sources"]:
        key = _url(source["url"])
        own = inspected["sources"].get(key, {})
        reasons = []
        status = "unknown"
        if state["origin"] != envelope["origin"]["url"]:
            reasons.append("recipient-origin-mismatch")
        elif state["representation"] != source["representation"]:
            reasons.append("recipient-representation-mismatch")
        elif not own.get("retained"):
            reasons.append("recipient-body-missing-or-corrupt")
        else:
            validated = own.get("validated_at")
            fresh = own.get("sourceStatus") == "current" and validated is not None and 0 <= now - validated < max_age
            # Intact differing bytes establish change even if that observation
            # no longer meets current freshness/availability policy.
            if own["hash"] != "sha256:" + source["hash"]:
                status = "changed"
                reasons.append("source-bytes-changed")
            elif fresh:
                status = "current"
                reasons.append("full-body-hash-match")
            if not fresh:
                reasons.append("recipient-source-unavailable-or-policy-expired")
        if source["originalObservedAt"] is None:
            reasons.append("original-source-time-unknown")
        source_reports.append(
            {
                "id": source["id"],
                "url": source["url"],
                "boundHash": source["hash"],
                "observedHash": own.get("hash", "")[7:] if own.get("hash") else None,
                "validatedAt": _stamp(own["validated_at"]) if own.get("validated_at") is not None else None,
                "sourceStatus": status,
                "reasons": reasons,
            }
        )
    status = source_status(s["sourceStatus"] for s in source_reports)
    scope_match = scope == envelope["taskScope"]
    blockers = []
    if not scope_match:
        blockers.append("task-scope-mismatch")
    if envelope["attribution"]["author"] is None:
        blockers.append("original-attribution-unknown")
    if any(s["originalObservedAt"] is None for s in envelope["sources"]):
        blockers.append("original-source-time-unknown")
    if status != "current":
        blockers.append("sources-not-current")
    interpretation = {"disposition": "unreviewed", "review": None}
    if review_file is not None:
        review = _json(_read(review_file))
        _fields(review, "envelopeDigest disposition reviewer reviewedAt taskScope completeSourceScope note")
        _digest(review["envelopeDigest"])
        if review["envelopeDigest"] != _hash(raw) or review["taskScope"] != scope:
            raise ValueError("review-digest-or-scope-mismatch")
        if review["disposition"] not in ("accepted", "rejected", "conflicting"):
            raise ValueError("explicit-review-disposition-required")
        _text(review["reviewer"])
        _text(review["note"], 4096)
        if type(review["completeSourceScope"]) is not bool:
            raise ValueError("explicit-complete-source-scope-boolean-required")
        if not _date(envelope["findingCreatedAt"]) <= _date(review["reviewedAt"]) <= now:
            raise ValueError("review-time-outside-finding-and-check")
        if review["disposition"] == "accepted" and (blockers or not review["completeSourceScope"]):
            raise ValueError("accepted-review-requires-current-sources-known-time-attribution-and-complete-exact-scope")
        interpretation = {"disposition": review["disposition"], "review": review}
    receipt = {
        "format": "lazycollective.finding-receipt/1",
        "envelopeDigest": _hash(raw),
        "policy": {"id": policy_id, "maxAgeSeconds": max_age},
        "checkedAt": _stamp(now),
        "taskScope": scope,
        "taskScopeMatch": scope_match,
        "sourceStatus": status,
        "sources": source_reports,
        "interpretation": interpretation,
        "interpretationBlockers": blockers,
        "localIntegrityReads": inspected["local_integrity_reads"],
        "localIntegrityBytes": inspected["local_integrity_bytes"],
        "meaning": MEANING,
    }
    receipt_raw = _dump(receipt)
    if len(receipt_raw) > MAX_ENVELOPE:
        raise ValueError("receipt-exceeds64KiB")
    paths = _store(store, [raw, receipt_raw])
    return {
        **receipt,
        "envelope": paths[_hash(raw)],
        "receiptDigest": _hash(receipt_raw),
        "receipt": paths[_hash(receipt_raw)],
    }
