# Ecosystem and shared direction

**Publish what you know. Reuse what still holds. Investigate what changed.**

PageDigest and [DotRepo](https://dotrepo.org) share the
[Lazy Collective](https://lazycollective.org/) goal:
reduce repeated fetching, parsing, investigation and verification for publishers
and consumers together, while preserving useful results and explicit uncertainty.
Lazy Collective is the umbrella and coordination project. Its public home
explains the shared purpose and current projects; there is no released shared
service or runtime. Four roles live in two repositories:

- **DotRepo** is the existing repository protocol, tools and public lookup index.
  Declarations can be derived from manifests, CI and documentation; observed
  overlays retain their separate provenance and authority.
- **RepoDigest** is DotRepo's experimental discovery, requirement-assessment and
  reuse workflow. A lead, a source-supported preliminary choice and successful
  runtime execution establish different things.
- **PageDigest** is the existing website manifest protocol and publisher/consumer
  toolchain. Its recurring source workflow adds reports and retained findings.
- **DotPage** names the publisher role in existing site/build workflows, not a
  separately shipped product. It does not rename the v1 protocol or packages.

Declarations can avoid repeated work when needed local results remain complete,
available and fresh enough for the task. Missing bodies, failed processing,
representation changes, audits and uncertain facts still need work. Authenticity,
correctness and freshness answer different questions. Publishers should derive
metadata from existing sources and clarify genuine ambiguity; consumers should
benefit from ordinary HTTP/source caches even without publisher participation.

## Existing integration and evidence

DotRepo's public exporter already emits `/.well-known/pagedigest.json` alongside
its snapshot and per-file manifests. The [July 3 case study](case-studies/dotrepo.md)
records that implementation and estimates a cycle against naive full covered-file
fetching. It is operator dogfood and a dated export estimate, not independently
measured consumer savings, adoption or proof of current deployment freshness.

The [controlled comparisons](benchmarks/README.md) require equivalent results
before counting costs. The [bounded-freshness P1 study](benchmarks/digest-exchange-p1-20261029/README.md)
found PageDigest used 38.6% more response bytes than ordinary HTTP freshness
caching on its workload. That negative result remains intact. Neither batching
nor fewer modeled requests establishes lower total work or model-token cost.

This checkout includes the experimental source introduced in
[PR2](https://github.com/maxwellsantoro/pagedigest/pull/2): an unreleased [recurring consumer workflow](recurring-consumer.md), which
reports changes, required rereading and source-bound findings using HTTP,
sitemap and PageDigest signals as available. The [publisher workflow](publisher-workflow.md)
uses existing builds, generator state and Astro integration. Local controls
establish implementation behavior, not combined savings or independent adoption.

The [roadmap](../ROADMAP.md) owns the next bounded outcomes. Compare useful
completed results at equal quality/freshness, including publisher maintenance,
consumer reads/parsing, verification, fallback and unfinished attempts. Link
owning evidence instead of maintaining another catalog or shared runtime.
DotRepo's [workflow status](https://github.com/maxwellsantoro/dotrepo/blob/main/docs/workflow-status.md)
owns repository-side delivery and its negative or incomplete consumer studies.

## Design note: third-party observed-revision manifests

This is a possible future direction, not part of version 1. The v1 wire format
and publisher/consumer contract are unaffected.

Version 1 manifests come from the publisher origin. Consumers can still use
ordinary HTTP caching without them. DotRepo supports autonomous overlays with
explicit non-authority and provenance before maintainer participation; that is an
implemented bootstrap mechanism, not proof that adoption economics are solved.

The analogous unilateral bootstrap for pagedigest is a **third-party
observed-revision manifest**: a party that already crawls a site (a search
indexer, an archive, a CDN, a mirror network) publishes, under its own origin,
a manifest of the revisions and digests *it observed* for that site's URLs.
Other consumers could then use the observer's manifest for change detection
against sites that have not adopted pagedigest.

Key properties any future design would need to preserve:

- **Clear non-authority.** An observed manifest describes what an observer saw
  and when, never what the publisher declares. It must be impossible to
  confuse the two; the publisher's own `/.well-known/pagedigest.json` always
  supersedes any observation.
- **Honest staleness.** Observed revisions are only as fresh as the observer's
  last crawl; the manifest must carry that observation time so consumers can
  reason about it.
- **No enforcement rights.** Neither publisher nor observer manifests create
  protocol-defined enforcement rights. Rate limits remain origin policy, and
  repeated requests can reflect legitimate cache loss, audits, or separate users.
- **Provenance survives handoff.** When a publisher later adopts pagedigest
  natively, consumers switch to the authoritative manifest without ambiguity.

This is a hypothesis for later evaluation, not an implemented v1 extension or a
reason to start a shared service now. Any native authority upgrade still leaves
correctness, freshness, combined cost and adoption to be established separately.
