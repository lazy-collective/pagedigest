"""Publisher setup/update controls with the actual first-party Rust generator."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_core import load_tool


class PublisherWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tool = load_tool("publisher_workflow")
        cls.generator = Path(os.environ.get("PAGEDIGEST_GENERATOR", str(cls.tool.DEFAULT_GENERATOR))).resolve()
        if not cls.generator.is_file():
            subprocess.run(
                ["cargo", "build", "--locked"],
                cwd=cls.tool.ROOT / "implementations/rust-generator",
                check=True,
                timeout=180,
            )

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.build = self.root / "dist"
        self.build.mkdir()
        (self.build / "index.html").write_text("<h1>Local publisher fixture</h1>")
        self.state = self.root / "durable/state.json"

    def prepare(self, **kwargs):
        return self.tool.prepare(self.build, self.state, generator=self.generator, **kwargs)

    def initialize(self):
        return self.prepare(initialize=True, coverage="complete", apply=True)

    def test_first_setup_requires_only_explicit_history_and_coverage_decisions(self):
        result = self.prepare()
        self.assertEqual(result["state"], "needs-clarification")
        self.assertEqual(len(result["clarifications"]), 2)
        preview = self.prepare(initialize=True, coverage="complete")
        self.assertEqual(preview["changes"]["added"], ["/"])
        self.assertFalse(self.state.exists())
        self.assertFalse((self.build / ".well-known/pagedigest.json").exists())
        result = self.initialize()
        self.assertTrue(result["applied"])
        self.assertTrue(self.state.exists())
        self.assertEqual(result["siteRevision"], 1)

    def test_repeat_update_removal_and_readd_preserve_revision_history(self):
        self.initialize()
        initial_state = self.state.read_bytes()
        same = self.prepare()
        self.assertEqual(same["state"], "unchanged")
        self.assertEqual(self.state.read_bytes(), initial_state)
        (self.build / "index.html").write_text("<h1>Updated content</h1>")
        changed = self.prepare(apply=True)
        self.assertEqual(changed["changes"]["changed"], ["/"])
        self.assertEqual(changed["siteRevision"], 2)
        (self.build / "index.html").unlink()
        removed = self.prepare(apply=True)
        self.assertEqual(removed["changes"]["removed"], ["/"])
        (self.build / "index.html").write_text("<h1>Updated content</h1>")
        self.prepare(apply=True)
        manifest = json.loads((self.build / ".well-known/pagedigest.json").read_text())
        self.assertGreaterEqual(manifest["entries"]["/"]["rev"], 2)
        self.assertGreater(manifest["site_rev"], removed["siteRevision"])

    def test_missing_state_cannot_silently_reinitialize_published_manifest(self):
        self.initialize()
        self.state.unlink()
        manifest = self.build / ".well-known/pagedigest.json"
        before = manifest.read_bytes()
        result = self.prepare(initialize=True, coverage="complete", apply=True)
        self.assertEqual(result["state"], "needs-clarification")
        self.assertIn("restore state", result["clarifications"][0])
        self.assertEqual(manifest.read_bytes(), before)
        self.assertFalse(self.state.exists())

    def test_partial_coverage_is_inherited_without_another_catalog(self):
        docs = self.build / "docs"
        docs.mkdir()
        (docs / "index.html").write_text("<h1>Docs</h1>")
        result = self.prepare(initialize=True, coverage="prefixes", prefixes=["/docs/"], apply=True)
        self.assertEqual(result["changes"]["added"], ["/docs/"])
        same = self.prepare()
        self.assertEqual(same["state"], "unchanged")
        self.assertEqual(same["policy"]["prefixes"], ["/docs/"])

    def test_state_inside_build_and_symlink_output_refuse_without_writes(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            self.tool.prepare(self.build, self.build / "state.json", generator=self.generator)
        external = self.root / "external"
        external.mkdir()
        (self.build / ".well-known").symlink_to(external, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.initialize()
        self.assertEqual(list(external.iterdir()), [])

    def test_digest_choice_is_explicit_and_no_live_reconciliation_is_claimed(self):
        result = self.prepare(initialize=True, coverage="complete", with_digest=True, apply=True)
        self.assertIn("reconcile", result["nextSteps"][1])
        same = self.prepare()
        self.assertTrue(same["policy"]["withDigest"])
        self.assertEqual(same["state"], "unchanged")

    def test_malformed_state_fails_without_reset(self):
        self.initialize()
        self.state.write_text('{"site_rev": 9, "entries": []}')
        before = self.state.read_bytes()
        with self.assertRaisesRegex(TypeError, "entries object"):
            self.prepare(apply=True)
        self.assertEqual(self.state.read_bytes(), before)

    def test_failed_manifest_write_retains_high_water_for_recovery(self):
        self.initialize()
        (self.build / "index.html").write_text("<h1>New content</h1>")
        actual_run = self.tool.run_generator
        manifest = (self.build / ".well-known/pagedigest.json").resolve()
        old_manifest = manifest.read_bytes()

        def interfere(generator, build, state, output, **kwargs):
            if output == manifest:
                # Simulate a concurrent output failure after the read-only
                # staging pass; the actual Rust generator must retain state.
                manifest.unlink()
                manifest.mkdir()
            return actual_run(generator, build, state, output, **kwargs)

        with patch.object(self.tool, "run_generator", side_effect=interfere):
            with self.assertRaisesRegex(ValueError, "generator refused"):
                self.prepare(apply=True)
        advanced = json.loads(self.state.read_text())
        self.assertEqual(advanced["site_rev"], 2)
        manifest.rmdir()
        manifest.write_bytes(old_manifest)
        recovered = self.prepare(apply=True)
        self.assertEqual(recovered["siteRevision"], 2)
        self.assertEqual(json.loads(manifest.read_text())["entries"]["/"]["rev"], 2)


if __name__ == "__main__":
    unittest.main()
