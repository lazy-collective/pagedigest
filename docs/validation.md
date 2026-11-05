# Validation and CI

Run commands from the checkout root and use `uv` for Python. Workers run focused
checks for their changed behavior and its exposing case. The coordinator runs
the integrated gate after joining lanes, rather than repeating it in every worker.
Use a unique absolute `UV_PROJECT_ENVIRONMENT` and evidence/output directory for
each concurrently executing lane; see [execution](agent-execution.md).

## Choose the gate

| Change | Required evidence |
| --- | --- |
| Explicitly allowlisted planning/team prose only | Local reference/fragment check, v1 status check and review of scope, dependencies and factual claims |
| Protocol, contract, fixtures, generated docs, package guides, runtime, dependencies, site/deployment or any unknown/mixed path | Focused behavioral regression plus the full repository gate |
| Release or production delivery | Full gate and the existing [release](../RELEASE_CHECKLIST.md) / [dogfood deployment](../CONTENT_HYGIENE.md#dogfood-deployment-policy) controls |

The prose allowlist lives only in [classify_ci_scope.py](../tools/classify_ci_scope.py).
It is deliberately small; `.md` is not enough to skip tests. Deleted/renamed
files, empty or unavailable Git comparisons and unknown event types select full
checks. Adding or changing routing itself also selects full checks. The reference
checker covers maintained guides; frozen reports/archives remain evidence, not
current instructions. It checks repository targets/fragments, not remote health,
rendering or factual correctness.

```sh
# Prose: review the diff, then check local references and stable status.
uv run --no-project python tools/check_docs.py
uv run --no-project python tools/check_v1_status.py
# CI/routing changes: actual Git additions, deletions, renames and missing bases.
uv run --no-project python -m unittest discover -s tools -p 'test_*.py' -v
# Integrated gate: all 20 stages, still callable directly.
./tools/run_checks.sh
```

Focused examples (select the relevant one; do not treat these as the full gate):

```sh
uv run --project implementations/python-consumer --extra dev --locked python tools/validate_vectors.py
uv run --project implementations/python-consumer --extra dev --locked python -m unittest discover -s implementations/python-consumer/tests -v
cargo test --manifest-path implementations/rust-generator/Cargo.toml --locked
```

The full script retains formatting/lint, protocol vectors, Python/Rust/Astro/npm
tests, generator progression/parity, Scrapy traversal and cache policy, clean
artifact installs, equivalent-outcome benchmarks, dogfood manifest/state and
whole-collection sync checks. Benchmark output uses a per-run temporary directory;
failed runs retain that directory for diagnosis. No quality floors or workload
cases were removed.

## Hosted execution and publication

Opening a PR is the hosted feedback entrypoint for non-main branches: plain branch
pushes no longer duplicate the PR run. The `test` job stays stable. A PR uses its
base SHA and checked-out merge commit for conservative routing; missing history
fails closed to full checks. Only explicitly known prose-only PRs take the fast
path, which runs reference/status and routing tests without Rust/Node setup.
Every main push and manual CI run uses all 20 stages. There is no scheduled CI
entrypoint; an added schedule or unknown event cannot qualify for docs-only checks.
PR runs may supersede older PR feedback. Main tests can overlap without canceling
one another; production alone serializes in its noncanceling group.

After successful main `test`, CI calls the same-revision reusable Deploy Pages
workflow. The call is bound to main's exact checked SHA; its checkout must equal
the event SHA. Deployment rechecks current remote main immediately before upload,
publishes only `site/`, then verifies exact manifest/body bytes and cold/warm
consumer synchronization. A manually dispatched Deploy Pages runs the full suite
itself. PRs and other event/ref combinations cannot enter automatic deployment.

Every successful main CI run still attempts publication, including a docs-only
commit: a prior source update may have failed to publish or been superseded.
The latest commit's path list is not a receipt of the published source. Production
uses one serialized group and retains the current-main check to reject old queued
runs. GitHub may replace pending runs in a concurrency group; it is not a FIFO
queue. Manual deployment remains the explicit recovery route when no subsequent
main run occurs.

The optimization removes duplicate branch/PR runs and the second full suite from
automatic deployment, and enables dependency caches. It does not claim a hosted
wall-time improvement before measurements. Package publication workflows retain
their independent artifact/release checks. Workflow semantics follow GitHub's
[reuse guide](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows)
and [workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax).
