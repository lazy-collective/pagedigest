# Content Hygiene Guide

This guide helps publishers avoid false churn in `rev` and `digest` values.

The local [publisher workflow](docs/publisher-workflow.md) combines first setup,
build-output change review and explicit generation without a hand-maintained page
catalog. The existing [Astro hook](packages/astro/README.md) remains the direct
integration for Astro sites.

Repository tooling below runs from a source checkout root through the locked
consumer environment: `uv sync --project implementations/python-consumer --locked`.
Installed consumer usage is described separately in the
[publisher quickstart](README.md#publish-a-manifest).

## Default pipeline (when digests are enabled)

Generators hash **build output**. Audits hash **served** identity-encoded
bytes. Treat the following as the default publisher path whenever
`--with-digest` / `withDigest: true` is on:

1. Build final static (or deterministic) output.
2. Optional: `uv run --project implementations/python-consumer --locked python tools/check_content_hygiene.py ./site-dist`.
3. Generate the manifest (`pagedigest-generator`, `npx pagedigest`, or
   `@pagedigest/astro`).
4. Deploy pages + manifest (atomic if possible; else pages first, then
   manifest).
5. Confirm the intended content is live and representations are stable for supported
   clients. **Reconcile deliberately:** `uv run --project implementations/python-consumer --locked python tools/reconcile_served_digests.py <manifest>
   --base-url https://example.com --apply`, then redeploy the manifest if it
   changed.
6. **Verify:** `uv run --project implementations/python-consumer --locked pagedigest verify-live https://example.com --sample-size 25`.

Skipping step 5 is the usual cause of honest publishers failing their own
audits (CDN minification, email obfuscation, script injectors). If you cannot
reconcile, omit digests and rely on `rev` only.

## Why this matters

If non-content bytes change on every build or request, `pagedigest` becomes noisy:

- Consumers re-fetch unchanged pages.
- Audit mismatch rates increase.
- Trust in the manifest decreases.

## Common churn sources

- Build timestamps in rendered pages.
- Randomized cache-busting query strings injected at build time.
- Session IDs / CSRF tokens embedded into static output.
- Analytics snippets that change per build.
- Dynamic aggregates in static templates (view counts, comment counts).
- CDN and edge features that rewrite HTML after deploy (see below).

## Case study: CDN feature injection

Observed on pagedigest.org's own first production day (2026-07-02):
Cloudflare's **Email Address Obfuscation** rewrote a `mailto:` link into a
`/cdn-cgi/l/email-protection` URL and injected a decode script before
`</body>`, so the served bytes for `/` no longer matched the manifest's
`digest` — an honest publisher failing its own audit because of host
middleware. Pages without an email address on the same host audited clean.

Any edge feature that mutates HTML bytes has the same effect. Known
offenders include email obfuscation, auto-minification, script injectors
(RUM/analytics beacons, Rocket Loader-style optimizers), and bot-management
snippets.

Publishers do not need to disable these features. Run
`tools/reconcile_served_digests.py --apply` only after confirming that the intended
content is deployed and its identity representation is stable for the supported
request profiles. It samples each digest-bearing URL twice under one request
profile; two matching observations do not establish uniform bytes for every client —

- **stable transforms** (deterministic rewrites such as minification): the
  digest can be adopted for that observed representation; other representations
  still need explicit validation;
- **unstable transforms** (per-response rewrites such as randomized email
  obfuscation — the pagedigest.org case above): the digest is removed for
  that URL, which the spec defines as the honest state.

`rev` integers remain valid either way — this failure mode only poisons
`digest` audits, but a poisoned audit reads as publisher dishonesty to
consumers, which is worse than omitting the digest. Without `--apply` the
tool is read-only and exits non-zero on findings, so it can gate a deploy.

An injector can vary by request headers even when repeated reads from one client
are stable. In that case, adopting one variant's hash makes the other variant
wrong. The [dogfood deployment policy](#dogfood-deployment-policy) preserves exact
HTML bytes and checks multiple request profiles instead of automatically adopting
transformed hashes. This does not change the protocol's digest semantics.

## Practical pipeline pattern

Copy-paste default path (also on the [README](./README.md#publish-a-manifest)):

1. Render site to final deployable artifacts.
2. Optional: `uv run --project implementations/python-consumer --locked python tools/check_content_hygiene.py ./site-dist --fail-on warning`.
3. Generate `pagedigest` from rendered output (`--with-digest` when you want audits).
4. Deploy pages and manifest atomically (or pages first, then manifest).
5. Reconcile against served bytes
   (`tools/reconcile_served_digests.py <manifest> --base-url <origin> --apply`)
   and redeploy the manifest if it changed — this absorbs CDN/edge rewrites
   without disabling any host feature.
6. Sample live audits: `uv run --project implementations/python-consumer --locked pagedigest verify-live <origin>`.

### Digest-only reconcile and `site_rev`

By default, `--apply` updates digests (or drops unstable digests) and refreshes
`generated` **without** incrementing `site_rev`. That matches the SPEC: content
did not change, only the audit surface.

Consumers that short-circuit on equal `site_rev` will not re-read the entry map
until the next content-driven bump, so their cached digests may lag until then.
If your consumer pipeline only refreshes digests when `site_rev` moves, pass
`--bump-site-rev --state <publisher-state.json>` with `--apply`, or re-audit
digests out of band (`uv run --project implementations/python-consumer --locked pagedigest verify-live`). The state must be the durable
Rust or Astro state used to generate that manifest. Reconciliation verifies
matching revisions and reserves the new `site_rev` in state before replacing
the manifest, so subsequent builds retain the high-water mark. Run generation
and reconciliation serially. If a write fails after state advances, regenerate
before retrying reconciliation.

The dogfood CI guard compares build hashes against committed generator state
and checks manifest revisions and coverage. Served digests may differ or be
omitted after reconciliation; use live verification to check those claims.

## Digest reliability note

The current minimal Rust generator hashes source file bytes from the selected input directory.

Use it against final rendered output whenever possible. If CDN/edge layers transform HTML bytes (for example minification or script injection), digest audits may fail even when publisher intent is honest.

Generators retain per-URL `rev` high-water marks when a URL leaves the covered
set (delete or coverage filter), so republishing the same key later does not
reset `rev` to `1` and force consumer anomaly fallback (SPEC §4.1.1).

## Quick checklist before publishing

- [ ] Input directory is final rendered output (not source templates).
- [ ] Output excludes non-content artifacts (maps/temp files).
- [ ] Global template timestamp/churn is removed or stabilized.
- [ ] Manifest and pages are deployed in a consistent order.
- [ ] Initial audit sample confirms low mismatch/inconclusive rates.

Run the local checker against final rendered output before generating the
manifest:

```bash
uv run --project implementations/python-consumer --locked python tools/check_content_hygiene.py ./site-dist
```

By default, warnings are informational and only hard errors fail the command.
Use `--fail-on warning` to make likely churn hazards a deployment gate.
Repository dogfood (`site/`) is gated at `--fail-on warning` in
`./tools/run_checks.sh`. Protocol manifests at `.well-known/pagedigest.json`
are not flagged for their required `generated` timestamp.

## If you cannot make bytes stable

For URLs with unavoidable non-content churn:

- omit `digest` for those URLs,
- keep `rev` monotonic and content-driven,
- document the limitation in publisher notes.

## Dogfood verification helper

Use `uv run --project implementations/python-consumer --locked pagedigest verify-live` against a live deployment to sample digest-bearing entries and compare manifest hashes to identity-encoded responses over the wire.

Example:

```bash
uv run --project implementations/python-consumer --locked pagedigest verify-live https://example.com --sample-size 25
```

The legacy `tools/verify_over_wire_digests.py` script remains as a compatibility
wrapper for existing repository automation.

### Dogfood deployment policy

The source deployment for pagedigest.org sets `Cache-Control: no-transform` on
HTML responses in its Pages Worker, preserving full build bytes for digest
verification. This is a response policy, not a protocol requirement. According
to [Cloudflare's analytics documentation](https://developers.cloudflare.com/web-analytics/get-started/),
it prevents automatic analytics-beacon injection; it can also affect automatic
compression. Deploying this policy therefore stops automatic Web Analytics on
those HTML responses. The separate cooperation observation endpoint is unchanged.

The deployment gate `tools/verify_deployed_site.py` requires the exact intended
manifest and every covered identity body, with a digest for each entry, on two
complete passes for each of three request profiles: ordinary consumer, absent
`Accept`, and browser-style HTML. It also requires the HTML response policy.
In the November 2 tested matrix, analytics injection appeared when `Accept`
was absent, while `*/*` requests matched; adopting the injected variant's hashes
would break those ordinary consumer audits.
The gate rejects stale pages paired with a new manifest, redirects,
missing digests and inconclusive fetches. Bounded retries allow edge propagation;
they never rewrite hashes, normalize bytes or accept a smaller audit sample.
The existing cold/warm persistent-consumer checks then verify completed reuse.
Only current main can deploy; a queued older SHA must not roll revisions back.

This strict gate is specific to the fully digested dogfood collection. Other
publishers may use the protocol's optional digests and deliberate reconciliation.
Reconciliation now fails before writes if any observation is inconclusive and
checks both responses even when the first digest matches. Before adopting a
stable transformed digest, establish that the intended page content reached the
edge: a matching manifest alone does not prove that. Do not reconcile a new
build against an older live deployment.

## Durable publisher state

The following initialization and recovery interfaces require **generator 0.3.0
or Astro 0.2.0**. Existing durable
state remains readable; normal builds do not need an initialization flag.

The Rust generator refuses missing state unless explicitly invoked with `--init`
(first publication only) or `--recover-floor N`. Astro exposes `initialize: true`
and `recoverFloor: N` for the corresponding one-time operation. Both refuse to
replace existing state, and initialization refuses an existing output manifest.
Remove the initialization option before recurring builds. It is not a CI fallback.

Persist the state outside ephemeral workspaces and evictable CI caches, back it
up, and serialize the entire publication pipeline. Generator state includes
retired URL high-water marks; saving only the current public manifest loses those
marks. Each generator takes a `<state>.lock` during local generation. This guards
one filesystem, not concurrent deployments from independent machines. After a
crash, inspect the state/output and confirm there is no writer before removing a
stale lock. Use a CI concurrency group or an external publication lock through
state persistence, deployment, and reconciliation.

### CI recipe with a durable state branch

Create a dedicated `pagedigest-state` branch containing initialized `state.json`
once, outside recurring CI. This is durable publication history, not a cache.
Do not reset or force-push it. Restrict writers and back it up. The branch can be
private if state paths or retired URLs should not be public.

This workflow template uses the current source generator. Replace the two
marked site-specific commands with your build and deploy commands. The state
branch must already exist; checkout failure must fail the job.

```yaml
name: Publish with durable PageDigest state
on: workflow_dispatch
permissions:
  contents: write
concurrency:
  group: pagedigest-production
  cancel-in-progress: false
jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: actions/checkout@v7
        with:
          ref: pagedigest-state
          path: publisher-state
      - uses: dtolnay/rust-toolchain@stable
      - run: ./build-site.sh # replace with your build command producing site-dist/
      - run: >-
          cargo run --locked --manifest-path implementations/rust-generator/Cargo.toml --
          ./site-dist --state ./publisher-state/state.json --with-digest
      - name: Persist reserved revisions before deployment
        working-directory: publisher-state
        run: |
          git config user.name "PageDigest publisher"
          git config user.email "publisher@example.com"
          git add state.json
          if ! git diff --cached --quiet; then
            git commit -m "Reserve publication revisions"
            git push origin HEAD:pagedigest-state
          fi
      - run: ./deploy-site.sh # replace with your atomic deploy and digest reconciliation
```

If a job fails after state is reserved, the next build continues from the higher
state. It must not restore an older state file to make revision numbers smaller.
If reconciliation uses `--bump-site-rev --state`, persist its updated state before
publishing the corrected manifest, under the same publication lock.

### Recovery after state loss

Prefer restoring the latest complete durable state, including retired entries.
If only older backups remain, establish an upper bound **N on every site and
per-URL revision ever published, including retired URLs**, using trustworthy
publication records. Then run once with missing state:

```bash
pagedigest-generator ./site-dist --state /durable/example/state.json \
  --recover-floor 100000 --with-digest
```

Here `100000` is illustrative; do not copy it without establishing your own bound.
The generator starts recovered entries and site state above N and persists a
floor for historical keys reintroduced later. Astro's `recoverFloor` uses the
same rule and requires safe JavaScript integers. Without a trustworthy bound,
do not invent a recovery number or silently initialize: restore history or
coordinate a cache reset with consumers before resuming publication.

No local tool can distinguish a genuine first publication from total loss of all
publication evidence. Explicit initialization is an operator assertion, not an
automatic proof. Full-byte hashing is conservative change detection; disabling
emitted digests does not eliminate byte-induced revision churn.
