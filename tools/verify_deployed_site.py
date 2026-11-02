#!/usr/bin/env python3
"""Read-only gate for an exact, fully digested dogfood deployment.

Unlike sampled consumer audits, this deployment control requires complete
coverage and a digest for every entry. It never adopts served hashes or removes
digests. Two full passes catch deployment races; any unresolved observation fails.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import requests
from pagedigest import resolve_url_key, validate_manifest

MAX_BYTES = 10 * 1024 * 1024
MAX_ENTRIES = 100
# The observed injection depended on Accept; verify each known representation.
REQUEST_PROFILES = (
    ("consumer", requests.utils.default_user_agent(), "*/*"),
    ("audit-no-accept", "LazyCollective-MessagingReview/1.0", None),
    ("browser-html", "Mozilla/5.0 PageDigest-DeploymentCheck/1.0", "text/html"),
)


def fetch_body(base_url: str, key: str, profile: tuple) -> bytes:
    url = resolve_url_key(base_url, key)
    with requests.get(
        url,
        headers={
            "Accept-Encoding": "identity",
            "Cache-Control": "no-cache",
            "User-Agent": profile[1],
            "Accept": profile[2],  # None removes requests' default */* header.
        },
        allow_redirects=False,
        stream=True,
        timeout=15,
    ) as response:
        if response.status_code != 200:
            raise ValueError(f"{key}: expected HTTP 200, got {response.status_code}")
        if response.headers.get("Content-Encoding", "identity").lower() != "identity":
            raise ValueError(f"{key}: non-identity response")
        if (
            response.headers.get("Content-Type", "").split(";", 1)[0].lower()
            == "text/html"
        ):
            directives = {
                value.strip().lower()
                for value in response.headers.get("Cache-Control", "").split(",")
            }
            if "no-transform" not in directives:
                raise ValueError(
                    f"{key}: HTML lacks the required no-transform response policy"
                )
        body = response.raw.read(MAX_BYTES + 1, decode_content=False)
        if len(body) > MAX_BYTES:
            raise ValueError(f"{key}: response exceeds {MAX_BYTES} bytes")
        return body


def verify(base_url: str, expected: bytes) -> dict:
    manifest = json.loads(expected)
    if error := validate_manifest(manifest):
        raise ValueError(f"invalid expected manifest: {error}")
    if manifest.get("coverage") != {"mode": "complete"}:
        raise ValueError("deployment gate requires complete coverage")
    entries = manifest["entries"]
    if not 1 <= len(entries) <= MAX_ENTRIES:
        raise ValueError(f"deployment gate requires 1..{MAX_ENTRIES} entries")
    if any("digest" not in entry for entry in entries.values()):
        raise ValueError("deployment gate requires a digest for every entry")
    observations = []
    for profile in REQUEST_PROFILES:
        try:
            for pass_number in (1, 2):
                if (
                    fetch_body(base_url, "/.well-known/pagedigest.json", profile)
                    != expected
                ):
                    raise ValueError(
                        "live manifest differs from the exact intended manifest"
                    )
                for key, entry in entries.items():
                    body = fetch_body(base_url, key, profile)
                    digest = "sha256:" + hashlib.sha256(body).hexdigest()
                    if digest != entry["digest"]:
                        raise ValueError(
                            f"{key}: full served-body digest mismatch on pass {pass_number}: {digest}"
                        )
                    observations.append(
                        {
                            "profile": profile[0],
                            "pass": pass_number,
                            "url": key,
                            "digest": digest,
                            "bytes": len(body),
                        }
                    )
            if (
                fetch_body(base_url, "/.well-known/pagedigest.json", profile)
                != expected
            ):
                raise ValueError("live manifest changed during verification")
        except ValueError as error:
            raise ValueError(f"{profile[0]}: {error}") from error
    return {
        "site_rev": manifest["site_rev"],
        "entries": len(entries),
        "observations": observations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--attempts", type=int, default=1)
    parser.add_argument("--delay", type=float, default=15)
    args = parser.parse_args()
    if not 1 <= args.attempts <= 20 or not 0 <= args.delay <= 30:
        parser.error("attempts must be 1..20 and delay 0..30 seconds")
    expected = args.manifest.read_bytes()
    for attempt in range(1, args.attempts + 1):
        try:
            result = verify(args.base_url, expected)
        except (ValueError, requests.RequestException, OSError) as error:
            print(json.dumps({"attempt": attempt, "error": str(error)}), flush=True)
            if attempt < args.attempts:
                time.sleep(args.delay)
        else:
            print(json.dumps({"attempt": attempt, "verified": result}, indent=2))
            return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
