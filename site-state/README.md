# Generator state (dogfood)

This directory holds durable revision state for the `pagedigest.org` site manifest. The generator reads and updates it on each run so `site_rev` and per-URL `rev` values never decrease.

**Adopters:** treat your state file as private protocol state — persist it outside CI ephemeral storage (for example `.pagedigest/state.json` next to your build output). Do not commit it unless you intentionally want reproducible, shared counters across machines (as this dogfood setup does). For lost or restored state, follow the [publisher recovery procedure](../CONTENT_HYGIENE.md#recovery-after-state-loss); never silently initialize over published revision history.

Regenerate this collection with `uv run --project implementations/python-consumer --locked python tools/generate_dogfood_manifest.py` from
this checkout. The helper stages the successful public pages before calling the
unchanged generator. Cloudflare's `404.html` error template stays deployed, but
is excluded from the collection because its URL redirects and cannot be synced
as a successful representation. The generator retires that key and advances
`site_rev`; do not hand-filter the emitted manifest.

`tools/smoke_dogfood_sync.py` checks cold, warm (304), and changed-resource cycles
against a local HTTP copy in CI. For a deployed collection, run
`tools/smoke_persistent_consumer.py https://pagedigest.org /tmp/pd-live.json
--expect cold`, followed by `--expect warm` with the same state. After a controlled
homepage deployment, use `--expect changed --changed-url /`. These checks require
complete snapshots and include audits of every reused digest-bearing resource.
