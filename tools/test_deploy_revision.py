from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

GUARD = Path(__file__).with_name("check_deploy_revision.sh")


class DeploymentRevisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git("init", "--initial-branch=main")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Revision Test")
        self.git("commit", "--allow-empty", "-m", "initial")
        self.sha = self.git("rev-parse", "HEAD")
        self.git("remote", "add", "origin", str(self.root))

    def git(self, *args):
        return subprocess.check_output(
            ["git", *args], cwd=self.root, stderr=subprocess.PIPE, text=True
        ).strip()

    def guard(self, before_upload=False, **overrides):
        env = dict(
            os.environ,
            GITHUB_REF="refs/heads/main",
            GITHUB_EVENT_NAME="push",
            GITHUB_SHA=self.sha,
            CHECKED_SHA=self.sha,
        )
        env.update(overrides)
        return subprocess.run(
            ["bash", str(GUARD), *(["--before-upload"] if before_upload else [])],
            cwd=self.root,
            env=env,
            capture_output=True,
            text=True,
        )

    def test_exact_main_push_and_manual_revision_pass(self):
        self.assertEqual(self.guard().returncode, 0)
        self.assertEqual(self.guard(before_upload=True).returncode, 0)
        self.assertEqual(
            self.guard(
                before_upload=True,
                GITHUB_EVENT_NAME="workflow_dispatch",
                CHECKED_SHA="",
            ).returncode,
            0,
        )

    def test_non_main_unsupported_event_and_unbound_checkout_fail(self):
        for overrides in (
            {"GITHUB_REF": "refs/heads/topic"},
            {"GITHUB_EVENT_NAME": "pull_request"},
            {"GITHUB_EVENT_NAME": "schedule"},
            {"CHECKED_SHA": ""},
            {"CHECKED_SHA": "f" * 40},
            {"GITHUB_SHA": "f" * 40, "CHECKED_SHA": "f" * 40},
            {"GITHUB_SHA": ""},
        ):
            with self.subTest(overrides=overrides):
                self.assertNotEqual(self.guard(**overrides).returncode, 0)

    def test_new_main_after_checkout_refuses_stale_automatic_and_manual_upload(self):
        self.git("commit", "--allow-empty", "-m", "new main")
        self.git("checkout", "--detach", self.sha)
        self.assertEqual(self.guard().returncode, 0)
        for event in ("push", "workflow_dispatch"):
            result = self.guard(before_upload=True, GITHUB_EVENT_NAME=event)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Refusing stale main deployment", result.stderr)

    def test_missing_remote_refuses_upload(self):
        self.git("remote", "remove", "origin")
        self.assertNotEqual(self.guard(before_upload=True).returncode, 0)


if __name__ == "__main__":
    unittest.main()
