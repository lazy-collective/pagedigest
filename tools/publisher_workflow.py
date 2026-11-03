"""Preview or generate PageDigest from final build output with durable source state.

No page catalog is maintained: the existing generator discovers the build. The
default operation stages generation without changing build output or state.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GENERATOR = (
    ROOT / "implementations/rust-generator/target/debug/pagedigest-generator"
)
MAX_JSON = 10 * 1024 * 1024


def read_json(path):
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON:
        raise ValueError(f"regular JSON file up to 10 MiB required: {path}")
    with path.open("rb") as stream:
        body = stream.read(MAX_JSON + 1)
    if len(body) > MAX_JSON:
        raise ValueError(f"publisher JSON exceeds 10 MiB: {path}")
    value = json.loads(body)
    if not isinstance(value, dict) or not isinstance(value.get("entries"), dict):
        raise TypeError(
            f"publisher state/manifest must contain an entries object: {path}"
        )
    if type(value.get("site_rev")) is not int or value["site_rev"] < 0:
        raise ValueError(
            f"publisher state/manifest must contain a nonnegative site_rev: {path}"
        )
    if any(not isinstance(entry, dict) for entry in value["entries"].values()):
        raise ValueError(f"publisher entries must be objects: {path}")
    if value.get("coverage") is not None and not isinstance(value["coverage"], dict):
        raise ValueError(f"publisher coverage must be an object: {path}")
    return value


def meaningful(manifest):
    return {key: value for key, value in (manifest or {}).items() if key != "generated"}


def run_generator(
    generator, build, state, output, *, initialize, coverage, prefixes, with_digest
):
    command = [
        str(generator),
        str(build),
        "--state",
        str(state),
        "--output",
        str(output),
        "--coverage",
        coverage,
    ]
    if initialize:
        command.append("--init")
    if with_digest:
        command.append("--with-digest")
    for prefix in prefixes:
        command += ["--prefix", prefix]
    result = subprocess.run(
        command, capture_output=True, text=True, timeout=60, check=False
    )
    if result.returncode:
        raise ValueError("generator refused: " + result.stderr.strip())
    return command


def prepare(
    build,
    state,
    *,
    generator=DEFAULT_GENERATOR,
    initialize=False,
    coverage=None,
    prefixes=(),
    with_digest=None,
    apply=False,
):
    build, state, generator = build.resolve(), state.absolute(), generator.resolve()
    if not build.is_dir():
        raise ValueError("build must be an existing final-output directory")
    if state.is_symlink():
        raise ValueError("durable state may not be a symlink")
    state = state.resolve()
    if state.is_relative_to(build):
        raise ValueError("keep durable state outside the disposable build directory")
    output = build / ".well-known/pagedigest.json"
    if output.is_symlink() or output.parent.is_symlink():
        raise ValueError("manifest output may not traverse a symlink")
    previous = read_json(state)
    published = read_json(output)
    clarifications = []
    if previous is None:
        if published is not None:
            clarifications.append(
                "Manifest exists but durable state is missing: restore state or use the documented recovery procedure."
            )
        elif not initialize:
            clarifications.append(
                "For the first publication only, explicitly select --initialize; recurring builds must retain state."
            )
        if coverage is None:
            clarifications.append(
                "Declare --coverage complete only for the entire covered URL set; otherwise choose prefixes or none."
            )
    elif initialize:
        clarifications.append(
            "State already exists: omit --initialize on recurring builds."
        )
    prior_coverage = (previous or {}).get("coverage") or {}
    coverage = coverage or prior_coverage.get("mode", "none")
    if coverage not in {"complete", "prefixes", "none"}:
        raise ValueError("coverage must be complete, prefixes or none")
    prefixes = sorted(
        set(
            prefixes
            or (prior_coverage.get("prefixes", []) if coverage == "prefixes" else [])
        )
    )
    if coverage == "prefixes" and not prefixes:
        clarifications.append(
            "Prefix coverage requires at least one explicit origin-relative --prefix."
        )
    if coverage != "prefixes" and prefixes:
        raise ValueError("--prefix requires --coverage prefixes")
    if with_digest is None:
        with_digest = any(
            "digest" in entry for entry in (published or {}).get("entries", {}).values()
        )
    report = {
        "schemaVersion": 1,
        "state": "needs-clarification" if clarifications else "prepared",
        "build": str(build),
        "durableState": str(state),
        "manifest": str(output),
        "applied": False,
        "clarifications": clarifications,
        "policy": {
            "coverage": coverage,
            "prefixes": prefixes,
            "withDigest": with_digest,
        },
        "meaning": "Build-byte changes and covered inventory only. No deployment, served-byte verification, model call or savings claim.",
    }
    if clarifications:
        return report
    with tempfile.TemporaryDirectory(prefix="pagedigest-publisher-") as tmp:
        staging = Path(tmp)
        staged_state, staged_output = staging / "state.json", staging / "manifest.json"
        if previous is not None:
            staged_state.write_text(json.dumps(previous), encoding="utf-8")
        if published is not None:
            staged_output.write_text(json.dumps(published), encoding="utf-8")
        run_generator(
            generator,
            build,
            staged_state,
            staged_output,
            initialize=initialize,
            coverage=coverage,
            prefixes=prefixes,
            with_digest=with_digest,
        )
        candidate = read_json(staged_output)
        proposed_state = read_json(staged_state)
    if apply:
        # The generator re-reads current inputs and holds its own state lock. It
        # writes state before the manifest, preserving high-water marks on failure.
        # Recompute the report from actual output, not the disposable preview.
        run_generator(
            generator,
            build,
            state,
            output,
            initialize=initialize,
            coverage=coverage,
            prefixes=prefixes,
            with_digest=with_digest,
        )
        candidate, proposed_state = read_json(output), read_json(state)
        report["applied"] = True
    old_entries = (previous or {}).get("entries", {})
    new_entries = proposed_state["entries"]
    changes = {
        "added": sorted(set(new_entries) - set(old_entries)),
        "removed": sorted(set(old_entries) - set(new_entries)),
        "changed": sorted(
            url
            for url in old_entries.keys() & new_entries.keys()
            if old_entries[url]["digest"] != new_entries[url]["digest"]
        ),
    }
    report.update(
        changes=changes,
        unchanged=len(old_entries.keys() & new_entries.keys())
        - len(changes["changed"]),
        siteRevision=candidate["site_rev"],
        previousSiteRevision=(previous or {}).get("site_rev"),
        manifestChanged=meaningful(candidate) != meaningful(published),
        coverageChanged=(previous or {}).get("coverage")
        != proposed_state.get("coverage"),
        nextSteps=[
            "Run the same preparation with --apply after reviewing the changes."
            if not apply
            else "Persist and back up durable state; publish pages and manifest atomically, or pages first.",
            "After deployment, reconcile and verify served digests."
            if with_digest
            else "Digests are omitted; this manifest supplies publisher revision signals only.",
        ],
    )
    report["state"] = "changed" if report["manifestChanged"] else "unchanged"
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build", type=Path)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--generator", type=Path, default=DEFAULT_GENERATOR)
    parser.add_argument("--initialize", action="store_true")
    parser.add_argument("--coverage", choices=("complete", "prefixes", "none"))
    parser.add_argument("--prefix", action="append", default=[])
    digest = parser.add_mutually_exclusive_group()
    digest.add_argument("--with-digest", dest="with_digest", action="store_true")
    digest.add_argument("--without-digest", dest="with_digest", action="store_false")
    parser.set_defaults(with_digest=None)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 when output needs generation or clarification",
    )
    args = parser.parse_args(argv)
    try:
        result = prepare(
            args.build,
            args.state,
            generator=args.generator,
            initialize=args.initialize,
            coverage=args.coverage,
            prefixes=args.prefix,
            with_digest=args.with_digest,
            apply=args.apply,
        )
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        subprocess.TimeoutExpired,
    ) as error:
        print(json.dumps({"state": "blocked", "error": str(error)}))
        return 2
    print(json.dumps(result, indent=2))
    return int(
        result["state"] == "needs-clarification"
        or (args.check and result["state"] != "unchanged")
    )


if __name__ == "__main__":
    raise SystemExit(main())
