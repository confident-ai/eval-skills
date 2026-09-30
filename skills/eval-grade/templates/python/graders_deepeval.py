"""Graders for the local track, using DeepEval metrics as standalone graders.

Copy to .eval/default/graders/graders.py. Replace the examples with one grader per
failure mode (ids from .eval/default/eval-skills.json). Every grader follows the
eval-skills grader contract:

    grade(case: dict, result: dict) -> {"passed": bool, "reason": str, "score": float, "confidence": float | None}

and raises (instead of returning a fail) when it can't decide.

Judge mode comes from EVAL_SKILLS_JUDGE_MODE:
    jev  -> DeepEval eval_mode="system_one" (Jev decides; needs TYPESAFE_API_KEY)
    llm  -> an LLM judge (set EVAL_SKILLS_JUDGE_MODEL; Anthropic shown below)

Part of eval-skills (Apache-2.0).
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable

from deepeval.metrics import FaithfulnessMetric, GEval, JevEval
from deepeval.metrics.jev_eval import Noul
from deepeval.test_case import LLMTestCase, SingleTurnParams, ToolCall

JUDGE_MODE = os.getenv("EVAL_SKILLS_JUDGE_MODE", "jev")


def judge_model():
    """LLM judge for llm mode. Pass a model object; a bare "claude-..." string is routed to OpenAI."""
    from deepeval.models import AnthropicModel

    return AnthropicModel(model=os.getenv("EVAL_SKILLS_JUDGE_MODEL", "claude-sonnet-5-5"), temperature=0)


def _text(value) -> str:
    return value if isinstance(value, str) else ("" if value is None else str(value))


def test_case(case: dict, result: dict) -> LLMTestCase:
    """Map an eval-skills case + app result onto a DeepEval test case."""
    return LLMTestCase(
        input=_text(case.get("input")),
        actual_output=_text(result.get("output")),
        expected_output=case.get("expected_output"),
        context=case.get("context"),
        retrieval_context=result.get("retrieval_context"),
        tools_called=[
            ToolCall(name=t["name"], input_parameters=t.get("input") or {}, output=t.get("output"))
            for t in result.get("tools_called") or []
        ]
        or None,
        expected_tools=[
            ToolCall(name=t["name"], input_parameters=t.get("input") or {})
            for t in case.get("expected_tools") or []
        ]
        or None,
    )


def _grade(metric, tc: LLMTestCase) -> dict:
    metric.measure(tc)  # raises on missing fields or API errors; the runner records those separately
    if metric.error:
        raise RuntimeError(f"{metric.__name__}: {metric.error}")
    return {
        "passed": bool(metric.is_successful()),
        "reason": metric.reason or "",
        "score": metric.score,
        "confidence": getattr(metric, "confidence", None),
    }


# --- Example 1: a code check (no judge). -------------------------------------
# Failure mode: "mentions-competitor". Prefer plain code whenever it can decide.

COMPETITORS = re.compile(r"\b(acme|globex)\b", re.IGNORECASE)


def mentions_competitor(case: dict, result: dict) -> dict:
    match = COMPETITORS.search(_text(result.get("output")))
    return {
        "passed": match is None,
        "reason": f"Mentions {match.group(0)!r}." if match else "No competitor named.",
        "score": 0.0 if match else 1.0,
        "confidence": None,
    }


# --- Example 2: a custom judgment criterion. ---------------------------------
# Failure mode: "invented-policy" — states a window, fee, or rule that isn't in
# the retrieved policy. One Noul statement that is true exactly when it passes.

PASS_STATEMENT = (
    "Every return window, fee, and eligibility rule stated in the actual output "
    "appears in the retrieval context, or the actual output states none."
)


def invented_policy(case: dict, result: dict) -> dict:
    params = [SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.RETRIEVAL_CONTEXT]
    if JUDGE_MODE == "jev":
        metric = JevEval(
            name="invented-policy",
            evaluation_params=params,  # always explicit; omitting it switches to trace mode
            questions=[Noul(PASS_STATEMENT)],
            threshold=0.5,
            async_mode=False,
        )
    else:
        metric = GEval(
            name="invented-policy",
            criteria=(
                "PASS if every return window, fee, and eligibility rule in the actual output "
                "appears in the retrieval context (or none is stated). FAIL otherwise."
            ),
            evaluation_params=params,
            model=judge_model(),
            strict_mode=True,  # binary verdict
            async_mode=False,
        )
    return _grade(metric, test_case(case, result))


# --- Example 3: a built-in metric. -------------------------------------------
# Failure mode: "unsupported-answer" — claims not backed by retrieved context.


def unsupported_answer(case: dict, result: dict) -> dict:
    if JUDGE_MODE == "jev":
        # Jev scores are probabilities: pass when an unsupported claim is unlikely.
        metric = FaithfulnessMetric(eval_mode="system_one", threshold=0.5, async_mode=False)
    else:
        metric = FaithfulnessMetric(model=judge_model(), strict_mode=True, async_mode=False)
    return _grade(metric, test_case(case, result))


# --- Example 4: tool use (agents). -------------------------------------------
# Failure mode: "wrong-tool" — calls a different tool than the case expects.
# Tool names are objective, so plain code decides. Reach for
# ArgumentCorrectnessMetric (eval_mode="system_one") when the *arguments* need judgment.


def wrong_tool(case: dict, result: dict) -> dict:
    expected = [t["name"] for t in case.get("expected_tools") or []]
    called = [t["name"] for t in result.get("tools_called") or []]
    missing = [name for name in expected if name not in called]
    return {
        "passed": not missing,
        "reason": f"Expected {missing} to be called; called {called}." if missing else "Expected tools were called.",
        "score": 0.0 if missing else 1.0,
        "confidence": None,
    }


GRADERS: dict[str, Callable[[dict, dict], dict]] = {
    "mentions-competitor": mentions_competitor,
    "invented-policy": invented_policy,
    "unsupported-answer": unsupported_answer,
    "wrong-tool": wrong_tool,
}
