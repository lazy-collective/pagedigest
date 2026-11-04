# PageDigest publisher generator

Publish resource revisions from final site output, with durable history and optional digests for audits. No separate page catalog is needed. Crate name: `pagedigest`. Installed binary: `pagedigest-generator`.

## Behavior

- Detects full-byte changes, including incidental build churn; digest omission does not change this behavior.
- Scans an input directory for allowlisted content files (`.html`, `.htm`, `.md` by default).
- Persists durable revision state (default: `<input_dir_parent>/.pagedigest/state.json`).
- Increments per-URL `rev` on content changes; `site_rev` on any add/remove/change; never decreases.
- Retains per-URL `rev` high-water marks in state `retired` when a URL leaves the
  scan set so a later re-add cannot emit a lower `rev` (SPEC §4.1.1).
- Maps `index.html` to `/` or `/section/` (`--index-style trailing-slash|file`).
- Emits coverage metadata (see [Coverage](#coverage)).
- Optionally emits stable per-entry `modified` timestamps (`--with-modified`).

## Coverage

The generator scans the input directory and emits one of:

- `--coverage complete` (default): `{"mode": "complete"}`. Use **only** when the
  input directory is the entire covered URL set for the origin — `complete`
  tells consumers that any URL they know which is absent from the manifest has
  left the covered set, not necessarily been deleted over HTTP. Pointing the
  generator at a subdirectory while keeping
  `complete` would overclaim coverage.
- `--coverage prefixes --prefix /blog/ [--prefix /docs/]`:
  `{"mode": "prefixes", "prefixes": [...]}`. Only entries whose URL key starts
  with one of the given prefixes are listed; URLs outside them receive default
  crawler behavior. Use this for partial manifests. Prefixes must begin with `/`
  and are normalized (sorted, de-duplicated) so re-runs do not churn `site_rev`.
- `--coverage none`: omits the field, so omission is ambiguous rather than a
  completeness claim.

Changing coverage semantics (mode or prefix list) increments `site_rev`, per
[SPEC.md §3.1](https://github.com/lazy-collective/pagedigest/blob/generator-v0.3.0/SPEC.md#31-top-level-fields).

## Digests

Optional (`--with-digest`). Hashes **on-disk** file bytes, not served HTTP
bytes. Emitting digests without a post-deploy check is the most common
publisher foot-gun.

**Default path when digests are enabled:**

1. Generate from final static output (`--with-digest`).
2. Deploy pages + manifest (atomic if possible; else pages first).
3. From a repository checkout root: `uv run --project implementations/python-consumer --locked python tools/reconcile_served_digests.py <manifest> --base-url https://… --apply`
4. Redeploy the manifest if digests changed; sample with `uv run --project implementations/python-consumer --locked pagedigest verify-live`.

If you cannot reconcile (or the host rewrites HTML unpredictably), omit
`--with-digest` and ship `rev` only. Details: [CONTENT_HYGIENE.md](https://github.com/lazy-collective/pagedigest/blob/main/CONTENT_HYGIENE.md).

## Modified timestamps

Optional (`--with-modified`). The generator records when it first observes each
content digest and persists that UTC timestamp in durable state. Unchanged
content keeps the same timestamp across rebuilds; changed content receives the
current generation timestamp. This deliberately avoids filesystem mtimes,
which often churn when otherwise identical build artifacts are copied.

## Revision state

Version 0.3.0 requires explicit first initialization (`--init`) and fails if durable state is missing on recurring builds. Recover with `--recover-floor N` only after establishing a bound on all historical revisions. Both operations refuse existing state. [Durable state, serialized CI, and recovery](https://github.com/lazy-collective/pagedigest/blob/main/CONTENT_HYGIENE.md#durable-publisher-state) are part of setup. These flags were introduced in v0.3.0; v0.2.0 does not support them.

## Run

From the repository root, after building your site into `./site-dist`:

```bash
# First publication only, for an origin with no previous revision history:
cargo run --locked --manifest-path implementations/rust-generator/Cargo.toml -- \
  ./site-dist --state ./publisher-state.json --init --with-digest

# Every later build uses the SAME durable state; missing state must fail:
cargo run --locked --manifest-path implementations/rust-generator/Cargo.toml -- \
  ./site-dist --state ./publisher-state.json --with-digest
```

Keep `publisher-state.json` outside build output, backed up and available to each
serialized build. Do not turn `--init` into a missing-state fallback. Digests
require the served-byte validation/reconciliation path above.

Or use the released crate with the same first-run/update distinction:

```bash
cargo install pagedigest --version 0.3.0 --locked
# First publication only:
pagedigest-generator ./site-dist --state ./publisher-state.json --init --with-digest
# Subsequent builds:
pagedigest-generator ./site-dist --state ./publisher-state.json --with-digest
```

The [publisher quickstart](https://github.com/lazy-collective/pagedigest/blob/main/README.md#publish-a-manifest) owns the complete
installation/deployment path; the commands above select source versus released
generator execution, not separate state histories.

Flags: `--index-style`, `--include-ext`, `--output`, `--state`,
`--with-digest`, `--with-modified`, `--coverage complete|prefixes|none`,
`--prefix` (repeatable; requires `--coverage prefixes`).

Before adopting served hashes, confirm the intended content is live and its bytes
are stable across supported request representations. Repeated reads from one
client do not establish this. Preserve byte-stable responses or explicitly review
representation differences; never strip scripts or normalize bodies during audits.
