# Portable evidence contract, version 1

This is a minimal interchange contract for exports and examples, not a mandatory native database schema. Adapt existing records. Preserve original source exports and additional metadata. Unknown values are null or absent, never fabricated defaults.

A bundle contains `manifest.json`, `cases.jsonl`, optional `annotations.jsonl`, optional `results.jsonl`, optional `attempts.jsonl`, and referenced files below its root. References use relative paths, never traversal or external symlinks. Hosted URLs belong in metadata; copy required evidence locally when permitted to make an offline bundle.

## Manifest

Required: `schema_version: 1`, `flow` (nonempty string), `dataset_version` (nonempty string).

When results exist, require `run_id` and `run_fingerprint`. The fingerprint represents dataset, split, app, configuration, grader, environment/fixture, and repetition policy. Add their readable values to the manifest; a hash alone does not explain an experiment. `expected_results` is optional but recommended to detect a partial run.

Optional `splits` maps `development`, `validation`, and/or `test` to arrays of case IDs. When present it must cover every case exactly once, and one `group_id` cannot occur in multiple splits. `sample_purpose` distinguishes discovery, calibration, regression, and representative measurement.

## Cases

Required fields: `id`, `group_id`, `input`, `source`.

`id` and `group_id` are nonempty strings. `input` is a string or structured object carrying the full input. `source` is an object with a nonempty `kind` such as synthetic, production, expert, incident, or imported. Put source IDs, timestamps, and retention decisions there when known. Optional: tags, attachments, metadata, expected, reference_origin.

References and expected outputs belong to grader-only storage. A bundle containing them must not be mounted into an acting model's workspace. Create a separate app-visible input projection.

## Annotations

Required: `id`, `case_id`, `criterion_id`, `origin` (`human` or `agent`), `status` (`suggested`, `confirmed`, `dismissed`, `uncertain`), and `note` (string).

Optional `label` is `pass` or `fail`; open-ended discovery notes need no label. `confirmed` requires `reviewed_by`, a real reviewer identifier. An agent-origin suggestion can be human-confirmed while preserving its origin. Do not manufacture reviewer identities. Optional fields include created/updated timestamps, criterion version, and source annotation ID.

## Results

Required: `case_id`, nonnegative integer `rep`, `status`, `output`, `grades`, and `trace_ref`.

Statuses: `ok`, `app_error`, `grader_error`, `timeout`, or `truncated`. `output` may be null for an error, but must be present for `ok`. `trace_ref` is a local relative file reference; even an error trace can show what completed before failure. `grades` maps criterion IDs to objects containing finite numeric `score`, string `reason`, and nonempty `grader_version`. An `ok` result needs at least one grade. Error statuses cannot carry quality grades. A truncated result has no grades in this portable profile; use a separately versioned explicit policy if incomplete output is a scored product outcome.

A run has at most one terminal row per `(case_id, rep)`. Optional: refusal flag, model identity, judge identity, usage objects, duration, cost, metadata. A refusal can be a valid completed output graded by the task's criteria.

Usage objects (`usage` and `judge_usage`) map token field names to nonnegative integers or null. They contain measured counts only; their provider-specific semantics remain in metadata. `cost_usd` and `latency_s`, when present, are nonnegative finite numbers or null. Costs may be partial; record completeness.

## Attempts and raw traces

`attempts.jsonl` is optional append-only history: `case_id`, `rep`, positive integer `attempt`, `status`, and any measured usage/cost/error information. Its `(case_id, rep, attempt)` keys must be unique. Terminal results summarize the outcome, not additional billable calls; avoid counting their aggregated usage again when summing attempt-level costs.

Trace files retain the original format with a declared format in metadata, or use ordered messages/spans with stable IDs and parent IDs. Do not flatten a multi-step agent to final text if the criterion requires intermediate behavior. Preserve missing/truncated-content indicators.

## Helper

`skills/eval-run/scripts/artifacts.py` validates the structural subset above, inspects counts, or creates a deterministic group-disjoint split manifest. It checks references stay inside the bundle and exist; it cannot prove that a trace is truthful, human labels are authentic, a source is representative, or a judge is calibrated. Those require the workflow.

```bash
python3 skills/eval-run/scripts/artifacts.py validate /path/to/bundle
python3 skills/eval-run/scripts/artifacts.py inspect /path/to/bundle
python3 skills/eval-run/scripts/artifacts.py split /path/to/bundle --seed 42 --output /tmp/splits.json
```

The splitter uses group counts in a roughly 60/20/20 allocation, with at least one group in each split. It refuses fewer than three groups. Inspect task coverage and revise the design before freezing; it does not stratify automatically or choose statistically adequate sample sizes. Existing output files are not overwritten.
