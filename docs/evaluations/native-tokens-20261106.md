# Native agent-token comparison — November 6, 2026

**Decision: prefer ordinary HTTP plus cached sources and ordinary notes for this
measured workload.** The selected brief view is accepted engineering, but the
paired observation fails the predeclared savings rule. Lower uncached usage alone
does not establish less total agent work.

The experimental source candidate is `294349f652af2e448f8b6a49cd1ab12e4d6d7b07`.
`pagedigest inspect STATE --id FINDING --brief` projects one finding only after
the existing complete integrity and freshness checks. It preserves original dates,
selected/global failures, cycle completeness and semantic uncertainty. Full
inspection remains available; this is not a package release.

## Matched task and quality

Fresh native Codex sessions used the recorded GPT-6.1 Sol / High configuration.
Both arms received identical captured sources, equivalent source validation and
their own independently authored initial note. The baseline could reuse its note
efficiently; it was not forced to fetch or reread entire pages.

The task compared the project page and historical trace: replacement downloads
versus audits/requests, experimental versus shipped behavior, owner use versus
independent adoption, and supported recommendations/limits. Both arms passed all
five initial/return cases in independent cost-blind grading: initial, unchanged,
synthetic relevant change, unrelated change and missing/stale.

This is a **historical loopback HTTP-validation replay of captured first-party
served bytes**, from `http://127.0.0.1:61273`; it is not fresh public-site validation
or another real maintenance occasion. Replay uses the exact original validation
time, unchanged 3,600-second age bound, full-audit policy and HTTP freshness
metadata. The stale case is 3,601 seconds later. No recall renews observation dates
or substitutes matching bytes for interpretation review.

## Actual native usage

These are native `turn.completed.usage` counters, not estimates from bytes.
Cached input is part of input. **U = input − cached input + output**;
**total = input + output**. Reasoning output is already included in output.

| Phase / arm | Input | Cached input | Output | U | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Initial baseline | 145,917 | 118,272 | 2,033 | 29,678 | 147,950 |
| Initial product | 145,860 | 118,144 | 2,080 | 29,796 | 147,940 |
| Return baseline | 84,920 | 52,736 | 4,558 | 36,742 | 89,478 |
| Return product | 127,227 | 110,592 | 4,898 | 21,533 | 132,125 |
| **Initial + return baseline** | **230,837** | **171,008** | **6,591** | **66,420** | **237,428** |
| **Initial + return product** | **273,087** | **228,736** | **6,978** | **51,329** | **280,065** |

The product used **18.0% more total tokens despite 22.7% less U** overall.
Return-only totals rose 47.7% while U fell 41.4%. The frozen rule required complete
matched quality, at least 10% lower initial-plus-return U and no total-token
increase; it was not met. The product return received substantially more cached
input. Same source caches do not guarantee equal provider prompt-cache reuse;
this observation is not a causal cache advantage or a money estimate.

On return the product made 5 observed commands versus 2, read 54,366 explicitly
metered source-body bytes versus 21,685, and emitted 37,502 observed recall bytes
versus 33,154. Both arms performed the same 12 metered integrity reads totaling
221,289 bytes. The brief view therefore did not eliminate the existing integrity
work. The product reader additionally requested metadata and reread both unchanged
required pages; both readers read the relevant changed project page. The trace
does not say the interface required those extra reads. Read guidance and source
scope are investigation targets, with reader-strategy variation explicitly
retained; these counters do not causally allocate native tokens. Ordinary shell
reads and interpreter work are not completely metered.

## Preserved failures and limits

The original read-only runtime failed on uv temporary writes, and generic Python
lacked requests. All four initial readers across both products recovered and read
verified sources; their original answers and full costs remain. Both return arms
for both products were then run through the same independently verified pinned
interpreter. No semantic answer repair or favorable-run selection occurred.

Three original return attempts and two calibrations remain separate study
overhead: 937,025 total native tokens / 230,209 U. All 11 primary attempts and
two calibrations together used 2,171,170 total / 535,714 U across both products.
The amended pair is not a clean initial-runtime replication. Provider caching
and reader trajectory vary; one pair supplies no confidence interval or causal/
general claim. The harness's loose “historical remote” phrase did not establish
public-origin freshness.

There were zero new remote source acquisitions in this cached replay. It does not
remeasure HTTP/manifest transfer economics or reverse the prior full-audit HTTP
preference. Original acquisition, publisher upkeep, human attention and
implementation/coordination/grading tokens remain unknown. No total-program or
monetary saving is claimed; prior PD2/recovery/pilot evidence remains frozen.

The [batch acceptance record](/Users/maxwell/Documents/Codex/2026-11-06/task/measured-savings/acceptance/report.md)
links immutable protocols, every raw attempt, runtime corrections, independent
[quality grading](/Users/maxwell/Documents/Codex/2026-11-06/task/measured-savings/acceptance/review/quality-review.md)
and [native reconciliation](/Users/maxwell/Documents/Codex/2026-11-06/task/measured-savings/acceptance/review/native-cost-review.md).
[Native counters](/Users/maxwell/Documents/Codex/2026-11-06/task/measured-savings/acceptance/evaluation/native-costs.json)
retain reasoning/cache-write fields and separate local-read layers.
