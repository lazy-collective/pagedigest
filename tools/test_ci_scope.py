from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from classify_ci_scope import classify


class ScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Scope test")
        self.git("config", "user.email", "scope@example.invalid")
        self.write("ROADMAP.md", "base")
        self.write("SPEC.md", "normative")
        self.base = self.commit()

    def git(self, *args):
        return subprocess.check_output(
            ["git", *args], cwd=self.root, stderr=subprocess.PIPE, text=True
        ).strip()

    def write(self, path, text):
        out = self.root / path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text)

    def commit(self):
        self.git("add", "-A")
        self.git("commit", "-qm", "fixture")
        return self.git("rev-parse", "HEAD")

    def test_only_allowlisted_prose_can_use_fast_pr(self):
        self.write("ROADMAP.md", "updated")
        head = self.commit()
        self.assertEqual(
            classify(self.root, self.base, head, "pull_request")["mode"], "docs"
        )
        for event in ("push", "workflow_dispatch", "schedule", "unexpected"):
            self.assertEqual(
                classify(self.root, self.base, head, event)["mode"], "full"
            )

    def test_protocol_mixed_and_unknown_paths_require_full(self):
        for path in (
            "SPEC.md",
            "README.md",
            "docs/new-guide.md",
            "site/index.html",
            "test-vectors/example.md",
            "implementations/python-consumer/README.md",
            ".github/workflows/ci.yml",
        ):
            with self.subTest(path=path):
                self.git("reset", "--hard", self.base)
                self.write("ROADMAP.md", "updated")
                self.write(path, "changed")
                self.assertEqual(
                    classify(self.root, self.base, self.commit(), "pull_request")[
                        "mode"
                    ],
                    "full",
                )

    def test_delete_and_rename_require_full(self):
        (self.root / "ROADMAP.md").unlink()
        self.assertEqual(
            classify(self.root, self.base, self.commit(), "pull_request")["mode"],
            "full",
        )
        self.git("reset", "--hard", self.base)
        (self.root / "ROADMAP.md").rename(self.root / "AGENTS.md")
        self.assertEqual(
            classify(self.root, self.base, self.commit(), "pull_request")["mode"],
            "full",
        )

    def test_bad_or_empty_comparisons_require_full(self):
        for base, head in (
            ("", ""),
            (42, self.base),
            (None, self.base),
            ("0" * 40, self.base),
            ("f" * 40, self.base),
            (self.base, self.base),
        ):
            self.assertEqual(
                classify(self.root, base, head, "pull_request")["mode"], "full"
            )

    def test_docs_after_unpublished_site_change_still_get_full_main(self):
        self.write("site/index.html", "not yet successfully published")
        unpublished = self.commit()
        self.write("ROADMAP.md", "later prose")
        head = self.commit()
        self.assertEqual(
            classify(self.root, unpublished, head, "pull_request")["mode"], "docs"
        )
        self.assertEqual(classify(self.root, unpublished, head, "push")["mode"], "full")

    def test_workflow_entrypoint_uses_merge_checkout_and_fails_closed(self):
        self.write("ROADMAP.md", "updated")
        self.commit()
        self.write(
            "tools/classify_ci_scope.py",
            Path(__file__).with_name("classify_ci_scope.py").read_text(),
        )
        event = self.root / "event.json"
        output = self.root / "output.txt"
        for payload, mode in (
            ({"pull_request": {"base": {"sha": self.base}}}, "docs"),
            ({"pull_request": {"base": {"sha": 42}}}, "full"),
            ([], "full"),
        ):
            with self.subTest(payload=payload):
                event.write_text(json.dumps(payload))
                output.write_text("")
                result = subprocess.check_output(
                    [
                        sys.executable,
                        str(self.root / "tools/classify_ci_scope.py"),
                        "--github-event",
                        str(event),
                    ],
                    env=dict(
                        os.environ,
                        GITHUB_EVENT_NAME="pull_request",
                        GITHUB_OUTPUT=str(output),
                    ),
                    text=True,
                )
                self.assertEqual(json.loads(result)["mode"], mode)
                self.assertEqual(output.read_text(), f"mode={mode}\n")


if __name__ == "__main__":
    unittest.main()
