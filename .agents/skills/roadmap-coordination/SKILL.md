---
name: roadmap-coordination
description: Coordinate PageDigest roadmap packets across a coordinator and concurrent workers, with disjoint ownership, early preparation and evidence-gated joins. Use for team execution of PD1–PD5, not routine single-file edits.
---

# PageDigest roadmap coordination

Read the checkout's [AGENTS](../../../AGENTS.md), [current roadmap](../../../ROADMAP.md)
and [execution guide](../../../docs/agent-execution.md). They own priorities,
dispatch boundaries and acceptance; do not create another queue here.

Confirm actual branch/HEAD, task authorization and available slots. Reserve one
coordinator and dispatch only ready, bounded work with exclusive files and unique
environment/output paths. Prepare questions/baselines, publisher work and handoff
cases in parallel; preserve the roadmap's acceptance joins. Carry the parent
coordinator's shared goal and cross-project interface decisions when present.

At a join, require the exposing case, result, changed files and limits. Use the
[validation guide](../../../docs/validation.md) for focused worker checks and one
appropriate integrated gate. Preserve negative evidence and distinguish useful
evaluated findings from source-status labels. Return remaining dependencies and
the next ready packet; do not infer release or outreach authority from the plan.
