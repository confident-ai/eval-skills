<!-- Synced from shared/grader-contract.md by scripts/sync_shared.py. Edit shared/grader-contract.md, not this copy. -->

# Local grader contract

On the local tracks, every grader is a plain function with the same shape, so
the eval runner, the validation script, and the monitoring job can call any
of them without knowing how it works inside.

## Python

```python
def grade(case: dict, result: dict) -> dict:
    """Return {"passed": bool, "reason": str, "score": float, "confidence": float | None}."""
```

Graders live in `.eval/default/graders/graders.py`, collected in a registry:

```python
GRADERS = {
    "invented-policy": invented_policy,     # failure-mode id -> grader function
    "missing-order-id": missing_order_id,
}
```

Async graders (`async def`) are allowed; callers await them.

## TypeScript

```ts
export type Grade = { passed: boolean; reason: string; score?: number; confidence?: number | null };
export type Grader = (testCase: EvalCase, result: AppResult) => Grade | Promise<Grade>;
export const GRADERS: Record<string, Grader> = { 'invented-policy': inventedPolicy };
```

Graders live in `.eval/default/graders/graders.ts`.

## Arguments

- `case`: one dataset row from `.eval/default/dataset/goldens.jsonl` (`id`, `input`,
  `expected_output`, `context`, `tags`, `metadata`, or the conversational
  fields).
- `result`: what the app produced for that case, as assembled by the runner:

  ```json
  {
    "output": "the final answer (text or JSON)",
    "turns": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}],
    "retrieval_context": ["chunk text", "..."],
    "tools_called": [{"name": "lookup_order", "input": {"order_id": "A17"}, "output": {"status": "delivered"}}],
    "trace_id": "5b8aa5a2…"
  }
  ```

  Only `output` is always present. The runner fills the rest when the app
  exposes them (see `run-evals`).

## Return value

| Field | Meaning |
|---|---|
| `passed` | The verdict. `true` means the failure mode was **not** observed. |
| `reason` | One or two sentences a person can check against the trace. |
| `score` | Optional number in [0, 1] when the underlying check has one (a judge's probability, a similarity). Reports use `passed`. |
| `confidence` | Optional, for judges that report calibrated confidence. |

A grader that can't decide (missing field, API error) must **raise**, not
return `passed: false`. The runner records raised errors separately so a
broken grader never looks like a failing app.
