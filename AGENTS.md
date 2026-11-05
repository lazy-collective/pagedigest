# Agent guide

For this site's production deployment, use the strict
[dogfood deployment policy](CONTENT_HYGIENE.md#dogfood-deployment-policy).
It preserves HTML bytes and verifies every digest across request profiles;
generic automatic reconciliation is not the dogfood deployment gate.

Quick orientation for AI agents working in this repo. **Do not duplicate normative prose here** — link to canonical docs ([docs/README.md](./docs/README.md)).

## What this is

`pagedigest` v1.0: a JSON manifest at `/.well-known/pagedigest.json` with monotonic `site_rev` / per-URL `rev` and optional `sha256` digests. One-line pitch: [README.md](./README.md).

| Question | Canonical doc |
|----------|----------------|
| Wire format & consumer algorithm | [SPEC.md](./SPEC.md) |
| Publisher/consumer obligations | [CONTRACT.md](./CONTRACT.md) |
| Digest churn & post-deploy reconcile | [CONTENT_HYGIENE.md](./CONTENT_HYGIENE.md) |
| Current priorities and outcome gates | [ROADMAP.md](./ROADMAP.md) |
| Release gates | [RELEASE_CHECKLIST.md](./RELEASE_CHECKLIST.md) |

Check the actual branch/HEAD and [README status](./README.md#status) before
choosing work. The recurring consumer and publisher helpers described in this
checkout are experimental source workflows, not commands in the published Python 0.2.0
package. Relative guides describe this branch; canonical folder names and old
release announcements do not establish current capabilities or priorities.

## Repo map

```
implementations/rust-generator/   # Publisher CLI (pagedigest-generator)
implementations/python-consumer/  # Consumer library (fetch, diff, audit, check_site)
packages/astro/                   # SSG integration (static HTML subset)
packages/cli/                     # npx launcher for release binaries
integrations/scrapy/              # Experimental Scrapy consumer (CI offline tests)
test-vectors/                     # Conformance fixtures; index in index.json
tools/                            # validate_vectors, smokes, reconcile, verify, hygiene
site/                             # Dogfood static site + emitted manifest
site-state/                       # Committed generator state for dogfood only
docs/                             # Ecosystem, templates, IANA drafts, archive
pagedigest.schema.json            # Validation aid; SPEC is normative boundary
```

## Work and validation

Use the [roadmap graph](ROADMAP.md) and [execution guide](docs/agent-execution.md)
for a coordinator with concurrent workers. Reserve shared contracts/integration,
assign disjoint files and unique environments/outputs, and accept outcomes only
at their declared joins. This checkout's [coordination skill](.agents/skills/roadmap-coordination/SKILL.md)
routes that workflow without adding another plan. Carry the parent's shared goal
and current task authorization when working across projects.

Use `uv` for Python. Workers run focused checks against their exposing cases;
the coordinator runs the appropriate integrated gate on the joined tree. Follow
[validation and CI](docs/validation.md) for the narrow prose-only path and full
checks. Full gate: `./tools/run_checks.sh` (uv, Rust/Cargo and Node required).
Do not turn a focused receipt into a claim that later or integrated changes passed.

## Implementation notes (easy to get wrong)

- **Revisions never decrease.** Rollback content still bumps `rev` / `site_rev` ([SPEC.md](./SPEC.md) §4.1).
- **URL keys** are byte-exact, pre-redirect, origin-relative (`/about` ≠ `/about/`).
- **Digests** are over identity-encoded **served** bytes. Generators hash files;
  generic publishers deliberately validate/reconcile supported representations.
  Dogfood preserves HTML bytes and uses the strict [deployment policy](CONTENT_HYGIENE.md#dogfood-deployment-policy), never automatic hash adoption.
- **Malformed manifests** → consumer fallback, not hard failure ([SPEC.md](./SPEC.md) §5.3).
- **Omitted URLs:** omission never proves unchanged. Under complete coverage,
  previously listed omitted URLs leave the covered set; under partial or absent
  coverage they are not described. Coverage removal does not prove HTTP deletion
  ([SPEC.md](./SPEC.md) §5.1).
- **Schema ≠ full conformance.** Apply SPEC text in addition to `pagedigest.schema.json`.

When changing protocol behavior: update **SPEC** if normative, add/adjust **test-vectors**, extend **python-consumer** validation/diff tests (`tests/test_vectors.py`).

## Delivery boundaries

The [version matrix](README.md#version-matrix) owns published versions; the
[status](README.md#status) distinguishes source workflows from released packages.
Do not document a planned install path as available without updating the README
and [release checklist](RELEASE_CHECKLIST.md). Tests and local demonstrations are
implementation evidence, not adoption, utility or economic savings.

Publisher digests: generate → deploy → validate supported representations →
deliberately reconcile when appropriate → verify. Dogfood uses
`tools/verify_deployed_site.py` and cold/warm controls; mismatches block completion.
Do not regenerate or publish dogfood state as a side effect of unrelated work.
Publication, outreach, paid activity and access changes require task-specific
scope; the roadmap grants no such authorization.

## Editing conventions

- **Stay focused.** Match existing style; no drive-by refactors.
- **Keep docs DRY.** README = front door; SPEC = normative; hygiene/ops = CONTENT_HYGIENE; gates = RELEASE_CHECKLIST; current graph = ROADMAP. Preserve dated archives and original evidence paths. Link instead of copy.
- **Avoid new top-level markdown** unless necessary; prefer `docs/` for supplementary material.
- **Generator binary:** `pagedigest-generator`; the npm launcher command is `pagedigest`.

## Task → where to work

| Task | Start here |
|------|------------|
| Generator behavior / URL keys | `implementations/rust-generator/src/main.rs` |
| Consumer fetch/diff/audit | `implementations/python-consumer/pagedigest/core.py` |
| Recurring sync and source-bound findings | [Recurring workflow](docs/recurring-consumer.md); `implementations/python-consumer/pagedigest/recurring.py` and `persistence.py` |
| Publisher setup and build-output updates | [Publisher workflow](docs/publisher-workflow.md); `tools/publisher_workflow.py` and the existing Astro hook |
| New manifest fixture | `test-vectors/` + `index.json` + `tools/validate_vectors.py` |
| Post-deploy digest tooling | `tools/reconcile_served_digests.py`, `tools/verify_over_wire_digests.py` |
| Dogfood site | `site/`, regenerate manifest via generator, `site-state/`; [visual family](docs/visual-family.md) |
| Producer case study | [docs/DOGFOOD_TEMPLATE.md](./docs/DOGFOOD_TEMPLATE.md) |

## License

MIT. Protocol spec is not a legal contract; [CONTRACT.md](./CONTRACT.md) is explanatory.
