---
name: eval-descent
description: Improve an AI application through bounded, evidence-linked experiments against validated evals. Use for quality, latency, cost, or model migration; requires a trustworthy baseline.
license: Apache-2.0
metadata:
  author: Confident AI
  version: "1.1.0"
---

# Descent: reduce failures through bounded experiments

Read [the operating agreement](references/workflow.md), [experiment design](references/experiments.md), and [execution requirements](references/execution.md). Use [managed workflow guidance](references/managed.md) when selected.

For bundled local tools and exact commands, read [toolkit setup](references/toolkit.md). Run [the workspace installer](scripts/setup_workspace.py) for this skill; it preserves existing customized files.

## Agree on the loop

Descent is the name of this improvement loop, not a claim that it computes gradients. Define the objective explicitly: reduce an error, cost, or latency measure, or improve a quality measure while protecting agreed guardrails.

If a trustworthy baseline is missing, use `eval-build` when installed to establish it, or identify the missing cases, calibration, and run evidence before experimenting. Do not treat unvalidated scores as an optimization target.

Audit the baseline before experimenting. Recompute scores; inspect execution errors, grader validation, signal size, and whether the proposed lever actually reaches the app. Fix broken measurement first.

Agree once on the target, protected metrics, editable files/settings, off-limits behavior, maximum rounds or plateau condition, and paid budget. Offer per-change review when requested; default to autonomous work inside the agreed boundary. Do not deploy or merge automatically.

## Each round

1. Diagnose development examples and observed mechanisms. Reuse the reviewed failure taxonomy and its evidence links; if annotations need grouping, use `eval-error-analysis` when installed, or produce a reviewable taxonomy before choosing a target. Keep this analysis on development evidence. Where delegation is available and permitted, give one fresh analyzer only development records, current artifacts, scope, and target. Otherwise diagnose locally while excluding held-out content.
2. Propose one causal hypothesis with supporting cases, predicted benefit, and possible regressions. A patch can touch multiple files if it implements one hypothesis. Prefer operational instructions over vague prompt padding.
3. Apply the scoped patch and save its diff, rationale, and configuration fingerprint. Changes to the runner or grader require reviewing measurement impact, not quietly counting a new score as an app improvement.
4. Smoke-test settings and execution. Run the fixed comparable set at the agreed repetitions. Preserve raw results and billed errors.
5. Recompute comparisons, inspect guardrails, and keep or revert. Record the decision and uncertainty. Suspect implausible jumps until the underlying behavior explains them.

Use validation scores for selection and development traces for diagnosis. Do not repeatedly select on a set called “final test.” For small exploratory sets say so and collect new confirmation evidence before a strong claim.

## When progress stalls

Classify remaining development failures: missing capability/content, grader disagreement, infrastructure, inaccessible information/structure, or variation. Fix the bottleneck instead of adding another paragraph to a prompt. Regrading after a grader correction must include all comparable variants and preserve old verdicts.

Stop at agreed limits or an unresolved guardrail regression. Offer an extension before exceeding budget; never treat an offer as approval. Do not keep a marginal win solely because its point estimate is higher.

## Handover

Restore the selected version, or the baseline if no change is supported. Run final untouched confirmation when available. Report target/guardrail deltas, uncertainty, total spend where measurable, representative before/after evidence, and what was tried. Distinguish required compatibility fixes from optional tuning. Deliver a local patch/commit only when authorized; publishing remains a separate action.
