# Example: support bot

A deliberately imperfect customer-support bot for trying Eval Skills without
your own app. It answers policy and order questions with a retriever, an
order-lookup tool, and one model call, and it has a few realistic flaws for
error analysis to find (an invented return window, a warranty overclaim, and
asking for an order number the user already gave).

## Try it

```bash
cd examples/support-bot
pip install confident-trace openai
SUPPORT_BOT_OFFLINE=1 python app.py "Can I return shoes after 45 days?"
```

`SUPPORT_BOT_OFFLINE=1` uses canned replies, so no API keys are needed. Unset
it and set `OPENAI_API_KEY` to use a real model. Traces go to
`.eval/default/traces/` by default (`EVAL_SKILLS_TRACE_MODE=local`), or to Confident
AI with `EVAL_SKILLS_TRACE_MODE=confident` and `CONFIDENT_API_KEY`.

`tracing/` holds unmodified copies of the `eval-trace` templates.

## Skip straight to review

`sample-traces.jsonl` holds 60 normalized traces from this bot. To try error
analysis right away on a local track:

```bash
mkdir -p .eval/default/traces && cp sample-traces.jsonl .eval/default/traces/traces.jsonl
```

Then ask your agent: "Run error analysis on this app's traces."
