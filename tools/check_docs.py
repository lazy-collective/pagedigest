#!/usr/bin/env python3
"""Check repository Markdown file/fragment links without fetching external sites."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL = (
    "docs/archive/",
    "docs/announcements/",
    "docs/releases/",
    "docs/registrations/",
    "docs/case-studies/",
    "docs/benchmarks/digest-exchange-p1-20261029/",
    "docs/benchmarks/recurring-workflow-20261104/",
)


def prose(text: str) -> str:
    lines = []
    fence = ""
    for line in text.splitlines():
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if match:
            mark = match.group(1)
            if not fence:
                fence = mark
            elif mark[0] == fence[0] and len(mark) >= len(fence):
                fence = ""
            continue
        if not fence:
            lines.append(line)
    return "\n".join(lines)


def anchors(text: str) -> set[str]:
    text = prose(text)
    result = set(re.findall(r'<a\s+(?:id|name)=["\']([^"\']+)["\']', text))
    counts: dict[str, int] = {}
    for heading in re.findall(r"^#{1,6}\s+(.+?)\s*#*\s*$", text, re.MULTILINE):
        slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        number = counts.get(slug, 0)
        counts[slug] = number + 1
        result.add(slug if not number else f"{slug}-{number}")
    return result


def check(root: Path, paths: list[str]) -> list[str]:
    root = root.resolve()
    errors = []
    for name in paths:
        path = root / name
        if not path.resolve().is_relative_to(root):
            errors.append(f"{name}: Markdown input escapes repository")
            continue
        if not path.is_file():
            errors.append(f"{name}: missing Markdown input")
            continue
        text = prose(path.read_text(encoding="utf-8"))
        targets = re.findall(r"\]\((<[^>]+>|[^\s)]+)(?:\s+['\"][^)]*)?\)", text)
        targets += re.findall(r"^\s*\[[^\]]+\]:\s*(\S+)", text, re.MULTILINE)
        for target in targets:
            target = target.strip("<>")
            parsed = urlsplit(target)
            # Origin-relative examples and historical machine-local evidence are
            # not repository links. External availability is a separate check.
            if parsed.scheme or parsed.netloc or parsed.path.startswith("/"):
                continue
            dest = path.parent / unquote(parsed.path) if parsed.path else path
            if not dest.resolve().is_relative_to(root):
                errors.append(f"{name}: relative target escapes repository: {target}")
            elif not dest.exists():
                errors.append(f"{name}: missing target {target}")
            elif parsed.fragment and dest.suffix.lower() == ".md":
                if unquote(parsed.fragment) not in anchors(
                    dest.read_text(encoding="utf-8")
                ):
                    errors.append(f"{name}: missing fragment {target}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*")
    args = parser.parse_args()
    paths = args.paths
    if not paths:
        tracked = (
            subprocess.check_output(
                [
                    "git",
                    "ls-files",
                    "-z",
                    "--cached",
                    "--others",
                    "--exclude-standard",
                    "*.md",
                ],
                cwd=ROOT,
            )
            .decode()
            .rstrip("\0")
            .split("\0")
        )
        paths = [
            name
            for name in tracked
            if name != "design-qa.md" and not name.startswith(HISTORICAL)
        ]
    errors = check(ROOT, sorted(set(paths)))
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Markdown references checked in {len(set(paths))} documents")


if __name__ == "__main__":
    main()
