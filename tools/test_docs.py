from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from check_docs import anchors, check


class ReferenceTests(unittest.TestCase):
    def test_relative_escape_and_symlink_escape_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            outer = Path(tmp)
            root = outer / "repo"
            root.mkdir()
            (outer / "outside.md").write_text("# Private\n")
            (root / "escape.md").symlink_to(outer / "outside.md")
            (root / "README.md").write_text(
                "[outside](../outside.md#private)\n[link](escape.md)\n"
            )
            self.assertEqual(len(check(root, ["README.md"])), 2)
            self.assertEqual(len(check(root, ["../outside.md"])), 1)

    def test_missing_target_and_fragment_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("[lost](gone.md)\n[bad](other.md#absent)\n")
            (root / "other.md").write_text("# Present\n")
            self.assertEqual(len(check(root, ["README.md"])), 2)

    def test_relative_unicode_duplicate_and_explicit_anchors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "README.md").write_text('# Café\n# Café\n<a id="old-link"></a>\n')
            (root / "docs/guide.md").write_text(
                "[one](../README.md#caf%C3%A9)\n[two](../README.md#café-1)\n[old](../README.md#old-link)\n"
            )
            self.assertEqual(check(root, ["docs/guide.md"]), [])

    def test_code_examples_and_external_paths_are_not_local_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                "````md\n[example](missing.md)\n```\n[still example](gone.md)\n````\n"
                "[external](https://example.com/no.md)\n[site](/docs/)\n"
            )
            self.assertEqual(check(root, ["README.md"]), [])
            self.assertEqual(anchors("# Name\n# Name\n"), {"name", "name-1"})


if __name__ == "__main__":
    unittest.main()
