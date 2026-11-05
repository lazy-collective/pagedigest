# Documentation index

Agents: [AGENTS.md](../AGENTS.md) (symlinked as `CLAUDE.md`).

| Document | Audience | Purpose |
|----------|----------|---------|
| [Three visits](../README.md#try-three-visits) | New readers | Run a complete local read, unchanged revisit and changed-page fetch |
| [SPEC.md](../SPEC.md) | Implementers | Normative wire format and consumer algorithm |
| [CONTRACT.md](../CONTRACT.md) | Publishers & crawlers | Publisher claims, consumer responsibilities, and optional operational policies |
| [CONTENT_HYGIENE.md](../CONTENT_HYGIENE.md) | Publishers | Avoid false `rev`/`digest` churn; post-deploy reconcile |
| [ROADMAP.md](../ROADMAP.md) | Maintainers | Ready lanes, dependencies and acceptance for PD1–PD5 |
| [agent-execution.md](./agent-execution.md) | Coordinator & workers | File ownership, parallel preparation and integration joins |
| [validation.md](./validation.md) | Contributors | Focused checks, full gate, conservative PR routing and deployment |
| [RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md) | Maintainers | RC and 1.0 gates (v1.0 hard gates checked) |
| [ecosystem.md](./ecosystem.md) | Both | Shared roles, evidence and relationship with [DotRepo](https://dotrepo.org) |
| [DOGFOOD_TEMPLATE.md](./DOGFOOD_TEMPLATE.md) | Publishers | Template for deployment case studies |
| [case-studies/dotrepo.md](./case-studies/dotrepo.md) | Publishers & consumers | Dated dotrepo export estimates and live audit evidence |
| [benchmarks/README.md](./benchmarks/README.md) | Consumers & maintainers | Controlled equivalent-result comparison and independent-adoption acceptance criteria |
| [consumer-integration.md](./consumer-integration.md) | Consumers | Crawler, indexer, mirror, and agent integration guide |
| [recurring-consumer.md](./recurring-consumer.md) | Recurring users | Experimental source sync, rereading and source-bound findings workflow |
| [publisher-workflow.md](./publisher-workflow.md) | Publishers | Source-based preview/setup/update from final build output |
| [P1 bounded-freshness result](./benchmarks/digest-exchange-p1-20261029/README.md) | Evaluators | Negative savings result against HTTP freshness, preserved independently of new workflow controls |
| [cooperative-automation.md](./cooperative-automation.md) | Publishers & intermediaries | `PageDigest-State` logging, classification, nginx, and Cloudflare recipes |
| [announcements/v1-rc.md](./announcements/v1-rc.md) | Adopters & maintainers | Historical v1 RC announcement (protocol is v1.0) |
| [releases/consumer-safety.md](./releases/consumer-safety.md) | Adopters & maintainers | Safety release migration and published-artifact verification |
| [releases/consumer-safety-followup.md](./releases/consumer-safety-followup.md) | Adopters & maintainers | Replay-policy fixes, complete live synchronization, and refined benchmark evidence |
| [registrations/](./registrations/) | Maintainers | IANA registration drafts and filed request links |

Implementation guides: [rust-generator](../implementations/rust-generator/README.md), [python-consumer](../implementations/python-consumer/README.md).

Experimental integrations: [Scrapy consumer middleware](../integrations/scrapy/).

Conformance fixtures: [test-vectors/](../test-vectors/).

Current package/adapter guides: [Astro](../packages/astro/README.md),
[npm launcher](../packages/cli/README.md), [durable dogfood state](../site-state/README.md)
and [visual maintenance](visual-family.md).

Historical evidence is not the dispatch queue: the [roadmap snapshot](archive/roadmap-through-20261104.md),
[review guide](archive/REVIEW_GUIDE.md), [visual QA receipt](../design-qa.md),
announcements, releases, case studies and frozen benchmark reports keep their
original status and limitations. The [recurring control](benchmarks/recurring-workflow-20261104/README.md)
uses supplied finding text and does not establish independent utility. Do not
rewrite captured source or archived instructions to match today's implementation.
