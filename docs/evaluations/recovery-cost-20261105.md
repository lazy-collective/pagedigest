# Conditional validation during failure and recovery — November 5, 2026

An intact cached page with a strong ETag can be validated conditionally even when
the publisher manifest changes or has become distrusted. The recurring consumer
previously suppressed all conditional validators in those cases, downloading
unchanged bodies again. This source repair preserves publisher distrust and all
post-response policy/digest checks while avoiding those body transfers.

This is a new engineering replay of the original PD2 failure/recovery case. It
does not replace the [original useful-work comparison](pd2-results-20261105.md),
rescore its answers, establish independent adoption or change published packages.
The owner pilot's separate 100%-audit result also remains unchanged.

## Matched result

The frozen runner starts from the original treatment-odd visit4 state and verifies
the original failed-deployment and recovery body hashes before executing either
implementation. It retains the same timestamps, three source URLs, 3,600-second
deadline, required external archive audit in each phase, and manual homepage plus
manifest fallback after the failed sync. Only the recurring consumer changes.

| Measured layer, both phases | Before requests / body bytes | After requests / body bytes |
| --- | ---: | ---: |
| Core sync | 8 / 83,098 | 8 / 31,097 |
| Required external audits | 2 / 17,004 | 2 / 17,004 |
| Original manual fallback | 2 / 30,555 | 2 / 30,555 |
| Total | 12 / 130,657 | 12 / 78,656 |

The repair saves **52,001 response-body bytes**: 62.6% of the core sync traffic,
or 39.8% with the original audit/fallback work included. It does **not** reduce
request count. In this replay, each core sync requests a scoped page at most once; the
other requests belong to the retained external audit and manual fallback.
This result is limited to the two original phases and strong validators. It
does not establish latency, CPU, token, human-effort or all-in cost savings, or
superiority over the original competent baseline.

## Correctness boundary

- A 304 that conflicts with the advertised digest still makes the cycle incomplete
  and the affected finding unknown, without renewing the old source validation date.
- Global publisher distrust still disables manifest-derived reuse. An unchanged
  failed revision uses HTTP fallback; coherent newer evidence is required to
  restore trust.
- The additional conditional path requires an intact, non-suspect cached body and
  a syntactically strong ETag. The 304 must return the same strong ETag; a missing,
  weak or different returned tag triggers one unconditional retry within the
  existing request/byte budget. This matters because `If-None-Match` uses weak
  comparison even when the request sends a strong tag
  ([RFC 9110 §13.1.2](https://www.rfc-editor.org/rfc/rfc9110.html#section-13.1.2)).
  Weak/malformed cached ETags and Last-Modified alone keep unconditional fetching
  when the manifest changes or is distrusted. Ordinary HTTP conditional behavior
  is unchanged. The retry can add a request when the response lacks strong proof;
  the optimization is not a guarantee of lower cost for every origin.
- Selected audits remain unconditional. With 100% auditing, the original pair
  still consumes 12 requests / 130,657 body bytes. Missing/corrupt-body controls
  reacquire the lost source unconditionally, consuming 81,148 body bytes each.
- Original finding objects, creation dates and original observations remain
  unchanged. Response retention restrictions, finite budgets and freshness
  deadlines continue to apply.

The [predeclared protocol](/Users/maxwell/Documents/Codex/2026-11-05/task/pagedigest-recovery/acceptance/reproduction/protocol.md),
[baseline](/Users/maxwell/Documents/Codex/2026-11-05/task/pagedigest-recovery/acceptance/reproduction/baseline-dev2/summary.json)
and [candidate replay](/Users/maxwell/Documents/Codex/2026-11-05/task/pagedigest-recovery/acceptance/candidate-replay-final/summary.json)
retain original source identities, every request and all five control cases.
The [delivery record](/Users/maxwell/Documents/Codex/2026-11-05/task/pagedigest-recovery/acceptance/report.md)
owns independent review, required checks and exact source/site delivery status.

## Product decision

Keep this bounded reduction in redundant body transfer. Preserve the original
negative comparisons and remaining request overhead. Subsequent real maintenance
work should declare required freshness and discrepancy-detection policy before
comparing with competent HTTP caching; neither lowering audits nor widening the
workload solely to obtain a favorable result is an accepted optimization.
