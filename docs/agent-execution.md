# Coordinated roadmap execution

Use the [current roadmap](../ROADMAP.md) for the work graph. This guide owns team
mechanics, not a second queue. Start by checking branch, HEAD, dirty files and
linked worktrees; preserve other agents' work. Carry the user's scope and the
shared goal: useful recurring work at declared quality/freshness, counting total
publisher, intermediary and consumer cost.

## Dispatch a small complete result

One coordinator reserves shared contracts and integration. Workers take disjoint
files or isolated worktrees with explicit ownership; directories in the roadmap
are starting boundaries, not permission to edit every file in them. Give each
worker:

- Packet, concrete outcome and the upstream interface/commit it can rely on.
- Owned files, reserved files, and the other active lanes it must accommodate.
- Acceptance case, focused checks and a unique artifact directory.
- Any authorization/budget limits and the exact result that returns ownership.

Select dependency-ready work from the current roadmap after reconciling accepted
implementation, preparation and delivery receipts. Do not replay completed PD1
or preparation because an older schedule listed it first. With four available
slots, reserve one coordinator and use up to three workers across the selected
projects. Refill ready work as results land; independent preparation can proceed
while an outcome dependency is pending. A waiting outcome is not accepted work.
Avoid permanent roles or a full suite in every lane; rotate finished workers
into fresh review when independence is required.

## Reserve shared boundaries

The coordinator owns changes to SPEC/CONTRACT/schema, conformance vectors,
dependency manifests/locks, shared CLI/storage contracts, release/version files,
CI/check routing, and dogfood manifest/state. Workers propose needed changes;
the coordinator either implements them or explicitly transfers ownership. Freeze
the smallest usable consumer interface early so PD2 harness integration can start
while entrypoint work continues, when those packets remain open. Reuse accepted
interfaces and preparation. Handoff policy/cases can precede integration after
consumer ownership is released.

Keep the PD2 question/oracle author independent of implementation decisions where
possible: freeze cases before exposing outcomes and record later corrections.
Publisher runs do not wait for a consumer. An all-in savings claim requires
comparable publisher effort; missing measurements do not block a scoped pilot or
its repairs. PD4 acceptance waits for a useful evaluated finding and the
recipient's own-policy validation. PD5 owner/agent operation uses the accepted
entrypoint and permitted real task; independent validation has its own evidence
requirements. Cross-project finding interfaces belong to the parent coordinator.

Each Python worker uses an absolute `UV_PROJECT_ENVIRONMENT` outside the checkout
that is unique to its lane. Use unique result/cache/state paths and process-assigned
ports; never share a mutable consumer store. Isolate Cargo target directories for
concurrent Rust work in separate checkouts. Do not switch another worker's branch,
reset its changes, regenerate shared dogfood state or overwrite evidence.

## Measure before comparing

Before an evaluation starts, define the cost metrics, units, collection method
and accounting boundaries in its protocol. Collect available measurements from
the first attempt, including setup, failures, fallback, audits and unfinished
work. Keep overlapping byte/read layers separate. Record human attention and
interventions separately from machine elapsed time, requests, bytes, CPU, tokens
and money. Identify unavailable measurements as unknown; do not reconstruct
unrecorded human effort or billing with retrospective estimates. PD3 measurements
can be collected during owner/agent PD5 operation. Missing human/all-in measurements
limit claims, not readiness. Label an agent-operated or owner-operated pilot as
such; it does not establish independent third-party adoption.

Use the current roadmap's authorized pilot scope. Independent-operator recruitment,
complete cost accounting and seven qualifying scheduled days are not prerequisites
to that pilot or other ready local work. Continue operating-history observations
with honest dates/counts while development proceeds. Required correctness,
source-freshness, recovery, CI and publication checks remain in force.

After each comparison, record its product decision and evidence in the owning
roadmap or linked result: continue, simplify, narrow the intended workload,
prefer the baseline, or await named evidence. Keep the original rubric, source
identities, quality/freshness requirements and negative results. A new experiment
needs its own identity; it cannot replace a losing or incomplete original.

## Join once and retain evidence

Return changed files, interface assumptions, the exposing case and its result,
exact commands, failures/limits and artifact paths. Count unsuccessful attempts;
label local fixtures, evaluated work, independent use and adoption separately.
Original frozen studies and negative results remain at their original paths.

The coordinator reviews the diff and dependency joins, reconciles shared files,
then runs the appropriate integrated gate once on the combined tree using the
[validation guide](validation.md). Repeat only when later edits or failures
invalidate that receipt. A partial answer, missing source or stale observation
must remain visible as such. Tests demonstrate behavior, not utility or savings.

## Review delivery and closure

Before a delivery batch merges, review its related roadmap, status, dependency
and completion wording together. Consolidate related documentation corrections
where practical so avoidable follow-up merges do not queue repeated publication.
Keep independently useful implementation slices small. This changes the review
sequence, not the required gates: retain exact-source checks, exact served bytes,
current-main checks, recovery and any owning repository's archive-before-promotion
controls. Source merge, website deployment and package publication remain separate
observations.

Before goal closure, a fresh reviewer compares the original outcome criteria
with accepted receipts, checks for remaining authorized executable work and
verifies the canonical handoff routes to the accepted checkouts. Review scope
and wording before the final documentation merge; verify its final identity and
delivery afterward. Report engineering acceptance, demonstrated product benefit
and outcomes awaiting external evidence separately. A completed batch alone does
not close a sustained goal. Use the user's current stopping condition and record
explicit scope changes alongside the original criteria. Separate evidence still
needed for independent validation or economic claims from dependencies that
actually prevent the next authorized action. Preparation, manual retries or
expected future schedules do not supply missing outcome evidence; their absence
does not stop the authorized owner/agent pilot or other ready work.

The roadmap does not authorize publication, outreach, paid runs, access changes
or protocol expansion. Follow the current user's authorization when delivery is
in scope; [release gates](../RELEASE_CHECKLIST.md) and the [strict dogfood policy](../CONTENT_HYGIENE.md#dogfood-deployment-policy)
still govern it.
