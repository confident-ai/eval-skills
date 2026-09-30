> Operation names were checked against the available MCP inventory on 2026-09-30; individual REST recipes and live calls remain untested. Every MCP call except `list_projects` requires the selected `project_id`. Prefer the connected tool schema over spellings in examples.

# First trace: managed on Confident AI

## Connect

1. **The user** creates a free account at
   [app.confident-ai.com](https://app.confident-ai.com), opens the project's
   settings, and copies the API key. Never create the account or handle the
   key yourself; ask the user to add it to `.env`:

   ```bash
   CONFIDENT_API_KEY=...          # the user pastes this
   EVAL_SKILLS_TRACE_MODE=confident
   ```

   EU-region projects also set
   `CONFIDENT_OTEL_ENDPOINT=https://eu.otel.confident-ai.com/v1/traces`.

2. **Optional, recommended: connect the Confident AI MCP server** so you can
   read traces and create queues, datasets, and metrics directly. The user
   runs one command with their key (Claude Code shown; other agents take the
   same URL and header in their MCP config):

   ```bash
   claude mcp add --transport http confident-ai https://mcp.confident-ai.com/mcp --header "Authorization: Bearer <CONFIDENT_API_KEY>"
   ```

   EU projects use `https://eu.mcp.confident-ai.com/mcp`. The MCP server is in
   beta and exposes many tools; if the user wants to keep the agent's context
   small, skip it and use the REST API below for the handful of calls these
   skills need.

## Verify the first trace

After one run of the app:

- **With MCP:** call `list_traces` (it takes `page_size`, `environment`,
  `start`, `end`), find the newest trace, then `get_trace` for its spans.
- **Without MCP:**

  ```bash
  curl -s "https://api.confident-ai.com/v1/traces?pageSize=5" \
    -H "CONFIDENT_API_KEY: $CONFIDENT_API_KEY"
  ```

  (EU: `https://eu.api.confident-ai.com`.)

Share the trace's link with the user so they see it in the Confident AI UI,
where spans, inputs, outputs, and token usage are laid out for reading.

If nothing arrives:

- check `EVAL_SKILLS_TRACE_MODE` isn't `local` or `off` and the key is loaded
  into the process environment;
- short scripts must end with `confident_trace.shutdown()` (Python) or
  `await shutdown()` (Node) so the last batch is sent;
- turn on diagnostics: `logging.getLogger("confident_trace.diagnostics").setLevel(logging.DEBUG)`
  in Python.

## What the platform gives you from here

- **Threads and users:** set `thread_id` and `user_id` and conversations group
  automatically.
- **Environments:** set `environment` to keep staging and production apart.
- **Annotation queues and failure-mode analysis** (next skill:
  `eval-error-analysis`).

Record `managed.region` in `.eval/default/workflow.json`.

## Bringing local history along

If the user was on a local track before, replay their recorded spans once:

```bash
python replay_spans.py --in .eval/default/traces       # or: node replay-spans.mjs --in .eval/default/traces
```

Run with `--dry-run` first to see how many batches will be sent. Move the
replayed files aside afterwards so they aren't sent twice.
