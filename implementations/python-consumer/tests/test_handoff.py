from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_recurring import Origin

from pagedigest import cli
from pagedigest.handoff import _dump, _hash, _stamp, export_finding, receive_finding
from pagedigest.persistence import save_state
from pagedigest.recurring import inspect_state, read_state, remember, sync


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sender = self.root / "sender.json"
        self.recipient = self.root / "recipient.json"
        self.origin = Origin()
        self.origin.page("/setup", b"Requires Python 3.9 or newer.", cache="no-cache")
        self.origin.page("/limits", b"Only a setup claim.", cache="no-cache")
        self.cycle(self.sender)
        self.cycle(self.recipient)
        remember(self.sender, "runtime", "Use Python 3.9 or newer.", ["/setup", "/limits"], now=101)
        self.meta = self.root / "meta.json"
        self.meta.write_bytes(
            _dump(
                {
                    "taskScope": "Which setup runtime?",
                    "assumptions": [],
                    "limitations": ["No execution check."],
                    "attribution": {"author": "reader-a"},
                }
            )
        )
        self.exported = self.export()
        self.envelope = Path(self.exported["envelope"])

    def cycle(self, state, now=100, language=""):
        return sync(
            "https://example.com",
            state,
            urls=["/setup", "/limits"],
            session=self.origin,
            now=now,
            audit_rate=0,
            http_only=True,
            max_age=60,
            language=language,
        )

    def export(self, **kwargs):
        return export_finding(self.sender, "runtime", self.meta, self.root / "sender-sidecar", now=110, **kwargs)

    def receive(self, **kwargs):
        return receive_finding(
            self.recipient,
            self.envelope,
            "Which setup runtime?",
            "test-policy",
            40,
            self.root / "recipient-sidecar",
            now=111,
            **kwargs,
        )

    def review(self, disposition="accepted", **updates):
        value = {
            "envelopeDigest": self.exported["envelopeDigest"],
            "disposition": disposition,
            "reviewer": "reader-b",
            "reviewedAt": _stamp(111),
            "taskScope": "Which setup runtime?",
            "completeSourceScope": True,
            "note": "Reviewed the complete declared source scope.",
        }
        value.update(updates)
        path = self.root / "review.json"
        path.write_bytes(_dump(value))
        return path

    def test_original_time_round_trip_preserves_float_receipt_precision(self):
        from pagedigest.handoff import _date

        for value in (100, 100.0, 1793847772.3901591, 1793847848.726466):
            self.assertEqual(_date(_stamp(value)), value)

    def test_export_preserves_actual_finding_and_original_time_across_later_sync(self):
        self.cycle(self.sender, now=109)
        result = self.export()
        value = json.loads(Path(result["envelope"]).read_bytes())
        self.assertEqual(value["claim"]["text"], "Use Python 3.9 or newer.")
        self.assertEqual(value["findingCreatedAt"], _stamp(101))
        self.assertEqual({s["originalObservedAt"] for s in value["sources"]}, {_stamp(100)})
        self.assertEqual(inspect_state(self.sender, now=110)["sources"]["/setup"]["validated_at"], 109)
        self.assertFalse(result["originalTimeUnknown"])

    def test_source_state_read_only_no_network_and_immutable_original_conflicting_receipts(self):
        before = {p: p.read_bytes() for p in self.root.glob("*.json")}
        with patch("pagedigest.recurring.requests.Session", side_effect=AssertionError("HTTP forbidden")):
            result = self.receive()
            self.assertEqual(result["sourceStatus"], "current")
            self.assertEqual(result["interpretation"]["disposition"], "unreviewed")
            conflict = self.receive(review_file=self.review("conflicting", note="The wording is ambiguous."))
        self.assertEqual(conflict["sourceStatus"], "current")
        self.assertEqual(conflict["interpretation"]["disposition"], "conflicting")
        self.assertNotEqual(result["receiptDigest"], conflict["receiptDigest"])
        self.assertTrue(Path(result["receipt"]).is_file())
        self.assertEqual(Path(conflict["envelope"]).read_bytes(), self.envelope.read_bytes())
        self.assertEqual({p: p.read_bytes() for p in before}, before)

    def test_accepted_review_requires_complete_scope_digest_time_and_attribution(self):
        result = self.receive(review_file=self.review())
        self.assertEqual(result["interpretation"]["disposition"], "accepted")
        for updates in (
            {"completeSourceScope": False},
            {"envelopeDigest": "0" * 64},
            {"reviewedAt": _stamp(112)},
            {"taskScope": "Broader task"},
            {"completeSourceScope": 1},
            {"reviewedAt": _stamp(100)},
        ):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                self.receive(review_file=self.review(**updates))

    def test_legacy_unknown_never_uses_latest_validation(self):
        state = read_state(self.sender)
        del state["findings"]["runtime"]["original_observed_at"]
        save_state(self.sender, state)
        self.cycle(self.sender, now=109)
        exported = self.export()
        envelope = json.loads(Path(exported["envelope"]).read_bytes())
        self.assertTrue(all(s["originalObservedAt"] is None for s in envelope["sources"]))
        self.assertEqual(envelope["findingCreatedAt"], _stamp(101))
        self.envelope = Path(exported["envelope"])
        self.exported = exported
        received = self.receive()
        self.assertEqual(received["sourceStatus"], "current")
        self.assertIn("original-source-time-unknown", received["interpretationBlockers"])
        with self.assertRaisesRegex(ValueError, "accepted-review-requires"):
            self.receive(review_file=self.review())

    def test_contemporaneous_original_inspect_receipt_supplies_time_and_refuses_later_proof(self):
        state = read_state(self.sender)
        del state["findings"]["runtime"]["original_observed_at"]
        save_state(self.sender, state)
        original = inspect_state(self.sender, now=102)
        evidence = self.root / "evidence"
        evidence.mkdir()
        receipt = evidence / "original.json"
        receipt.write_bytes(_dump(original))
        self.cycle(self.sender, now=109)
        exported = self.export(evidence_root=evidence, original_receipt="original.json")
        envelope = json.loads(Path(exported["envelope"]).read_bytes())
        self.assertEqual({s["originalObservedAt"] for s in envelope["sources"]}, {_stamp(100)})
        self.assertEqual(envelope["originEvidence"]["originalReceipt"]["hash"], _hash(receipt.read_bytes()))
        for change in ("future", "binding", "later-validation", "later-inspection", "finding"):
            altered = json.loads(_dump(original))
            if change == "future":
                altered["inspected_at"] = 111
            elif change == "binding":
                altered["sources"]["/setup"]["hash"] = "sha256:" + "0" * 64
            elif change == "later-validation":
                altered["sources"]["/setup"]["validated_at"] = 105
            elif change == "later-inspection":
                altered["inspected_at"] = 10000
            else:
                altered["findings"][0]["text"] = "A changed claim"
            receipt.write_bytes(_dump(altered))
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.export(evidence_root=evidence, original_receipt="original.json")
        with self.assertRaises(ValueError):
            self.export(evidence_root=evidence, original_receipt="../meta.json")

    def test_original_state_receipt_and_temporal_uncertainty_are_separate_from_recipient_freshness(self):
        state = read_state(self.sender)
        del state["findings"]["runtime"]["original_observed_at"]
        save_state(self.sender, state)
        evidence = self.root / "evidence"
        evidence.mkdir()
        proof = evidence / "state.json"
        proof.write_bytes(self.sender.read_bytes())
        exported = self.export(evidence_root=evidence, original_receipt="state.json")
        self.envelope = Path(exported["envelope"])
        self.exported = exported
        self.cycle(self.recipient, now=1000)
        received = receive_finding(
            self.recipient,
            self.envelope,
            "Which setup runtime?",
            "fresh",
            10,
            self.root / "recipient-sidecar",
            now=1001,
        )
        self.assertEqual(received["sourceStatus"], "current")
        self.assertEqual(received["interpretationBlockers"], [])

    def test_changed_missing_corrupt_and_precedence(self):
        self.origin.page("/setup", b"Requires Python 3.12.", cache="no-cache")
        self.cycle(self.recipient, now=110)
        state = read_state(self.recipient)
        missing = Path(str(self.recipient) + ".pages") / state["pages"]["/limits"]
        missing.unlink()
        result = self.receive()
        self.assertEqual(result["sourceStatus"], "changed")
        self.assertEqual({s["sourceStatus"] for s in result["sources"]}, {"changed", "unknown"})
        with self.assertRaises(ValueError):
            self.receive(review_file=self.review())
        missing.write_bytes(b"bad body")
        result = self.receive()
        self.assertIn("recipient-body-missing-or-corrupt", result["sources"][0]["reasons"])

    def test_own_policy_expiry_failed_sync_and_representation(self):
        for policy in (0, -1, True, float("nan"), float("inf")):
            with self.subTest(policy=policy), self.assertRaises(ValueError):
                receive_finding(
                    self.recipient, self.envelope, "Which setup runtime?", "p", policy, self.root / "sidecar", now=111
                )
        expired = receive_finding(
            self.recipient, self.envelope, "Which setup runtime?", "p", 5, self.root / "sidecar", now=111
        )
        self.assertEqual(expired["sourceStatus"], "unknown")
        self.cycle(self.recipient, now=110, language="fr")
        result = self.receive()
        self.assertEqual(result["sourceStatus"], "unknown")
        self.assertTrue(all("recipient-representation-mismatch" in s["reasons"] for s in result["sources"]))

    def test_failed_sync_retains_bytes_without_current_source_authority(self):
        self.origin.routes["/setup"] = (503, b"temporarily unavailable")
        self.assertFalse(self.cycle(self.recipient, now=110)["complete"])
        result = self.receive()
        failed = next(source for source in result["sources"] if source["url"].endswith("/setup"))
        self.assertEqual(failed["sourceStatus"], "unknown")
        self.assertIsNotNone(failed["observedHash"])
        self.assertEqual(result["sourceStatus"], "unknown")

    def test_scope_mismatch_and_unknown_attribution_block_acceptance(self):
        result = receive_finding(
            self.recipient, self.envelope, "Broader task", "p", 40, self.root / "other-sidecar", now=111
        )
        self.assertFalse(result["taskScopeMatch"])
        self.assertIn("task-scope-mismatch", result["interpretationBlockers"])
        meta = json.loads(self.meta.read_bytes())
        meta["attribution"]["author"] = None
        self.meta.write_bytes(_dump(meta))
        self.exported = self.export()
        self.envelope = Path(self.exported["envelope"])
        self.assertIn("original-attribution-unknown", self.receive()["interpretationBlockers"])
        with self.assertRaises(ValueError):
            self.receive(review_file=self.review())

    def test_malformed_envelopes_refuse_before_any_output_writes(self):
        valid = self.envelope.read_bytes()
        variants = [
            b'{"format":"x","format":"y"}',
            b'{"bad":NaN}',
            b'{"bad":1e999}',
            b'{"bad":' + b"9" * 400 + b"}",
            b"[]",
            b"\xff",
            b"{" * 2000,
            valid + b" " * 65536,
        ]
        base = json.loads(valid)
        changes = [
            ("format", "new/2"),
            ("findingCreatedAt", _stamp(120)),
            ("exportedAt", _stamp(999)),
            ("sources", []),
            ("id", 4),
            ("taskScope", ""),
            ("claim", {"text": "x" * 32769}),
        ]
        for field, value in changes:
            altered = {**base, field: value}
            variants.append(_dump(altered))
        for field, value in (
            ("url", "https://other.invalid/setup"),
            ("url", "https://example.com/../x"),
            ("url", "https://a:b@example.com/setup"),
            ("hash", "sha256:" + "0" * 64),
            ("representation", "opaque-unsupported"),
            ("originalObservedAt", _stamp(200)),
            ("range", {"start": 1}),
        ):
            altered = json.loads(valid)
            altered["sources"][0][field] = value
            variants.append(_dump(altered))
        for index, raw in enumerate(variants):
            bad = self.root / "bad.json"
            bad.write_bytes(raw)
            output = self.root / ("no-output-" + str(index))
            with self.subTest(index=index), self.assertRaises(ValueError):
                receive_finding(self.recipient, bad, "Which setup runtime?", "p", 40, output, now=111)
            self.assertFalse(output.exists())

    def test_duplicate_state_keys_and_unsafe_paths_refused(self):
        original = self.recipient.read_bytes()
        self.recipient.write_bytes(original.replace(b'"workflow": 1', b'"workflow": 1, "workflow": 1'))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.receive()
        self.recipient.write_bytes(original)
        state = read_state(self.recipient)
        state["pages"]["/setup"] = "../other.body"
        save_state(self.recipient, state)
        with self.assertRaises(ValueError):
            self.receive()
        self.assertFalse((self.root / "recipient-sidecar").exists())

    def test_sidecar_capacity_integrity_and_sender_ids_never_control_paths(self):
        with patch("pagedigest.handoff.MAX_OBJECTS", 1), self.assertRaisesRegex(ValueError, "capacity"):
            self.receive()
        self.assertFalse((self.root / "recipient-sidecar").exists())
        result = self.receive()
        Path(result["receipt"]).write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "integrity"):
            self.receive()
        state = read_state(self.sender)
        state["findings"]["../../sender-controlled"] = state["findings"].pop("runtime")
        save_state(self.sender, state)
        exported = export_finding(self.sender, "../../sender-controlled", self.meta, self.root / "safe", now=110)
        self.assertRegex(Path(exported["envelope"]).name, r"^[0-9a-f]{64}\.json$")

    def test_expired_intact_changed_bytes_preserve_change_and_policy_uncertainty(self):
        self.origin.page("/setup", b"Requires Python 3.12.", cache="no-cache")
        self.cycle(self.recipient, now=110)
        result = receive_finding(
            self.recipient, self.envelope, "Which setup runtime?", "p", 40, self.root / "expired-changed", now=200
        )
        changed = next(s for s in result["sources"] if s["url"].endswith("/setup"))
        unchanged = next(s for s in result["sources"] if s["url"].endswith("/limits"))
        self.assertEqual(result["sourceStatus"], "changed")
        self.assertEqual(changed["sourceStatus"], "changed")
        self.assertEqual(unchanged["sourceStatus"], "unknown")
        self.assertIn("source-bytes-changed", changed["reasons"])
        self.assertIn("recipient-source-unavailable-or-policy-expired", changed["reasons"])

    def test_corrupt_prior_receipt_refuses_a_different_new_receipt_without_writes(self):
        initial = self.receive()
        Path(initial["receipt"]).write_bytes(b'{"tampered":true}')
        store = self.root / "recipient-sidecar"
        before = {p.relative_to(store): p.read_bytes() for p in store.rglob("*") if p.is_file()}
        with self.assertRaisesRegex(ValueError, "sidecar-object-integrity-failure"):
            receive_finding(self.recipient, self.envelope, "Which setup runtime?", "p", 40, store, now=112)
        after = {p.relative_to(store): p.read_bytes() for p in store.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_malformed_original_state_containers_fail_cli_without_writes(self):
        state = read_state(self.sender)
        del state["findings"]["runtime"]["original_observed_at"]
        save_state(self.sender, state)
        proof = self.root / "malformed-proof.json"
        store = self.root / "malformed-output"
        for field, value in (
            ("last_attempt", None),
            ("last_attempt", []),
            ("body_hashes", []),
            ("body_hashes", None),
            ("findings", []),
            ("resources", []),
        ):
            invalid = {**state, field: value}
            proof.write_bytes(_dump(invalid))
            out, err = io.StringIO(), io.StringIO()
            before = self.sender.read_bytes()
            with self.subTest(field=field, value=value):
                status = cli.main(
                    [
                        "handoff-export",
                        str(self.sender),
                        "--id",
                        "runtime",
                        "--metadata-file",
                        str(self.meta),
                        "--store",
                        str(store),
                        "--evidence-root",
                        str(self.root),
                        "--original-receipt",
                        proof.name,
                    ],
                    stdout=out,
                    stderr=err,
                )
                self.assertEqual(status, 1)
                self.assertEqual(out.getvalue(), "")
                self.assertIn("workflow error: invalid-original-state-receipt", err.getvalue())
                self.assertFalse(store.exists())
                self.assertEqual(self.sender.read_bytes(), before)

    def test_sender_locators_never_dereferenced(self):
        value = json.loads(self.envelope.read_bytes())
        value["originEvidence"]["originalReceipt"] = {"locator": "must-not-open.json", "hash": "f" * 64}
        changed = self.root / "relocated.json"
        changed.write_bytes(_dump(value))
        self.envelope = changed
        self.assertEqual(self.receive()["sourceStatus"], "current")

    def test_cli_export_receive_and_error(self):
        output, error = io.StringIO(), io.StringIO()
        args = [
            "handoff-export",
            str(self.sender),
            "--id",
            "runtime",
            "--metadata-file",
            str(self.meta),
            "--store",
            str(self.root / "cli-store"),
        ]
        with patch("pagedigest.handoff.time.time", return_value=110):
            self.assertEqual(cli.main(args, stdout=output, stderr=error), 0)
        envelope = json.loads(output.getvalue())["envelope"]
        output = io.StringIO()
        with patch("pagedigest.handoff.time.time", return_value=111):
            code = cli.main(
                [
                    "handoff-receive",
                    str(self.recipient),
                    envelope,
                    "--scope",
                    "Which setup runtime?",
                    "--policy-id",
                    "test",
                    "--max-age",
                    "40",
                    "--store",
                    str(self.root / "cli-receive"),
                ],
                stdout=output,
                stderr=error,
            )
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["sourceStatus"], "current")
        args[args.index("runtime")] = "absent"
        self.assertEqual(cli.main(args, stdout=io.StringIO(), stderr=error), 1)
        self.assertIn("finding-not-found", error.getvalue())


if __name__ == "__main__":
    unittest.main()
