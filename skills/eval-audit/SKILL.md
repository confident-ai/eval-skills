---
name: eval-audit
description: Audit existing AI evaluation evidence, graders, datasets, and run reliability before trusting a score or optimizing an application. Not a generic code or security review.
license: Apache-2.0
metadata:
  author: Confident AI
  version: "1.1.0"
---

# Audit an existing evaluation

Read [the operating agreement](references/workflow.md). Inspect artifacts; do not produce findings from a checklist alone.

For bundled local tools and exact commands, read [toolkit setup](references/toolkit.md). Run [the workspace installer](scripts/setup_workspace.py) for this skill; it preserves existing customized files.

## Gather evidence

Find the runner command, actual app entrypoint, cases, reference origins, full traces, human labels, grader definition/version, and raw results. Reuse connected observability tools or local exports. For the managed track read [hosted workflow guidance](references/managed.md).

## Checks

1. **Task validity:** Does the metric measure the desired outcome? Are failure categories observed or merely generic names? For an acting agent, does the check inspect resulting state?
2. **Data validity:** Are inputs current, representative for the claimed rate, and legally retainable? Identify synthetic cases and model-generated reference answers. Check duplicates and shared conversations across splits.
3. **Trace validity:** Do output, score, model identity, usage, and transcript correspond to the same execution? Inspect tool calls and retrieval where relevant. Missing content may be a capture-policy limit, not an app failure.
4. **Grader validity:** Examine expert disagreements, false passes and false failures. Test empty output, an answer to a different question, a known pass, and a known fail. Verify case references before blaming the model.
5. **Harness validity:** Induce a safe local error. It must be reported as an execution error rather than a capability zero. Check retry policy, timeouts, incremental writes, and resume identity.
6. **Comparison validity:** Recompute the headline from raw rows. Compare dataset, judge, mode, app/configuration, and environment versions. Inspect error rates and missing-data denominators. Check that a parameter actually reaches the app and any subagents.
7. **Resolution:** Estimate uncertainty and headroom against the smallest useful improvement. Repetitions over one generated index or memory store cannot measure the variance of rebuilding it.

Classify findings as blocking (invalid claim), important (weak evidence), or improvement. Each needs an artifact reference, observed consequence, and concrete fix. Mark unavailable evidence as unknown, not passed.

## Repair without erasing history

Correcting a grader requires retaining old grades and regrading all compared stored outputs. Correcting app execution may require rerunning the baseline. Version the change, show whether rankings move, and return to the appropriate stage. Do not tune the app to work around a mislabeled reference.

Deliver the recomputed result, confidence limits, failure/error breakdown, prioritized findings, and the next executable step. If trustworthy, reuse the pipeline.
