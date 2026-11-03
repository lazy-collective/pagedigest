# Publisher setup and recurring build review

Use final site output as the inventory. There is no second page list to maintain.
The `tools/publisher_workflow.py` helper wraps the existing Rust generator
and stages a change report before any write. This is experimental source tooling,
not a new PageDigest format or a live-site update.

Build the first-party generator and review a first publication:

```bash
cargo build --locked --manifest-path implementations/rust-generator/Cargo.toml
uv run --project implementations/python-consumer --locked python tools/publisher_workflow.py \
  /path/to/site-dist --state /durable/example/state.json \
  --initialize --coverage complete
```

The only initial declarations are facts the build cannot establish: that this
is the first publication and which URL set is covered. Choose `complete` only
when the output covers the entire declared origin set. For a partial collection,
use `--coverage prefixes --prefix /docs/`; choose `none` when no coverage claim
can be established and omitted URLs must remain undescribed. Complete-coverage
omission means removal from the covered set, not proof of HTTP deletion.
With omitted choices, the helper reports the exact
clarifications and writes nothing. Durable state must live outside disposable
build output.

Review `added`, `changed`, `removed`, `unchanged`, coverage, and the proposed site
revision. Add `--apply` to generate the manifest and persist revision state.
Only the first invocation includes `--initialize`. Recurring builds use:

```bash
uv run --project implementations/python-consumer --locked python tools/publisher_workflow.py \
  /path/to/site-dist --state /durable/example/state.json --apply
```

Coverage and prefixes are read from existing durable state. No-change previews
ignore the diagnostic generation timestamp. An ordinary preview does not change
the build or state; `--check` exits 1 when generation or clarification is needed.
Missing state with an existing manifest blocks initialization and points to
[recovery](../CONTENT_HYGIENE.md#durable-publisher-state). Removed URL high-water
marks and generation locking remain owned by the existing generator.

Digest emission is optional. Use `--with-digest` explicitly in recurring CI when
audits are wanted; absent that flag, the helper preserves digest emission when
it can observe it in the existing manifest, otherwise defaults to revision-only.
This matters when each build starts with a clean output directory. After a
digest-bearing deployment, use the existing
[served-byte reconciliation and verification](../CONTENT_HYGIENE.md#default-pipeline-when-digests-are-enabled).
On-disk hashes do not establish live response bytes.

Serialize build, generation, durable-state backup and deployment. The helper
rechecks current input when applying, and the generator writes state before the
manifest so a failed output write cannot reset historical revisions. An applied
report describes the actual generated output, not the earlier preview. It does
not deploy anything.

Astro publishers can keep the existing
[`@pagedigest/astro` build hook](../packages/astro/README.md): it already discovers
static HTML after the build. Keep the durable state and one-time initialization
settings there instead of running a second generator over its output. The helper
is for the Rust generator workflow; it does not consume Astro's differently
shaped state. Both paths share the same v1 consumer contract and reconciliation
requirements.

The local fixture controls exercise setup, no-change builds, content updates,
removal/re-addition, inherited partial coverage, lost-state refusal and explicit
digest policy against the actual Rust generator. These controls establish workflow
behavior, not independent publisher adoption, operator time saved, or bandwidth
savings. The negative
[P1 comparison](benchmarks/digest-exchange-p1-20261029/README.md) remains unchanged.
