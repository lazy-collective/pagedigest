# Public visual family

PageDigest shares Lazy Collective's warm paper, evergreen, serif headings,
system body fonts and visible keyboard focus. Existing URLs, protocol,
publisher/consumer entrypoints and historical article body remain owned here.

`site/assets/lazy-collective/v1/family.css` is a self-hosted copy of Lazy
Collective's `design/v1/family.css`; `UPSTREAM.json` pins version 1.0.0 and SHA-256.
`site/assets/site-family.css` owns product layout. There are no remote fonts or
runtime design packages. Change the shared source, copy it explicitly with the
parent `tools/sync_family.py`, then verify the receipt and this repo's full checks.
A published shared version is immutable: new bytes need a new versioned path,
with old assets retained while referenced.

The manifest covers three successful HTML pages, not the CSS dependency graph
or 404 template. Findings that depend on styles or other resources must check
those dependencies separately. A changed stylesheet does not expand manifest
coverage. Regenerate changed HTML with `tools/generate_dogfood_manifest.py`,
preserve durable state/high-water marks, then follow [strict dogfood policy](../CONTENT_HYGIENE.md#dogfood-deployment-policy).
Keep `_worker.js` and `_headers` no-transform controls; do not adopt a transformed
response hash to make verification pass. Browser QA and `tools/run_checks.sh`
supplement, rather than replace, repeated exact-byte checks.

The [umbrella home](https://lazycollective.org/) is live and linked from the
product homepage. Source and local previews do not establish child-site delivery;
verify the current main commit and live manifest before treating a checkout as deployed.
