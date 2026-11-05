# Roadmap snapshot — November 4, 2026

This historical snapshot is from `e41285ad3b4bc141fbf1abbecbbb1bc7907dc1bc`.
Only relative links were adjusted for relocation. Dated status and former
priorities below describe that snapshot; use the [current roadmap](../../ROADMAP.md)
for dispatch. Evidence stays at its original paths.

# Roadmap

**Now:** v1.0 — stable wire format, shipped reference implementations and packages, dogfood on [pagedigest.org](https://pagedigest.org). Gates: [RELEASE_CHECKLIST.md](../../RELEASE_CHECKLIST.md).

## Active outcome priorities — November 4, 2026

The next product outcome is a returning reader completing useful work, retaining
its source dependencies and revisiting the right material after a change. The
stable protocol and generators already exist; the experimental `sync`/`remember`
workflow supplies most of the next path. The ordered packets here own new work.
The dated notes and Phase 1–6 tables below preserve delivery history.

| Order | Packet and concrete deliverable | Acceptance and decision |
| --- | --- | --- |
| 1 | **PD1 — A reproducible recurring-reader entrypoint.** Extend the three-visit demonstration into a maintained source-install path for `sync` and `remember`, with an inspectable saved finding and restart/recovery instructions. Build a versioned local wheel candidate from the existing implementation. | A fresh environment reads a small site, saves a real answer with its declared sources, exits, then returns and reports what needs rereading. Exercise old-cache migration and missing-body recovery. A package release is a later explicit delivery step; Python 0.2.0 still lacks these commands. |
| 2 | **PD2 — Useful work over six cycles.** Freeze three recurring questions against a small mostly static corpus before running them. Include initial read, unchanged revisit, relevant change, irrelevant change, cache loss and failed-deployment recovery. | Evaluate the resulting answers and omissions as well as source-status labels. Compare the same HTTP cache and discovery opportunities, with equal freshness and audit policy. Count all attempts, local integrity reads, parsing, requests/bytes and unfinished work. The reader must revisit affected evidence and preserve unrelated usable work. Fix the largest observed gap before expanding the workload. |
| 3 | **PD3 — A durable publisher path people can maintain.** Use two representative existing builds, including one Astro site, through initial setup and two updates. Exercise state restoration and served-byte verification without a hand-maintained page catalog. | Record operator time, interventions, unexpected revision churn and recovery steps. Ordinary builds derive their inventories automatically; lost state never silently restarts history. PD3 can run once PD1's path is stable. Use its costs in PD2/PD5 instead of treating publication as free. |
| 4 | **PD4 — A finding handed to a second reader.** After PD2 yields a useful retained answer, prototype an explicit export/import between two isolated stores, coordinated with DotRepo D4. Carry claim text, scope, source references/hashes, assumptions and original observation time. | The recipient applies its own checks and can distinguish unchanged sources from a correct conclusion. Include relevant change, missing source and conflicting interpretation. Compare against sharing the same cached source alone. Start with files; a shared network service and v1.1 changes require a demonstrated unmet need. |
| 5 | **PD5 — A bounded independent recurring use case.** After PD1–PD3, prepare a pinned candidate and operating guide for one independent publisher/consumer pair. PD4 is required only if findings cross readers. | Freeze useful outputs, freshness, a finite run count and spending ceiling first. Compare total publisher + intermediary + consumer work against competent HTTP/sitemap/fingerprint alternatives, including setup, audits, fallback and maintenance. Report favorable and unfavorable workload regions separately. Seek permission for outreach, paid activity or package release; these roadmap items do not authorize them. |

**Next implementable packet: PD1.** Today's local three-visit example demonstrates
real cache behavior, with audits disabled for reproducibility. It is not yet a
complete recurring research task or independent evidence. PD2 must use actual
questions and evaluated answers rather than supplied finding text alone.

**Go/no-go rule:** completion, freshness and correct invalidation come first;
economic benefit is then measured with publisher work included. The retained
38.6% byte overhead and six-cycle 14-request/1,199-byte result remain negative
evidence. If a matched workload still loses, simplify the integration, narrow
its intended use or prefer ordinary HTTP caching. Do not manufacture a positive
result by dropping audits, missing results or failed attempts.

**Deferred:** more SSG plugins, broad crawler distribution, manifest sharding,
new hash/discovery mechanisms, observation-counter polish and a shared-memory
backend. Reopen an item when a named workflow encounters its specific limit.
Protocol stability and the existing deployment/recovery checks remain obligations.

## Delivery history and retained evidence

**November 4 org-review repair (local candidate):** sitemap discovery now applies
the requested prefixes before its 200-source admission limit, while validating
all input URL keys and retaining separate 2 MiB / 10,000-entry input bounds.
Regression controls cover large narrowed sitemaps, persisted scope, explicit URLs,
overfull selected scope and unsafe excluded entries. Full-gate results and the
bounded recurring-workflow control are retained in the parent review packet at
`/Users/maxwell/Documents/Codex/2026-11-04/task/address-org-review/acceptance/`.
This is source preparation, with no package or website publication.

The [completed-workflow control](../../docs/benchmarks/recurring-workflow-20261104/README.md)
compares the real publisher/recurring workflow with the same HTTP cache through
six bounded local cycles. Both retain useful source bindings and handle loss,
change, failure and recovery; PageDigest uses 14 requests / 1,199 consumed body
bytes versus HTTP's 12 / 365. This developer-defined, post-exposure control uses
supplied finding texts; independent utility, operator effort and all-in economic
benefit remain open. Preserve P1's negative result and DotRepo's export-time churn
receipt; no shared runtime, scaling campaign or provider spend follows.

**November 3 review follow-up:** keep the current Pages hosting and use
descriptive application user agents, per the user's explicit choice after the
managed-zone BIC limitation was verified. Default source consumer sessions now
identify PageDigest; custom sessions retain their own identity. This is source
delivery, not a new package release. The recurring guide records the urllib
example and the remaining Pages platform constraint. Shared acceptance evidence
is retained in the parent November 3 `task/not-done` packet.


**Source milestone (implemented November 2, not yet packaged):** a recurring consumer reports
what changed, what needs rereading and which findings retain their source
bindings. A publisher helper derives the manifest from final build output,
previews changes and preserves durable state/coverage. These workflows reuse
the current protocol and generator rather than adding a separate publisher service.
See [recurring consumption](../../docs/recurring-consumer.md) and
[publisher setup/update](../../docs/publisher-workflow.md).

**Next outcome:** demonstrate that independently operated recurring work finishes
correctly with useful findings at a stated freshness target, and measure the
publisher's setup/update effort. Compare total work against competent HTTP caching
and sitemap discovery, including acquisition, audits, missing bodies, failures and
maintenance. Local tests are implementation evidence, not adoption or savings.

The local [P1 bounded-freshness experiment](../../docs/benchmarks/digest-exchange-p1-20261029/README.md)
failed its savings gate: PageDigest used 38.6% more response bytes than HTTP
freshness caching. Preserve that result. Additional integrations, a shared
coordinator or v1.1 features need a new bounded workload demonstrating their value.

## Consumer safety milestone (released September 16, 2026)

- Implemented: explicit publisher initialization/recovery, incomplete-cache checks,
  real 304 audits, and Scrapy cached-response replay with a traversal regression.
- Implemented: clean wheel/npm-tarball installation checks and a controlled local
  comparison with conditional HTTP, accurate sitemap, and fingerprint baselines.
- Released: generator/launcher 0.3.0 and Python/Astro 0.2.0, with exact artifact
  checks and clean registry installation verification.
  [Migration and release evidence](../../docs/releases/consumer-safety.md).
- Remaining adoption evidence: an independent operator, deployment failure and
  recovery observations, and equivalent-result/freshness measurements. Local
  fixtures and sibling deployments do not satisfy this milestone.

Acceptance and measured fixture results: [benchmark notes](../../docs/benchmarks/README.md).

The [repository follow-up](../../docs/releases/consumer-safety-followup.md) adds
conservative Scrapy HTTP replay policy, complete live synchronization checks, and
matched-audit/persistent-consumer benchmark measurements. The adapter remains
experimental, and independent operation is still the next adoption gate.

The historical protocol sequence below records completed implementation and
reserved extensions. Use the active outcome priorities above to choose new work.

## Phase 1 — Public RC

| Task | Status |
|------|--------|
| Pre-public docs/tests polish | done |
| Tag `v1.0.0-rc.1` | done — released 2026-07-02 |
| Adopter feedback channel (Issues/Discussions) | done — [v1 RC feedback issue](https://github.com/lazy-collective/pagedigest/issues/1) |
| RC announcement | done — [docs/announcements/v1-rc.md](../../docs/announcements/v1-rc.md) published on site at [/announcements/v1-rc/](https://pagedigest.org/announcements/v1-rc/) |
| Prior-art comparison on README/site/spec | done |
| Reserve optional `PageDigest-State` + vectors | done |
| Audit-economics failure-scope guidance | done |
| pagedigest.org `PageDigest-State` observer | done — Worker shipped; `PAGEDIGEST_OBSERVATIONS` KV bound and live counts confirmed 2026-07-04 |

## Phase 2 — Distribution

| Task | Priority / status |
|------|-------------------|
| GitHub Releases (`pagedigest-generator` binaries) | done — `v0.3.0` published for Linux, macOS, and Windows |
| PyPI (`pagedigest` consumer) | done — `0.2.0` published with Trusted Publishing |
| `cargo install` | done — `pagedigest 0.3.0` published to crates.io |
| npm wrapper (`npx pagedigest`) | done — `pagedigest 0.3.0` published with verified binary downloads and Trusted Publishing |

Update README install blocks as each ships. Semver for implementations; spec `version` stays `1`.
Canonical matrix: [README.md § Version matrix](../../README.md#version-matrix).

## Phase 3 — Publisher path

| Task | Priority |
|------|----------|
| Astro plugin (`@pagedigest/astro`) | done — `0.2.0` published to npm; OIDC releases configured |
| Astro `withModified` + pipeline/docs parity | done — matches generator observation timestamps; HTML subset documented |
| Producer case study ([dotrepo](../../docs/case-studies/dotrepo.md), [template](../../docs/DOGFOOD_TEMPLATE.md)) | done — first measured case study |
| Hygiene checker utility | done — `tools/check_content_hygiene.py` |
| Generator: per-entry `modified` fields | done — stable observed-content timestamps via `--with-modified` |
| Hugo / Eleventy / Jekyll plugins | deferred — Post-1.0; copy Astro retired-rev + URL-key encoding + conformance smoke pattern |

Publisher pipeline: build → generate manifest → deploy → `reconcile_served_digests.py --apply` → verify. Details: [CONTENT_HYGIENE.md](../../CONTENT_HYGIENE.md). Generators remind on `--with-digest` / default Astro digests.

## Phase 4 — Consumer path

| Task | Priority |
|------|----------|
| Consumer integration write-up | done |
| Reference sample (cache persistence) | done — atomic state and bounded body cache with failure tests |
| Live digest verification CLI (`pagedigest verify-live`) | done |
| Scrapy consumer middleware | done (experimental in-tree) — [integrations/scrapy](../../integrations/scrapy/); uses reference `pagedigest` validate/header; offline tests gated in CI; PyPI publish deferred to Post-1.0 |

## Phase 5 — Standards registration

| Task | Status |
|------|--------|
| Well-known URI suffix registration | done — filed ([issue #98](https://github.com/protocol-registries/well-known-uris/issues/98)); docs reflect extension-URI discovery |
| Link relation registration | done — filed ([issue #73](https://github.com/protocol-registries/link-relations/issues/73)); v1.0 ships with `rel="https://pagedigest.org/rel"` |
| Short-form IANA `rel` token | deferred — update examples when assigned (not a v1.0 blocker; see [RELEASE_CHECKLIST.md](../../RELEASE_CHECKLIST.md)) |

Drafts remain in [docs/registrations/](../../docs/registrations/).

## Phase 6 — v1.0

| Task | Status |
|------|--------|
| All hard [1.0 Gate](../../RELEASE_CHECKLIST.md#10-gate) items | done |
| README / ROADMAP / SPEC primary status → v1.0 | done |
| Tag `v1.0.0` | done — local annotated tag on the status-ship commit (implementation package semver stays 0.x until a separate package release) |

Short-form IANA `rel` remains optional follow-up, not a v1.0 blocker.

## Post-1.0 (reserved)

Any v1.1 extension must first justify `PageDigest-State` intermediary semantics
using measured consumers. Manifest sharding, content extracts, DNS
discovery, and additional hash algorithms remain reserved; see [SPEC.md](../../SPEC.md) §6.

| Item | Disposition |
|------|-------------|
| Hugo / Eleventy / Jekyll plugins | Deferred until an active publisher workflow needs one; reuse Astro conformance pattern |
| Scrapy middleware on PyPI | Graduate from experimental when a maintainer is ready |
| Short-form IANA `rel` examples | Flip docs when the token is assigned |
| mypy/pyright in CI | Optional polish; consumer is annotated and unit-tested |
| Atomic Worker observation counters | KV get-then-put is best-effort metrics only (`site/_worker.js`) |
| Pure-JS Windows unzip | System `tar.exe` is standard on modern Windows (`packages/cli`) |

## Contribute

Open an issue referencing an active packet. Start with **PD1's reproducible
recurring-reader path**, then **PD2's evaluated repeat work** and **PD3's publisher
upkeep**. Independent operation follows a usable candidate.
