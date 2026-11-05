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

Preparation for PD2, PD3, PD4 and PD5 can start without PD1 completion. Prefer PD1
plus question/baseline and publisher preparation when PageDigest is the only
project. Across both projects with four slots, reserve coordinator + D1 + PD1 +
one rotating preparation worker. Refill ready work as results land. A worker can
prepare the next case while a dependency is pending; a waiting outcome is not
accepted work. Avoid permanent roles, mandatory extra reviewer agents or a full
suite in every lane.

## Reserve shared boundaries

The coordinator owns changes to SPEC/CONTRACT/schema, conformance vectors,
dependency manifests/locks, shared CLI/storage contracts, release/version files,
CI/check routing, and dogfood manifest/state. Workers propose needed changes;
the coordinator either implements them or explicitly transfers ownership. Freeze
the smallest usable consumer interface early so PD2 harness integration can start
while PD1 installation/recovery work continues. PD4 can prepare policy and cases
first, then integrate after consumer ownership is released.

Keep the PD2 question/oracle author independent of implementation decisions where
possible: freeze cases before exposing outcomes and record later corrections.
Publisher runs do not wait for a consumer. PD2's all-in cost conclusion does wait
for publisher effort, PD4 acceptance waits for a useful evaluated finding and the
recipient's own-policy validation, and PD5 independent use waits for its roadmap
joins. Cross-project finding interfaces belong to the parent coordinator.

Each Python worker uses an absolute `UV_PROJECT_ENVIRONMENT` outside the checkout
that is unique to its lane. Use unique result/cache/state paths and process-assigned
ports; never share a mutable consumer store. Isolate Cargo target directories for
concurrent Rust work in separate checkouts. Do not switch another worker's branch,
reset its changes, regenerate shared dogfood state or overwrite evidence.

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

The roadmap does not authorize publication, outreach, paid runs, access changes
or protocol expansion. Follow the current user's authorization when delivery is
in scope; [release gates](../RELEASE_CHECKLIST.md) and the [strict dogfood policy](../CONTENT_HYGIENE.md#dogfood-deployment-policy)
still govern it.
