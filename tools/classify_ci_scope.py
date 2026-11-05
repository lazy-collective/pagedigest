#!/usr/bin/env python3
"""Select only an explicitly known prose-only PR for the fast documentation gate.

Main pushes and manual runs always use the complete suite. Git diff errors,
deletions, renames, empty changes and unrecognized paths also require it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROSE = frozenset(
    {
        "AGENTS.md",
        "CLAUDE.md",
        "ROADMAP.md",
        "docs/README.md",
        "docs/agent-execution.md",
        "docs/validation.md",
        "docs/DOGFOOD_TEMPLATE.md",
        "docs/ecosystem.md",
        "docs/visual-family.md",
        ".agents/skills/roadmap-coordination/SKILL.md",
    }
)


def classify(root: Path, base: str, head: str, event: str) -> dict:
    result = {
        "mode": "full",
        "reason": "main/manual/unknown event requires full checks",
        "changes": [],
    }
    if event != "pull_request":
        return result
    if not all(
        isinstance(value, str)
        and re.fullmatch(r"[0-9a-fA-F]{40}", value)
        and int(value, 16)
        for value in (base, head)
    ):
        result["reason"] = "missing or invalid Git boundary"
        return result
    try:
        raw = subprocess.check_output(
            ["git", "diff", "--name-status", "-z", "--no-renames", base, head, "--"],
            cwd=root,
            stderr=subprocess.PIPE,
        ).decode("utf-8")
    except (OSError, subprocess.CalledProcessError, UnicodeError):
        result["reason"] = "Git comparison unavailable"
        return result
    fields = raw.split("\0")
    if fields[-1:] == [""]:
        fields.pop()
    if not fields or len(fields) % 2:
        result["reason"] = "empty or malformed change set"
        return result
    changes = list(zip(fields[::2], fields[1::2]))
    result["changes"] = [{"status": status, "path": path} for status, path in changes]
    if any(status not in {"A", "M"} or path not in PROSE for status, path in changes):
        result["reason"] = "change is outside the explicit prose allowlist"
        return result
    result.update(mode="docs", reason="only added/modified allowlisted prose")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="")
    parser.add_argument("--head", default="")
    parser.add_argument("--event", default="pull_request")
    parser.add_argument("--github-event", type=Path)
    args = parser.parse_args()
    base, head, event = args.base, args.head, args.event
    if args.github_event:
        event = os.environ.get("GITHUB_EVENT_NAME", "unknown")
        try:
            payload = json.loads(args.github_event.read_text())
            base = payload.get("pull_request", {}).get("base", {}).get("sha", "")
            head = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip()
        except (OSError, ValueError, subprocess.CalledProcessError, AttributeError):
            base, head = "", ""
    result = classify(ROOT, base, head, event)
    print(json.dumps(result, indent=2))
    if output := os.environ.get("GITHUB_OUTPUT"):
        with open(output, "a", encoding="utf-8") as stream:
            stream.write(f"mode={result['mode']}\n")


if __name__ == "__main__":
    main()
