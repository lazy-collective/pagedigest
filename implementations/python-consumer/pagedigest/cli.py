from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from .core import DEFAULT_MAX_AUDIT_BYTES, DEFAULT_MAX_MANIFEST_BYTES, verify_live


def _add_verify_live_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("base_url", help="Site base URL, e.g. https://example.com")
    parser.add_argument(
        "--manifest-url",
        help="Override manifest URL (defaults to /.well-known/pagedigest.json)",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=25,
        help="Number of digest entries to sample",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic sampling",
    )
    parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout seconds")
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=DEFAULT_MAX_AUDIT_BYTES,
        help="Abort identity fetches larger than this many bytes",
    )
    parser.add_argument(
        "--manifest-max-bytes",
        type=int,
        default=DEFAULT_MAX_MANIFEST_BYTES,
        help="Abort manifest fetches larger than this many bytes",
    )


def _run_verify_live(args: argparse.Namespace, stdout: TextIO, stderr: TextIO) -> int:
    if args.sample_size < 0:
        print("sample-size must be non-negative", file=stderr)
        return 1
    if args.timeout <= 0:
        print("timeout must be positive", file=stderr)
        return 1
    if args.max_bytes <= 0:
        print("max-bytes must be positive", file=stderr)
        return 1
    if args.manifest_max_bytes <= 0:
        print("manifest-max-bytes must be positive", file=stderr)
        return 1

    result = verify_live(
        args.base_url,
        manifest_url_override=args.manifest_url,
        sample_size=args.sample_size,
        seed=args.seed,
        timeout=args.timeout,
        max_bytes=args.max_bytes,
        manifest_max_bytes=args.manifest_max_bytes,
    )

    print(f"manifest: {result.get('manifest_url')}", file=stdout)
    if not result.get("ok"):
        error = result.get("error") or "unknown-error"
        status_code = result.get("status_code")
        suffix = f":{status_code}" if status_code is not None else ""
        print(f"error: {error}{suffix}", file=stderr)
        return 1

    print(f"sampled: {result['sampled']}", file=stdout)
    print(f"match: {result['match_count']}", file=stdout)
    print(f"mismatch: {result['mismatch_count']}", file=stdout)
    print(f"inconclusive: {result['inconclusive_count']}", file=stdout)

    for item in result["results"]:
        if item["status"] != "match":
            print(f"- {item['status']}: {item['url']} ({item['detail']})", file=stdout)

    if result["mismatch_count"] > 0:
        return 2
    return 0


def verify_live_main(
    argv: Sequence[str] | None = None, stdout: TextIO | None = None, stderr: TextIO | None = None
) -> int:
    parser = argparse.ArgumentParser(description="Verify pagedigest digest values over the wire")
    _add_verify_live_args(parser)
    return _run_verify_live(parser.parse_args(argv), stdout or sys.stdout, stderr or sys.stderr)


def main(argv: Sequence[str] | None = None, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pagedigest")
    subcommands = parser.add_subparsers(dest="command")
    verify_parser = subcommands.add_parser("verify-live", help="Verify manifest digests against live responses")
    _add_verify_live_args(verify_parser)

    sync_parser = subcommands.add_parser("sync", help="Run one bounded recurring source/finding update (experimental)")
    sync_parser.add_argument("base_url")
    sync_parser.add_argument("state", type=Path)
    sync_parser.add_argument("--url", action="append", dest="urls", help="Origin-relative source URL; repeat as needed")
    sync_parser.add_argument("--sitemap", help="Origin-relative urlset for discovery, e.g. /sitemap.xml")
    sync_parser.add_argument(
        "--prefix",
        action="append",
        dest="prefixes",
        help="Limit manifest/sitemap discovery to this origin-relative path prefix; repeat as needed",
    )
    sync_parser.add_argument("--http-only", action="store_true", help="Use HTTP without requesting PageDigest")
    sync_parser.add_argument("--max-age", type=float, default=3600, help="Maximum seconds since body validation")
    sync_parser.add_argument("--audit-rate", type=float, default=0.01)
    sync_parser.add_argument("--language", default="", help="Fixed Accept-Language representation")
    sync_parser.add_argument("--max-requests", type=int, default=250)
    sync_parser.add_argument("--max-bytes", type=int, default=50 * 1024 * 1024)

    remember_parser = subcommands.add_parser("remember", help="Retain a finding bound to synchronized sources")
    remember_parser.add_argument("state", type=Path)
    remember_parser.add_argument("--id", required=True, dest="finding_id")
    remember_parser.add_argument("--text-file", type=Path, required=True)
    remember_parser.add_argument("--source", action="append", required=True, dest="sources")

    inspect_parser = subcommands.add_parser(
        "inspect", help="Read saved findings and source bindings without network access"
    )
    inspect_parser.add_argument("state", type=Path)
    inspect_parser.add_argument("--id", dest="finding_id", help="Return one saved finding")
    inspect_parser.add_argument("--source", help="Include one retained UTF-8 source body by origin-relative URL")
    inspect_parser.add_argument(
        "--brief",
        action="store_true",
        help="Show one finding, its dependencies and read/recovery guidance; requires --id, excludes --source",
    )

    export_parser = subcommands.add_parser("handoff-export", help="Export one experimental offline finding")
    export_parser.add_argument("state", type=Path)
    export_parser.add_argument("--id", required=True, dest="finding_id")
    export_parser.add_argument("--metadata-file", required=True, type=Path)
    export_parser.add_argument("--store", required=True, type=Path)
    export_parser.add_argument("--evidence-root", type=Path)
    export_parser.add_argument("--original-receipt")

    receive_parser = subcommands.add_parser("handoff-receive", help="Check an offline finding against own cache")
    receive_parser.add_argument("state", type=Path)
    receive_parser.add_argument("envelope", type=Path)
    receive_parser.add_argument("--scope", required=True)
    receive_parser.add_argument("--policy-id", required=True)
    receive_parser.add_argument("--max-age", required=True, type=float)
    receive_parser.add_argument("--store", required=True, type=Path)
    receive_parser.add_argument("--review-file", type=Path)

    args = parser.parse_args(argv)
    if args.command == "verify-live":
        return _run_verify_live(args, stdout or sys.stdout, stderr or sys.stderr)
    if args.command in ("handoff-export", "handoff-receive"):
        from .handoff import export_finding, receive_finding

        try:
            if args.command == "handoff-export":
                result = export_finding(
                    args.state,
                    args.finding_id,
                    args.metadata_file,
                    args.store,
                    evidence_root=args.evidence_root,
                    original_receipt=args.original_receipt,
                )
            else:
                result = receive_finding(
                    args.state,
                    args.envelope,
                    args.scope,
                    args.policy_id,
                    args.max_age,
                    args.store,
                    review_file=args.review_file,
                )
            print(json.dumps(result, indent=2), file=stdout or sys.stdout)
            return 0
        except (OSError, ValueError) as exc:
            print(f"workflow error: {exc}", file=stderr or sys.stderr)
            return 1

    if args.command in ("sync", "remember", "inspect"):
        from .recurring import inspect_state, remember, sync

        try:
            if args.command == "inspect":
                result = inspect_state(args.state, finding_id=args.finding_id, source=args.source, brief=args.brief)
            elif args.command == "remember":
                if args.text_file.stat().st_size > 32768:
                    raise ValueError("finding text exceeds32KiB")
                result = remember(args.state, args.finding_id, args.text_file.read_text(), args.sources)
            else:
                result = sync(
                    args.base_url,
                    args.state,
                    urls=args.urls,
                    sitemap=args.sitemap,
                    prefixes=args.prefixes,
                    http_only=args.http_only,
                    max_age=args.max_age,
                    audit_rate=args.audit_rate,
                    language=args.language,
                    max_requests=args.max_requests,
                    max_bytes=args.max_bytes,
                )
            print(json.dumps(result, indent=2), file=stdout or sys.stdout)
            return 0 if result.get("complete", True) else 2
        except (OSError, ValueError) as exc:
            print(f"workflow error: {exc}", file=stderr or sys.stderr)
            return 1

    parser.print_help(stderr or sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
