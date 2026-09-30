> Operation names were checked against the available MCP inventory on 2026-09-30; individual REST recipes and live calls remain untested. Every MCP call except `list_projects` requires the selected `project_id`. Prefer the connected tool schema over spellings in examples.

# Run evals: managed on Confident AI

Grading runs on Confident AI against the metric collection from
`eval-grade`. Each run becomes a **test run** you can open, filter, and
compare with earlier runs in the project.

There are two ways to produce the outputs, depending on where the app runs.

## Option A: run the app locally, grade on Confident AI

Use this for apps that run from the repo (the common case).

1. **Get the dataset.** `pull_dataset` with the alias (or
   `GET /v1/datasets/{alias}`) and write the finalized goldens to
   `.eval/default/dataset/goldens.jsonl` in the local case shape
   (`id`, `input`, `expected_output`, `context`, `tags`).
2. **Collect outputs** with the runner template in collect-only mode. It
   calls the app through the adapter, with concurrency, timeouts, retries,
   and resume, and runs no graders locally:

   ```bash
   python .eval/default/scripts/run_evals.py --variant baseline --reps 2 --graders none
   npx tsx .eval/default/scripts/run-evals.ts --variant baseline --reps 2 --graders none   # Node
   ```

3. **Upload for grading**, one test run per variant, with the settings that
   define the variant as hyperparameters:

   ```bash
   python .eval/default/scripts/upload_results.py --variant baseline --collection support-bot-core --param model=gpt-4.1-mini --param prompt=v3
   node .eval/default/scripts/upload-results.mjs --variant baseline --collection support-bot-core --param model=gpt-4.1-mini
   ```

   The same call is available as the `run_llm_evals` MCP tool
   (`metric_collection`, `llm_test_cases`, `identifier`, `hyperparameters`).

4. **Read the results** with `list_test_runs` (newest first; status, pass and
   fail counts) and `get_test_run` (per-metric scores and per-case verdicts).
   Compute the headline and its interval from the per-case verdicts as the
   skill describes, and give the user the test run link.

## Option B: let Confident AI call the app

Use this when the app is deployed and reachable over HTTP. Configure it once
as an **AI connection** in the project, then start runs with
`run_dataset_evaluation` (`alias`, `metric_collection`, `ai_connection_id`,
`identifier`, `num_generations` for repetitions). For multi-turn datasets set
`include_simulation: true` and Confident AI simulates each conversation from
the golden's scenario before grading. Runs are asynchronous; the response has
the test run id and link.

## Comparing variants

Keep the baseline test run fixed. For each change, run the same dataset with
the same reps under a new `identifier` and hyperparameters, then compare the
two test runs on the platform (side by side, per case) and, for the verdict,
compute the paired difference from `get_test_run` results as the skill
describes. The platform also shows regressions between runs of the same
dataset.

## Regression gate in CI

In CI, run Option A (collect + upload) with an `identifier` such as the
commit SHA, then fetch the test run's results and fail the job if a metric's
pass rate drops below the agreed floor. Store `CONFIDENT_API_KEY` as a CI
secret.
