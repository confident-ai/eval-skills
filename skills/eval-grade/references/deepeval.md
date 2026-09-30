# Local grading with DeepEval

This reference is only for the local DeepEval track. It does not introduce hosted tracing, reporting, synthetic generation, or a DeepEval runner. Keep the user's local data and UI independent.

## Choose the judging mode

When not already settled, ask: “For local grading, I recommend Jev (`system_one`). Would you prefer that, hybrid judging, or an LLM judge?” No extra permission question is needed to choose DeepEval itself within this track.

The supported Python spellings inspected in the current implementation are `system_one`, `hybrid`, and `llm`. The library defaults to `llm`; this suite recommends `system_one` explicitly. Read current [eval-mode documentation](https://deepeval.com/docs/evaluation-eval-modes) and inspect the installed metric's signature before generating code. Version support is a preflight, not an exception discovered after a full paid pass.

Jev uses a TypeSafe AI service credential; local orchestration is not local inference. Never ask users to paste secrets. Use current documented setup, such as the installed `set-typesafe` command when available, and the project's secret mechanism.

## A narrow adapter

For a supported text metric in Python:

```python
from deepeval.metrics import FaithfulnessMetric
from deepeval.test_case import LLMTestCase

def grade_faithfulness(case, output):
    # Use only if unsupported claims are an observed failure and the retrieved
    # evidence below is actually what the app saw during this execution.
    metric = FaithfulnessMetric(eval_mode="system_one")
    test_case = LLMTestCase(
        input=case["input"],
        actual_output=output["text"],
        retrieval_context=output["retrieval_context"],
    )
    metric.measure(test_case)
    return {
        "score": metric.score,
        "reason": metric.reason,
        "confidence": metric.confidence,
        "judge_cost_usd": metric.evaluation_cost,
    }
```

Create a metric per concurrent task unless its documentation guarantees safe reuse; metric instances carry mutable result state. Apply the human-calibrated threshold in the adapter and record the actual judge/model configuration. Do not replace absent retrieval context with invented documents or the expected answer.

For TypeScript use the installed supported equivalent, including its `evalMode` spelling; verify the current SDK rather than transliterating Python blindly. For custom criteria choose a supported custom judge. `JevEval` evaluates bounded questions directly and is Jev-backed regardless of eval mode; `GEval` does not become Jev-backed merely through a global setting. Check current docs for required question types and evaluation parameters. Plain test-case fields can avoid requiring a framework-specific trace representation.

## Compatibility and failures

A metric may not support `system_one`, text-only Jev may not accept an image, and request/context limits can reject a long trace. Preserve the case and show the limitation. Ask for an explicit alternative when it changes the established choice: a supported grader, an LLM mode, or human review. Do not truncate relevant evidence or silently change judges.

Hybrid may fall back internally to an LLM on a failed Jev decision. Capture exposed fallback reason/model and distinguish those results. `system_one` does not promise such fallback. A metric's configuration and mode are part of its version; different modes can yield different score semantics.

Use deterministic code checks without Jev for objective requirements. Validate all subjective metrics against human labels using the same protocol as other judges. A prebuilt metric name is not evidence that it measures this application's actual failure.
