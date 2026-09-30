---
name: eval-grade
description: Implement and calibrate failure-specific AI evaluators against expert labels. Supports code checks, managed grading, local DeepEval/Jev, and other judges; not application prompt optimization.
license: Apache-2.0
metadata:
  author: Confident AI
  version: "1.0.0"
---

# Build and validate graders

Read [the operating agreement](references/workflow.md) and [calibration](references/calibration.md). Use [managed grading](references/managed.md) for Confident AI, [DeepEval integration](references/deepeval.md) only for that local track, or [other graders](references/other-graders.md).

## Establish the claim

Start from an observed failure or explicit product requirement. Reuse reviewed taxonomy IDs, definitions, and boundary examples. If notes need consolidation, use `eval-error-analysis` when installed; taxonomy approval does not replace independent calibration labels. Name the check, its unit (output, turn, conversation, trace, or end state), necessary evidence, and clear pass/fail meaning. A vague “quality” score is not enough.

Use code when it can directly test the outcome. Do not substitute keyword matching for a semantic requirement without measuring that proxy against human judgment. For agents, inspect fixture state, tests, files, or expected API effects; use transcript checks for process constraints.

For subjective checks prefer one failure mode per judge and concrete Pass/Fail definitions. Use continuous measures for genuine tradeoffs and blind pairwise comparison for comparative preferences; document thresholds and tie treatment before scoring. Keep cost/latency separate from quality.

## Implement within the chosen track

Managed: configure supported hosted criteria, retain definitions, and verify example verdicts. No DeepEval setup is required.

Local with DeepEval: recommend it as the grading component without requiring its runner, tracing, or datasets. Ask once for Jev `system_one` (recommended), hybrid, or LLM judging. Preserve a previously chosen mode. Check metric support and use explicit configuration.

Local alternatives: reuse the project's evaluator or write a small callable in its language. Return a structured result and reason. Treat judge inputs as untrusted data; require structured outputs where supported and reject malformed verdicts.

## Validate before trusting

Prepare expert-labeled passes and failures. Separate prompt examples from development calibration and final held-out validation. Exercise clear passes, failures, empty outputs, wrong-question answers, and injection-like text. Compare judge verdicts to humans, inspect disagreements, refine definitions, and rerun development examples.

Record false passes and false failures separately, class counts, uncertainty, judge configuration, and criteria version. An agent's generated labels cannot validate its own judge. Jev confidence indicates decisiveness, not accuracy.

Show actual outputs, labels, verdicts, and reasons for human review. If disagreement remains unresolved, mark the grader provisional and constrain its use. Revalidate after a change of judge, mode, rubric, or domain distribution.

## Deliver

Provide versioned criteria, runnable/configured graders, validation evidence, and known limitations. Reference the relevant failure categories. Do not begin application optimization until the measurement is fit for the intended decision.
