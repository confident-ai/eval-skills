---
name: eval-run
description: Run an AI application against reviewed cases with validated graders, reliable traces, usage accounting, and resumable results. Use for baselines and comparisons, not for inventing criteria without evidence.
license: Apache-2.0
metadata:
  author: Confident AI
  version: "1.1.0"
---

# Run a reproducible evaluation

Read [the operating agreement](references/workflow.md), [execution requirements](references/execution.md), and [portable artifacts](references/artifacts.md). For hosted runs read [managed guidance](references/managed.md).

For bundled local tools and exact commands, read [toolkit setup](references/toolkit.md). Run [the workspace installer](scripts/setup_workspace.py) for this skill; it preserves existing customized files.
For the managed route, use [concrete service operations](references/api-managed.md) after confirming the connected schema.

## Prepare

Reuse the real application entrypoint and existing runner. Check reviewed cases, criteria, versions, split, fixtures, and intended claim. If those are missing, finish the corresponding discovery/curation/calibration stage first.

Choose case count, repetitions, app/judge settings, concurrency, timeout, and retry policy. Confirm paid scope before calling services; use existing authorized limits. A measured pilot supports duration and spend estimates. Include app, judge, and billed retry usage. No budget change is implicit authorization to continue.

## Pilot

Run one authorized case, then inspect the actual saved output, trace, grade, model identity, timing, and available usage. Verify unknown fields are not silently zero. Check that graders consume the actual app result and that requested settings take effect. Test local error classification without spending a full pass.

## Execute

Use fresh app outputs for each application comparison. Regrading stored output is valid for grader calibration, but label it as such. Write completed records incrementally. Run bounded concurrency, jittered retries, per-case wall-clock limits, and clean cancellation. Record errors and billable attempts separately.

Resume only against unchanged case, app, grader, and run fingerprints. Preserve at most one terminal record per case/repetition in a run; separate attempt history. If the app failed before grading, it is an execution error. An actual safety refusal or incorrect answer is an observed outcome whose grading follows the pre-agreed criteria.

Use the host's background execution when supported, with a progress artifact. Do not create subagents just to wait on a shell command. Verify completion from saved counts, not a notification alone.

## Report

Recompute aggregates from raw records. Show scorable count, error count, missing metrics, refusals, truncations, and denominators alongside scores. Do not present a partial pass as a complete run. Estimate uncertainty at the independent case/group level.

Managed: link the verified hosted run and preserve export/version identifiers. Local: build/reuse a readable report alongside the review UI; escape all untrusted text. Summarize per-case failures, metric tradeoffs, costs where known, and evidence links.

Deliver the exact rerun command and configuration. The bundled [artifact helper](scripts/artifacts.py) can validate portable records, inspect an export, and create group splits; it is not a replacement app runner.
