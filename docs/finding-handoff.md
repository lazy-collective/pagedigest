# Experimental offline finding handoff

This source-only adapter transfers one existing `remember` finding as
`lazycollective.finding-handoff/1`. It changes neither the PageDigest public
protocol nor the published consumer package. The source workflow and its
interpretation boundary are described in [recurring-consumer.md](recurring-consumer.md).
An envelope preserves a user interpretation. Intact source bindings do not
establish its correctness or complete dependency coverage.

From the locked source checkout, create an operator-authored metadata file:

```json
{
  "taskScope": "Which runtime does this setup page require? Scope: setup page at https://example.com only.",
  "assumptions": [],
  "limitations": ["No installation was executed."],
  "attribution": {"author": "reader-a", "product": "local reader", "recordId": "setup-note-1"}
}
```

`author` must be supplied explicitly; null retains unknown attribution. `product`
and `recordId` are optional, defaulting to `pagedigest` and the selected finding
ID. A supplied record ID must match the selected finding. Scope must be exact,
nonempty text, including the target and question. Assumptions and limitations
are explicit lists; their absence is refused. The caller supplies these original
context declarations because existing `remember` records contain claim text and
source bindings, rather than these additional fields.

```sh
uv run --project implementations/python-consumer --locked python -m pagedigest.cli handoff-export \
  ./sender.json --id setup-note-1 --metadata-file ./metadata.json --store ./sender-handoffs
```

The JSON result reports `envelopeDigest`, `envelope`, `originEvidence` and
`originalTimeUnknown`. Send the exact envelope file. The digest covers those
UTF-8 bytes. The sidecar also retains a selected local inspection snapshot whose
hash and content-addressed locator appear in `originEvidence`. Source URLs are
exact pre-redirect URLs constructed from the saved origin and original URL keys;
source hashes cover full bodies. The original finding text, ID, creation time,
representation and source bindings are preserved. Export does not renew source
age, modify recurring state, fetch bodies, or run source instructions.

Each source carries kind `page`, URL, plain lowercase SHA-256 `hash`, the
original opaque PageDigest representation digest, `originalObservedAt` and its
unknown reason when null. `revision` and `range` are null: the adapter does not
invent historical publisher revisions or claim excerpt hashes. Source IDs are
local labels. The envelope also carries top-level `taskScope`, `limitations`,
`assumptions`, attribution, origin, claim, original `findingCreatedAt`, separate
`exportedAt`, and provenance. Times are UTC RFC3339, preserving precision from
saved finite Unix timestamps. Sender status labels are not imported as authority.

New `remember` records persist `original_observed_at` per cited source at finding
creation. Later syncs preserve that map. Legacy findings export null times with
an explicit reason, even when current cache validation is recent. An optional
operator-selected original receipt can provide missing historical times:

```sh
uv run --project implementations/python-consumer --locked python -m pagedigest.cli handoff-export \
  ./sender.json --id setup-note-1 --metadata-file ./metadata.json --store ./sender-handoffs \
  --evidence-root ./original-evidence --original-receipt original-inspect.json
```

The operator must supply a genuinely original retained state or inspection
receipt, rather than a recreated receipt with backdated fields. The adapter
checks exact finding ID/text/creation/source hashes/representation and origin.
Original per-source validation must be no later than finding creation or receipt
time. A state receipt must have its last sync at or before finding creation; an
inspection receipt must be from creation through 60 seconds afterward. Future
receipts, later source validations, conflicting original maps and differing
bindings are refused. The proof's exact hash and safe relative locator are
preserved. Paths must stay inside the explicit evidence root, without symlinks
or traversal. A sender locator is provenance, not an instruction to a receiver;
receivers never open it. A matching hash authenticates bytes, not the author's
identity or the receipt's historical truth.

The recipient first observes its own sources through the existing approved
`sync` workflow, then checks the envelope offline:

```sh
uv run --project implementations/python-consumer --locked python -m pagedigest.cli handoff-receive \
  ./recipient.json ./transferred-envelope.json --scope 'Which runtime does this setup page require? Scope: setup page at https://example.com only.' \
  --policy-id local-source-policy-1 --max-age 3600 --store ./recipient-handoffs
```

Pass the exact original task scope; for real scripts use argument arrays or
appropriate shell quoting. `--max-age` is an explicit recipient freshness bound
in addition to the recipient state's saved policy. Neither source age is reset.
Known historical observation age does not replace current recipient validation;
a recent export does not improve either. The recipient validates its own origin,
representation, retained body integrity, availability and freshness before
comparing full-body hashes. Intact differing bytes establish `changed` even if
the recipient observation has expired; the receipt also preserves its policy
expiry/unavailability reason. Matching bytes require acceptable availability and
freshness to be `current`, otherwise they remain `unknown`. Aggregate precedence
is changed, then unknown, then current. Exact task-scope
matching, unknown attribution and unknown original time are reported separately.

Every receive preserves the exact original envelope and a separate immutable
`lazycollective.finding-receipt/1` object. The receipt includes envelope digest,
recipient policy/check time, per-source reasons/current observations,
`sourceStatus`, `taskScopeMatch`, interpretation blockers, integrity-read
accounting, and interpretation disposition. Default disposition is `unreviewed`,
including when all bytes are current. It neither calls `remember` nor creates a
recipient finding. A user can explicitly attach their own JSON review:

```json
{
  "envelopeDigest": "<64 lowercase hex characters>",
  "disposition": "conflicting",
  "reviewer": "reader-b",
  "reviewedAt": "2026-11-05T03:05:00Z",
  "taskScope": "<exact recipient scope>",
  "completeSourceScope": false,
  "note": "My interpretation differs for the following reason."
}
```

Add `--review-file ./own-review.json`. Dispositions are `accepted`, `rejected`
or `conflicting`; reviewer and explanation must be explicit, the digest and
scope must match, and review time must lie between original creation and this
check. `accepted` additionally requires all sources current, exact task scope,
known original observation times, known original attribution and the reviewer's
explicit `completeSourceScope: true` declaration. That declaration is a reviewed
assertion about dependencies, not inferred evidence of completeness. Conflicting
and rejected reviews may accompany current source bytes. Differing receipts
remain alongside each other without replacing the original.

Inputs refuse unsupported formats, extra/missing fields, duplicate keys,
nonfinite values, malformed types/times/digests/URLs, unsafe paths and oversized
objects before writing outputs. Envelopes are at most 64 KiB, claims 32 KiB,
source lists 1–16. Sidecars contain at most 128 content-addressed JSON objects
and 16 MiB, including provenance snapshots and all differing receipts. Capacity
exhaustion fails rather than evicting old interpretations. Every append first
checks the content-address hash and JSON integrity of all existing sidecar
objects, including older receipts, within these same count and byte bounds.
Corruption refuses the append without replacing or repairing old objects. Use one local writer;
a sidecar `.lock` refuses concurrent mutation and needs operator inspection
after a crash. The caller chooses the sidecar directory. No sender ID or locator
chooses a write destination. Existing source states and body stores are read
only and must not have concurrent writers. Handing a file to this adapter never
requests HTTP, model inference, code execution, scheduling or publication.

Receipts count completed source-integrity reads and bytes using `inspect`;
they exclude state/envelope/receipt JSON I/O, filesystem metadata, physical I/O,
CPU, tokens and actual billing. Export preparation, storage, review, failed
attempts and any separate source acquisition must be counted by the evaluation.
Focused tests establish adapter mechanics. Useful transfer and a comparison
against sharing the same cached source bytes require independently evaluated
findings and isolated recipient outcomes; adapter tests do not close that gate.
