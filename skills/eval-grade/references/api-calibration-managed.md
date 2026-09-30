> Operation names were checked against the available MCP inventory on 2026-09-30; individual REST recipes and live calls remain untested. Every MCP call except `list_projects` requires the selected `project_id`. Prefer the connected tool schema over spellings in examples.

# Validate graders: managed on Confident AI

## Collect labels

Create one annotation queue per failure mode being validated, so each label
answers exactly one question:

- `create_annotation_queue` with `name` like `"label: invented-policy"` and
  `type: "TRACE"` (or `"THREAD"` for conversation-level metrics).
- `add_items_to_annotation_queue` with the traces to label: reviewed traces
  from error analysis plus fresh random ones, aiming for ~50 fails and ~50
  passes.

Tell the reviewer the rule for this queue in one sentence, in pass/fail
terms: thumbs up = the failure mode is **absent**, thumbs down = present, with
a short explanation for each fail.

## Split and iterate

Read the labels with `list_annotations` (filter by trace, then keep only
annotations from this queue's items). Draw train/dev/test splits over the
labeled trace ids yourself, stratified by rating, and save them to
`.eval/default/validation/splits.json` so they stay fixed.

Run the metric on dev traces with `evaluate_trace` (or `evaluate_thread`),
passing the metric collection and `overwrite_metrics: true` when re-running
after an edit. Read each trace's verdict back with `get_trace`, compute TPR
and TNR, and walk through disagreements with the user. Revise the metric with
`update_metric` (criteria, steps, and rubric are replaced wholesale), putting
only train cases into its examples.

Confident AI's **Annotation Alignment** view shows how metric verdicts line
up with human annotations across the project; point the user there for a
visual check alongside your numbers.

## Measure test once

When dev meets the target, evaluate the test traces once, compute TPR and
TNR, and record them in `.eval/default/workflow.json`. Don't edit the metric after
seeing test results; relabel a fresh dev set instead if it needs more work.
