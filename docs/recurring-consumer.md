# Recurring source and finding updates (experimental source workflow)

This checkout adds `pagedigest sync` and `pagedigest remember`. They are not in the
published 0.2.0 consumer. They reuse the existing atomic persistent-cache helpers
and PageDigest validation; they add no wire-format fields or hosted service.

A sync answers three questions in JSON: which source bodies changed, what needs
rereading, and which previously recorded findings still have usable source
bindings. Run one sync whenever your existing job or research workflow needs an
update. The command does not install a schedule, call a model, execute page
instructions, or infer conclusions for you.

## First observation

From this checkout, install the locked consumer environment, then choose a small
source scope. URLs are origin-relative and remain byte-exact.

```sh
uv sync --project implementations/python-consumer --extra dev --locked
uv run --project implementations/python-consumer --locked python -m pagedigest.cli sync \
  https://example.com ./research/example.json \
  --url /docs/start/ --url /docs/limits/ --max-age 3600
```

By default the workflow requests PageDigest if available. Missing, malformed or
anomalous manifests fall back to ordinary HTTP over the selected source scope.
Use `--http-only` to omit that manifest request altogether. An existing site's
sitemap can supply URL discovery:

```sh
uv run --project implementations/python-consumer --locked python -m pagedigest.cli sync \
  https://example.com ./research/example.json \
  --sitemap /sitemap.xml --http-only
```

A large manifest or sitemap can exceed the 200-source cycle bound. Narrow
discovery with one or more `--prefix` options (persisted like explicit URLs);
explicit `--url` sources stay in scope regardless:

```sh
uv run --project implementations/python-consumer --locked python -m pagedigest.cli sync \
  https://dotrepo.org ./research/dotrepo.json --prefix /v0/repos/github.com/astral-sh/
```

Only bounded, same-origin sitemap `urlset` files are supported. Sitemap indexes,
external entities and cross-origin entries are refused. `lastmod` changes cause
inspection; unchanged or missing `lastmod` does not prove unchanged content.
Omission from a sitemap does not delete an already observed source. Complete
PageDigest inventory omission can retire a discovered URL; an explicitly selected
URL is still checked directly. A direct HTTP 404/410 retires its cached mapping.

Explicit URL scope and sitemap location persist in the state, so subsequent
invocations can omit them. Repeat freshness, audit, HTTP-only and language options
when you want the same policy; they are command options rather than an implicit
scheduler configuration. Source coverage is bounded and is never an exhaustive
statement about the website.

With explicit URLs and no sitemap, sync observes only those URLs even if the
publisher's manifest describes a larger site. Supplying a narrower URL list
reports previous sources as `out_of_scope`, without claiming they were deleted.
Saved findings citing those sources remain recorded but become unknown until
their dependencies are synchronized again. Cited historical body objects remain.

## Save work against its actual sources

After reading cached sources, write your finding to a small UTF-8 file and bind it
to every source it depends on:

```sh
uv run --project implementations/python-consumer --locked python -m pagedigest.cli remember \
  ./research/example.json --id setup-note-1 --text-file ./setup-note.txt \
  --source /docs/start/ --source /docs/limits/
```

`remember` requires retained, intact bodies that were available in the last sync
and are still within that sync's validation deadline. It stores the text, exact
source SHA-256 values, representation identity and creation time atomically. IDs
are immutable: use a new ID when revising your work. The `.json.pages` directory
contains content-addressed source bodies; `pages` in the JSON maps URL keys to
filenames, and `body_hashes` exposes their bindings.

A finding is a user-supplied interpretation. Its list of sources is an explicit
claim about dependencies, not a discovered complete read set. An unlisted page,
new document, changed external premise, or mistaken inference can invalidate a
conclusion even while its listed source bytes are unchanged. Inventory-wide and
absence claims are outside this bounded workflow.

## Repeat and inspect the result

```sh
uv run --project implementations/python-consumer --locked python -m pagedigest.cli sync \
  https://example.com ./research/example.json --max-age 3600 > ./research/latest.json
```

| Report field | Meaning |
| --- | --- |
| `new` / `changed` | A fetched body's exact hash differs from the previous stored hash. |
| `reread` | New/changed bytes or unresolved sources needing attention. A failed read remains an error, not a successful change observation. |
| `removed` | Sources retired by direct 404/410 or complete PageDigest inventory omission; this does not prove global nonexistence. |
| `reused` | Intact cached body retained using HTTP freshness or an unchanged PageDigest signal within the validation deadline. |
| `revalidated` | A conditional HTTP 304 renewed a retained body's validation. |
| Finding `usable` | Every declared source still has the bound bytes, representation and acceptable observation age. This is not independent verification of the conclusion. |
| Finding `needs_reread` | At least one currently observed dependency has different bytes. |
| Finding `unknown` | A dependency is missing, failed, no longer observed, or belongs to a different representation. |
| `complete` | All work in this cycle's bounded scope completed. Successful sources may remain usable in an incomplete cycle. |

Exit status is **0** for a complete cycle, **2** for an incomplete cycle, and **1**
for invalid configuration/state or inability to persist the workflow. Keep every
cycle's report when evaluating recurring cost; do not discard failures. This
checkout's tests exercise controlled HTTP cycles and failure cases, not independent
adoption or economic savings.

## Freshness and failure rules

### HTTP client identity on Cloudflare Pages

Use a descriptive application `User-Agent`, such as `ResearchReader/1.0`.
The reference Python consumer now identifies its own default sessions as
`PageDigest-Python (+https://pagedigest.org/)`; supplied sessions retain their
configured headers, and the recurring workflow already identifies itself.
This source change is not a new package release.

Cloudflare Pages applies Browser Integrity Check in a Cloudflare-managed zone,
including on custom domains. A site's own skip/configuration rule cannot
exempt that layer. Its default Python `urllib` user agent can therefore receive
error 1010 even when the manifest is public. Cloudflare recommends identifying
the application, rather than pretending to be a browser; see its
[error 1010 guidance](https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-1xxx-errors/error-1010/).
For a bare urllib client:

```python
from urllib.request import Request, urlopen

request = Request(
    "https://pagedigest.org/.well-known/pagedigest.json",
    headers={"User-Agent": "ResearchReader/1.0"},
)
with urlopen(request, timeout=15) as response:
    manifest_bytes = response.read()
```

### Reuse policy

- HTTP `max-age`/`Expires` freshness can avoid a page request while the response
  is fresh, including with `must-revalidate`; `no-cache` requires validation.
- An unchanged entry in this cycle's validated manifest is the origin's validation
  of the stored body ([SPEC §5.1.2](../SPEC.md#512-interaction-with-http-caching)),
  equivalent to a 304, so it also covers `no-cache` and expired pages. The report
  labels that reuse `pagedigest-unchanged`. Otherwise the workflow revalidates with
  ETag/Last-Modified when a usable body exists. Manifest validation never permits
  retaining `no-store`, `private`, `Set-Cookie` or unsupported `Vary` responses.
- `--max-age` bounds time since body validation, even when a manifest repeatedly
  returns 304. Default: one hour. No metadata poll resets that deadline.
- Default audit probability is 0.01 per cached source per cycle. `--audit-rate 1`
  reads every reusable body without conditional validators. Audits can consume
  the declared budget and produce an incomplete cycle.
- A failed PageDigest digest/unchanged audit retains earlier bytes but marks the
  affected source unavailable for that cycle. Subsequent cycles fall back to
  ordinary HTTP until a newer publisher revision completes without contradiction.
  Unchanged claims do not suppress the HTTP recovery path.
- Lost or corrupt bodies are fetched again; neither a matching revision nor a
  304 without an intact conditional body recreates content. Failed attempts never
  renew that source's validation time. Successful observations can be committed
  alongside explicit failures; the state never labels that cycle complete.
- Each cache is bound to one origin and a fixed public representation, including
  `Accept-Language` and identity encoding. Changing `--language` invalidates finding
  reuse even if the text happens to match. For a non-default language PageDigest
  supplies discovery only; HTTP controls the representation.
- Redirects, authenticated sessions, unsupported `Vary`, `private`, `no-store`,
  `Set-Cookie`, and non-identity responses cannot produce retained public source
  evidence. Environment proxies/netrc and session cookies are disabled. This is
  a deliberately small public-GET cache, not an RFC-complete browser cache.

## Bounds and accounting

A cycle has at most 200 source URLs, 250 started requests and 50 MiB of consumed
response bodies; `--max-requests` and `--max-bytes` can lower the latter bounds.
Individual bodies/manifests/sitemaps are capped at 2 MiB. A 120-second elapsed
budget is checked before requests and during streaming; it is not a hard process
deadline. In-flight transport/DNS work can overshoot it, with 15-second HTTP
connect/read timeouts. Byte-limit detection may consume one
additional 64 KiB stream chunk, which is counted in the report. No retry loop or
paid inference is hidden in a cache miss.

State is capped at 4 MiB; each finding is capped at 32 KiB and 16 source references,
with at most 200 findings. Retained source bodies are capped at 128 MiB, including
old bodies still cited by findings. After a successful state commit, the workflow
removes only its unreferenced, hash-named body objects. It retains every current
body and every body cited by a saved finding, including stale findings. A full
cache refuses additional source retention instead of dropping those references;
archival/retention management is an explicit operator task.

Atomic state writes and an exclusive writer lock use the same approach as the
persistent example. A stale lock after a crash needs operator inspection.
Distributed writers and a general retention/archive service are not included.

Reports count every started request, status when available, consumed response-body
bytes and elapsed time, including failed attempts. They exclude HTTP headers,
TLS, server CPU, physical disk I/O and actual billing. They measure this run only.
Body counters are consumer-visible streamed bytes, not wire-byte measurements;
identity encoding is requested and encoded page responses cannot be retained.
The prior [P1 negative result](benchmarks/digest-exchange-p1-20261029/README.md)
remains unchanged: no bandwidth, token or total-cost improvement is claimed here.
