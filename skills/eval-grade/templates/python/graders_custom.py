"""Graders for the local track, written without an eval library.

Copy to .eval/default/graders/graders.py next to judge.py. Replace the examples with
one grader per failure mode (ids from .eval/default/eval-skills.json). Every grader
follows the eval-skills grader contract:

    grade(case: dict, result: dict) -> {"passed": bool, "reason": str, "score": float, "confidence": None}

and raises (instead of returning a fail) when it can't decide.

Part of eval-skills (Apache-2.0).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable

try:
    from .judge import binary_judge
except ImportError:
    from judge import binary_judge


def _text(value) -> str:
    return value if isinstance(value, str) else ("" if value is None else json.dumps(value))


# --- Example 1: a code check. ------------------------------------------------
# Failure mode: "missing-order-id" — asks for the order number although the
# user already gave one.

ORDER_ID = re.compile(r"\b[A-Z]\d{2,}\b")
ASKS_FOR_ID = re.compile(r"order (number|id)\??", re.IGNORECASE)


def missing_order_id(case: dict, result: dict) -> dict:
    gave_id = bool(ORDER_ID.search(_text(case.get("input"))))
    asked = bool(ASKS_FOR_ID.search(_text(result.get("output"))))
    failed = gave_id and asked
    return {
        "passed": not failed,
        "reason": "Asked for the order number after the user gave it." if failed else "OK.",
        "score": 0.0 if failed else 1.0,
        "confidence": None,
    }


# --- Example 2: a structural check against the output format. ----------------
# Failure mode: "bad-json" — the app must return JSON with "answer" and "sources".


def bad_json(case: dict, result: dict) -> dict:
    try:
        data = json.loads(_text(result.get("output")))
        missing = [k for k in ("answer", "sources") if k not in data]
    except ValueError as err:
        return {"passed": False, "reason": f"Not valid JSON: {err}", "score": 0.0, "confidence": None}
    return {
        "passed": not missing,
        "reason": f"Missing fields: {missing}" if missing else "Valid JSON with required fields.",
        "score": 0.0 if missing else 1.0,
        "confidence": None,
    }


# --- Example 3: an LLM judge. --------------------------------------------------
# Failure mode: "invented-policy". Definitions come from the error-analysis notes;
# few-shot examples come from the validate-graders TRAIN split only.

INVENTED_POLICY_EXAMPLES: list[dict] = []  # fill after validate-graders draws the development split


def invented_policy(case: dict, result: dict) -> dict:
    verdict = binary_judge(
        criterion="Does the reply state a return window, fee, or eligibility rule that is not in the policy text?",
        pass_definition="Every window, fee, and rule in the reply appears in the policy text, or the reply states none.",
        fail_definition="The reply states a window, fee, or rule the policy text doesn't contain, or contradicts it.",
        fields={
            "Policy text": "\n\n".join(result.get("retrieval_context") or []) or "(none retrieved)",
            "Assistant reply": _text(result.get("output")),
        },
        examples=INVENTED_POLICY_EXAMPLES,
    )
    passed = verdict["verdict"] == "pass"
    return {"passed": passed, "reason": verdict["critique"], "score": 1.0 if passed else 0.0, "confidence": None}


GRADERS: dict[str, Callable[[dict, dict], dict]] = {
    "missing-order-id": missing_order_id,
    "bad-json": bad_json,
    "invented-policy": invented_policy,
}
