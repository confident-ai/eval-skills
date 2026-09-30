---
name: eval-maintain
description: Maintain trusted AI evaluations through CI regression checks, production feedback, dataset refresh, and grader recalibration. Use after a baseline exists; not generic deployment or security scanning.
license: Apache-2.0
metadata:
  author: Confident AI
  version: "1.0.0"
---

# Keep evaluation useful after the first run

Read [the operating agreement](references/workflow.md), [maintenance guide](references/maintenance.md), and [managed workflows](references/managed.md) when applicable.

## Establish ownership

Identify the existing CI, release process, production observability, reviewer, and baseline. Reuse them. Agree on which failures block a release, which merely flag review, and how infrastructure errors are handled. A failed request is never a silent passing check.

## Regression checks

Create a small representative suite plus known-failure regressions. Pin cases, grader versions, app configuration, and independent confirmation rules. Separate fast deterministic checks from slower paid evaluation. Expose skipped or missing-credential runs rather than reporting a pass.

For managed PR workflows, inspect current Confident Actions setup and generated callback/workflow. Confirm it invokes the actual app and reports the intended check. For local workflows use the project's CI and runner, with credentials kept in its secret store. Do not expose paid secrets to untrusted pull-request code.

## Production feedback

Define sampling policy and population before measuring rates. Include random normal traffic alongside complaints and failure-triggered samples. Use trace/thread identity to link user feedback, human labels, and resulting regression cases.

Managed users reuse hosted review and monitoring. Local users reuse a collector, scheduled export, or existing job system; do not create an always-on agent loop unless requested. New recurring work requires an agreed cadence and notification policy.

## Refresh

After model, prompt, tool, retrieval, or audience changes, inspect fresh traces for new failure types. Preserve a stable regression suite and version a refreshed representative suite. Revalidate judges against new expert labels and rerun baselines when criteria change.

Alert on actionable thresholds with ownership, minimum sample sizes, error context, and deduplication. Do not confuse provider failures with application quality drift.

## Deliver

Provide the verified CI command/check, sampling and alert policy, owner, versioned evidence locations, and next review trigger. State what has actually been enabled versus merely documented. Never silently deploy a candidate or start a recurring paid job.
