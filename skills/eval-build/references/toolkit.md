# Run the bundled toolkit

Reuse existing project infrastructure first. For a new local workflow, install the templates shipped inside the selected skill rather than regenerating its server, runner, or storage. Customize trace rendering, the application adapter, and graders for the product.

## Install and resume

From the application repository, run the installed skill's `scripts/setup_workspace.py --flow support --language python` (or `--language typescript`). The default flow is `default`; `--root /existing/eval/location` preserves a previously selected workspace. Run the same installer from each needed skill. Existing files are preserved, never overwritten; review template updates before applying them to customized code.

The installer reports copied/preserved files and records installed skills in `.eval/<flow>/workflow.json`. Keep stage, track, decisions, milestones, evidence locations, reviewer ownership, and approved run scope there. It installs resources; it does not mark a human review or a run complete. Missing sibling skills are not an error: explain the missing capability, reuse an existing implementation, or install that focused skill.

Examples below use `.eval/default/`. Other flow installers rewrite template defaults to the selected absolute root. Use explicit CLI paths when reusing an existing workspace. Do not move generated scripts after installation without updating their configured paths.

## What gets installed

| Skill | Runnable resources |
| --- | --- |
| eval-trace | Python/TypeScript tracing setup, local OTLP exporter, normalizer, replay |
| eval-discover | Sampler and Python/Node review app |
| eval-error-analysis | The same synchronized review app and sampler for standalone use |
| eval-grade | Custom and framework grader templates, judge adapters, calibration, group splitter |
| eval-run | Python/TypeScript runner, report, upload helper, portable export adapter |
| eval-descent | Group-disjoint development/validation/test splitter |
| eval-maintain | Local monitoring job |

Python helper CLIs use Python 3.10+. TypeScript runners need Node 22+ and the project's `tsx`/TypeScript tooling. Both review servers use only their runtime's standard library. The sampler, Descent splitter, and portable exporter are Python utilities usable with either application language. Framework grading and tracing templates require their respective SDKs; check installed versions before adapting.

## Local sequence

1. **Trace:** install the trace skill's templates, put the generated scripts directory on the application's import path, and call `setup_tracing()` / `setupTracing()` before model imports. Default capture is local even if a hosted key exists. Choose `EVAL_SKILLS_TRACE_MODE=confident` only after the managed route is selected. Run `python .eval/default/scripts/normalize_traces.py` or `node .eval/default/scripts/normalize-traces.mjs` after a real request. `replay_spans.py --dry-run` / `replay-spans.mjs --dry-run` inspects a proposed upload without sending it.
2. **Review:** run `python .eval/default/scripts/sample_traces.py --n 25`, then `python .eval/default/review-app/server.py` or `node .eval/default/review-app/server.mjs`. Open the printed loopback URL, enter the actual reviewer's name, and save notes. Stop the server after review. Use `--mode label` for calibration and mark uncertain judgments explicitly.
3. **Analyze:** use the Progress view to review mode definitions and memberships separately. Add, rename, merge, split, retire, and reassign without erasing history. Agent proposals go into the local taxonomy as proposed definitions and suggested assignments; never invent human confirmation. A split returns affected assignments to the unresolved queue. Export saves annotations, taxonomy revisions, and evidence in one JSON response.
4. **Curate:** write `dataset/goldens.jsonl` with stable IDs, `group_id`, full input, source provenance, and grader-only expectations. Adapt existing cases rather than requiring a new dataset system.
5. **Grade:** choose `scripts/graders_custom.py` or `scripts/graders_deepeval.py` (TypeScript equivalents are also supplied), copy the chosen registry and any judge helper to `graders/graders.py` or `graders/graders.ts`, and replace the examples with product criteria. Calibration commands: `python .eval/default/scripts/validate.py split --mode <criterion>`, then `run --mode <criterion> --split validation`, finally `--split test` once. TypeScript uses `npx tsx .eval/default/scripts/validate.ts`. The fixed splits are group-disjoint; inspect label/task coverage before fitting a judge.
6. **Run:** implement `scripts/app_adapter.py:run_case` or `scripts/app-adapter.ts:runCase` against the actual app. The runner passes only ID, input/scenario, and attachments to this adapter; graders receive the full case. Run `python .eval/default/scripts/run_evals.py --variant baseline --dry-run`, then the approved run. TypeScript: `npx tsx .eval/default/scripts/run-evals.ts`. Supply `--config` for non-secret model/judge/fixture settings and `--app-version` when Git does not identify the application. Runs with different settings need different variants.
7. **Report and export:** run `python .eval/default/scripts/report.py` or `node .eval/default/scripts/report.mjs`. Export either runner's native records with `python .eval/default/scripts/export_bundle.py --variant baseline --output /new/bundle`, then validate using the artifact helper. Native records retain additional data; the portable v1 contract remains unchanged. Actual runtime traces are preserved when returned as `trace`; otherwise exported traces explicitly identify themselves as limited runner records.
8. **Descent:** `python .eval/default/scripts/split_cases.py` freezes group-disjoint `development_ids.json`, `validation_ids.json`, `test_ids.json`, and `select_ids.json`. Read development examples, select candidates using validation, and use test once for confirmation. Do not redraw splits based on scores.

## Limits and accounting

The runner's timeout bounds waiting on a call; it cannot forcibly stop synchronous Python worker code or a provider request already in flight. Adapters must configure provider timeouts/cancellation and use disposable side-effect fixtures. Do not describe the wrapper as a hard process-kill ceiling.

`attempts.jsonl` is the call ledger for successful and failed app/judge invocations. Usage is recorded when exposed; absent values remain null. Summary usage includes known partial totals and missing-call counts. Do not add terminal result usage to attempt totals. Collection-only outputs are not graded passes. Grader failures remain errors; a normal refusal is graded according to product criteria.

Repeated calls are averaged within a case/group. The supplied Wilson interval is an approximation over independent groups; it does not model all within-case stochastic uncertainty. Small or unrepresentative sets support limited claims. The optional rate-correction helper conditions on the supplied observed rate; it is not a full population interval unless production-sampling uncertainty is also accounted for. Follow the calibration reference before using it for reporting.
