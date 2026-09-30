"""Adapter between the eval runner and the real application.

Copy to .eval/default/scripts/app_adapter.py and implement run_case(). It must call the
app's REAL entry point (the same function, route, or command production uses),
not a re-creation of its LLM call. Stub only side effects that can't run
safely (sending emails, writing to production databases).

run_case returns the "result" half of the eval-skills grader contract:

    {
      "output": ...,                    # required: the final answer
      "retrieval_context": [...],       # optional: retrieved chunks, if graders need them
      "tools_called": [{"name", "input", "output"}],  # optional
      "turns": [...],                   # optional: full conversation for multi-turn cases
      "model": "...",                   # optional: model reported by the response (not the config)
      "usage": {"input_tokens": 0, "output_tokens": 0},  # optional: from the response
      "trace_id": "...",                # optional: links the case to its trace
    }

Raise on failure. The runner classifies the exception (timeout, rate limit,
harness error) and records it in errors.jsonl instead of scoring it.

Part of eval-skills (Apache-2.0).
"""

from __future__ import annotations


def run_case(case: dict) -> dict:
    # Example for a single-turn app whose entry point returns text:
    #
    #   from app.agent import answer
    #   reply = answer(case["input"])
    #   return {"output": reply}
    #
    # Example for an app that exposes retrieval and usage:
    #
    #   response = answer_with_details(case["input"])
    #   return {
    #       "output": response.text,
    #       "retrieval_context": [doc.text for doc in response.documents],
    #       "model": response.model,
    #       "usage": {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens},
    #   }
    raise NotImplementedError("Implement run_case() to call the application's real entry point.")
