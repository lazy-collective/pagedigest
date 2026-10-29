# Digest Exchange P1: bounded freshness result

**No-go for a PageDigest savings claim on this workload.** The final run completed
2,016 assigned client/scenario rows with zero freshness, representation or inventory
violations under the frozen policy. PageDigest transferred **3,802,164** response
bytes versus **2,744,160** for HTTP freshness caching, which tied sitemap-lastmod.
That is **38.6% more**, against a preregistered requirement of at least 20% less.
No wire-format extension or shared coordinator is justified by this result.

The [summary](summary.json) is readable JSON; the [full final run](run-003.json.gz)
retains every row and all 85,680 HTTP response events. These are local fixture
observations, not production, adoption, dollar-cost or model-token measurements.

| Strategy | Requests | Response bytes | Client CPU, seconds |
| --- | ---: | ---: | ---: |
| Full fetch | 14,856 | 5,125,968 | 7.103 |
| Conditional HTTP | 14,856 | 4,116,960 | 5.534 |
| HTTP freshness | 9,576 | 2,744,160 | 3.859 |
| Sitemap-lastmod | 9,576 | 2,744,160 | 3.809 |
| Fingerprint manifest | 12,216 | 3,584,520 | 4.700 |
| Fingerprint manifest with audits | 12,216 | 3,685,488 | 4.709 |
| PageDigest with audits | 12,384 | 3,802,164 | 4.843 |

Bytes include compressed response bodies, identity audit bodies, response headers,
discovery, fallback, and failed fetches. They exclude request headers, TCP and TLS.
The primary gate uses the full assigned matrix, not a favorable warm-only subset.
PageDigest exceeded the best baseline by 55.1% for 10 pages and 36.6% for 100 pages;
one and three clients had the same proportional outcome within each size.

## Frozen workload and correctness

[SPEC.json](SPEC.json), retained with its hash, predates implementation and
measurement. Seven strategies see the same content and update schedule: 10 and
100 pages, one and three independent clients, three repetitions, and twelve cycles.
Execution order is deterministically shuffled within each cycle. Logical time
advances 30 seconds per cycle; CPU and wall time are measured, not simulated.

Every strategy must validate each retained body by age 60 seconds. An unchanged
manifest does not renew that deadline. The fixture serves ETags, gzip, max-age
and language variants; the HTTP freshness arm can reuse a fresh body without an
origin request. The experimental cache implements this fixture's policy, not a
general RFC-complete HTTP cache. A request for revalidation, missing body, changed
representation or expired validation triggers a fetch.

The cases cover cold/unchanged/sparse/concealed changes, deadline recovery,
addition/removal, lost cached bodies, partial PageDigest coverage, language change,
request no-cache, origin failure and recovery. PageDigest uses the existing
reference planner plus the experiment's explicit body deadline. Partial coverage
and unsupported variants require safe discovery/fetch fallback.

Each arm records **24 incomplete cycles**, exactly the assigned origin-failure
cases; all other cycles complete. The final gate rejects unexpected incomplete
cycles as well as false completion. PageDigest and the four other metadata/freshness
arms each record **24 stale-body observations within the allowed deadline** after
the concealed change. All recover at the deadline. Full and conditional fetches
observe no stale bodies. Zero violations therefore means compliance with the
bounded-staleness policy, not immediate change detection or exact-current bytes
at every cycle. The original exact-byte benchmark remains a separate control.

## Costs and limits

The final run used 85,680 requests, 25,803,420 total response bytes and about 56.8
seconds of measured matrix wall time, within its 100,000-request, 1 GiB and
600-second caps. It made no model calls or external-origin requests.

Publisher metadata generation is measured once per arm per shared fixture update,
not once per client. Across the matrix, PageDigest metadata generation used 5.764 ms
of fixture CPU versus 0.778 ms for the sitemap used by HTTP freshness. Response
preparation used 248.306 ms versus 190.379 ms. These measurements exclude socket
writes and use a small Python fixture, not the Rust publisher or a production CDN.
Client CPU is measured separately from server threads and the correctness oracle.

PageDigest read 27,515,328 bytes from its body cache and wrote 5,846,256 bytes.
The full per-cycle disk I/O and elapsed times remain in the raw report. This is
the experiment's on-disk cache; the shipped persistent example is still exercised
by the original benchmark and repository checks. There is no coordinator arm,
large-site scaling, upstream task execution, economic amortization or independent
operator evidence in this study. CPU timings vary by machine and run.

## Replay and retained corrections

From the repository root:

```bash
uv sync --project implementations/python-consumer --extra dev --locked
uv run --project implementations/python-consumer --locked python \
  tools/benchmark_consumers.py --freshness-study --output /tmp/pagedigest-p1-new.json
./tools/run_checks.sh
```

The freshness-study flag selects the frozen matrix; `--pages` applies only to the
original benchmark. The runner refuses an existing result path and verifies the
specification hash. Results include harness hashes. The final implementation is
in [benchmark_freshness.py](../../../tools/benchmark_freshness.py).

All three measured runs are retained as lossless gzip with encoded and decoded
hashes in [retained-artifacts.json](retained-artifacts.json). Earlier harness
snapshots are retained beside runs 001 and 002. These are development replays of
the same experiment, not three independent studies.

- Run 001 completed but overcounted cache reads in the variant transition: it
  counted files that were present but were not read. Its network totals are valid.
- Run 002 fixes that accounting and caps combined response/output storage. An
  initial startup attempt failed before HTTP work because the editable package
  installation was missing; rebuilding it enabled the retained measured run.
- Run 003 additionally disables ambient proxy settings, retains a partially
  completed cycle when its budget stops execution, and makes unexpected incomplete
  cycles fail the correctness gate. A regression test exercises a two-request cap.

The primary request and response-byte totals are identical across all three runs.
[Diagnostics](diagnostics/) retain the initial development-test failure, its
successful correction, the startup error and the later focused checks. The frozen
specification and negative threshold were not revised after observing outcomes.

The practical decision is to retain ordinary HTTP freshness and sitemap metadata
as the comparison to beat. PageDigest v1 remains an available batching protocol;
this experiment does not establish an additional savings benefit worth a larger
Digest Exchange implementation.
