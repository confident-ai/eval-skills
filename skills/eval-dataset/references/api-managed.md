> Operation names were checked against the available MCP inventory on 2026-09-30; individual REST recipes and live calls remain untested. Every MCP call except `list_projects` requires the selected `project_id`. Prefer the connected tool schema over spellings in examples.

# Build dataset: managed on Confident AI

Datasets live on Confident AI as named collections of goldens, versioned and
editable by the whole team.

## Creating the dataset

With the MCP server connected:

- `push_dataset` with an `alias` (for example `"support-bot-core"`) and
  either `goldens` (single-turn) or `conversational_goldens` (multi-turn).
  Set `finalized: false` if the user still has to review cases in the UI.
- `create_golden` to add one case to an existing dataset (`alias`, `golden`).
- `pull_dataset` to read it back; `create_dataset_version` to snapshot it
  before large edits.

Single-turn golden fields: `input`, `expected_output`, `context`,
`retrieval_context`, `tools_called`, `expected_tools`, `additional_metadata`.
Multi-turn golden fields: `scenario`, `expected_outcome`, `turns`, `context`,
`additional_metadata`. Put tags and the source trace id in
`additional_metadata` (`{"tags": [...], "source_trace_id": "..."}`).

Without MCP: `POST https://api.confident-ai.com/v1/datasets/{alias}` with
`{"goldens": [...]}` and the `CONFIDENT_API_KEY` header.

Teams can also add traces to a dataset straight from the trace view in the
Confident AI UI, which is often quicker for curating from reviewed traces.

Record `managed.dataset_alias` in `.eval/default/workflow.json`.

## Reviewing cases

The sign-off still happens: either produce `.eval/default/dataset/REVIEW.md` as the
skill describes, or push with `finalized: false` and ask the user to review
and finalize each golden in the dataset page. Only finalized goldens are used
in evaluation runs.

## Conversation scenarios

For multi-turn apps, write conversational goldens with `scenario`,
`expected_outcome`, and a `user_description` in `additional_metadata`. To
turn a scenario into a full conversation for testing:

- `simulate_conversation` returns the next simulated user message for a
  golden and its turns so far, and whether the expected outcome was reached.
  Alternate it with calls to the app until it reports completion.
- Or let the platform do the loop when running evals: `eval-run` covers
  `run_dataset_evaluation` with simulation turned on.

## Synthetic inputs

Follow Part A of the skill. Generate the inputs yourself (with the user's
real examples as anchors), show them, then push the approved ones with
`push_dataset`. Run the app over them so their traces land in Confident AI for
error analysis.
