# Recurring completed-workflow control — November 4, 2026

Both arms retained source-bound setup and limits notes through six controlled
cycles: cold, warm, changed setup, lost limits body, origin failure and recovery.
Five cycles completed; the forced failure remained incomplete with the affected
finding unknown. Setup changes invalidated only setup notes, the refreshed note
used a new immutable ID, and every available body matched the fixture oracle.

| Measured work | PageDigest | Same HTTP cache |
| --- | ---: | ---: |
| Started requests | 14 | 12 |
| Consumed response-body bytes | 1,199 | 365 |

This is a developer-defined two-page local control, authored after source
exposure. Its finding texts and expected outcomes are supplied by the control;
it is not independent task completion, adoption or a new general efficiency
study. The earlier P1 38.6% loss remains intact. The small control also loses on
requests and consumed body bytes; favorable warm reuse does not erase cold,
manifest, audit or recovery cost. Headers/TLS, native tokens, human effort and
money are unmeasured. No external origin or model calls occurred.

The existing publisher helper discovered pages from the final build, with
durable state outside it. Initial setup, unchanged rebuild and one source update
used three helper preparations (preview plus apply each). No second page catalog
was edited. Initial explicit choices were initialization, complete coverage and
digests; intervention time, backup/recovery maintenance and production deployment
were not measured. The unchanged rebuild changed no resource revisions.

[result.json](result.json) retains every cycle, failure, HTTP event, publisher
change set and measured client CPU. Replay with a fresh result path:

```sh
cargo build --manifest-path implementations/rust-generator/Cargo.toml --locked
uv run --project implementations/python-consumer --locked python tools/check_recurring_outcome.py --output /tmp/recurring-control-new.json
```

Limits are six cycles, at most five requests and 1 MiB consumed per arm/cycle,
with a 60-second body deadline. Failure/recovery force audits in both arms. This
control supports the workflow mechanics and keeps the combined-work proof gap
open. It does not supersede an independently operated comparison or the recorded
DotRepo export-time churn control.
