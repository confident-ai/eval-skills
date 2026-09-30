#!/usr/bin/env node
/**
 * Send collected outputs to Confident AI to be graded by a metric collection.
 * Node twin of upload_results.py.
 *
 *   CONFIDENT_API_KEY=... node upload-results.mjs --variant baseline --collection support-bot-core \
 *     [--param model=gpt-4.1-mini --param prompt=v3] [--region us|eu] [--dry-run]
 *
 * Reads .eval/default/runs/<variant>/results.jsonl (written by run-evals.ts with
 * --graders none) and .eval/default/dataset/goldens.jsonl, and creates one test run on
 * Confident AI named after the variant.
 *
 * Part of eval-skills (Apache-2.0). Node standard library only (Node 18+).
 */
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

const argv = process.argv;
const arg = (name, fallback) => {
  const i = argv.indexOf(name);
  return i > -1 ? argv[i + 1] : fallback;
};
const params = argv.flatMap((a, i) => (a === '--param' ? [argv[i + 1]] : []));
const variant = arg('--variant');
const collection = arg('--collection');
if (!variant || !collection) {
  console.error('usage: upload-results.mjs --variant <name> --collection <metric collection>');
  process.exit(1);
}
const region = arg('--region', (process.env.CONFIDENT_REGION ?? 'us').toLowerCase());
const api = region === 'eu' ? 'https://eu.api.confident-ai.com' : 'https://api.confident-ai.com';
const readJsonl = (p) => (existsSync(p) ? readFileSync(p, 'utf8').split('\n').filter((l) => l.trim()).map((l) => JSON.parse(l)) : []);
const asText = (v) => (typeof v === 'string' ? v : JSON.stringify(v));
const toolCalls = (items) =>
  items?.length
    ? items.map((t) => ({ name: t.name, inputParameters: t.input && typeof t.input === 'object' ? t.input : undefined, output: t.output }))
    : undefined;

const goldens = new Map(readJsonl(arg('--dataset', '.eval/default/dataset/goldens.jsonl')).map((g) => [g.id, g]));
const rows = readJsonl(join(arg('--runs', '.eval/default/runs'), variant, 'results.jsonl'));
if (!rows.length) {
  console.error(`No results for ${variant}; run run-evals.ts --graders none first.`);
  process.exit(1);
}
const llmTestCases = rows.map((r) => {
  const g = goldens.get(r.case_id) ?? {};
  return JSON.parse(
    JSON.stringify({
      name: `${r.case_id}#${r.rep}`,
      input: asText(r.input),
      actualOutput: asText(r.output),
      expectedOutput: g.expected_output ?? undefined,
      context: g.context ?? undefined,
      retrievalContext: r.retrieval_context ?? undefined,
      toolsCalled: toolCalls(r.tools_called),
      expectedTools: toolCalls(g.expected_tools),
    }),
  );
});
const body = {
  metricCollection: collection,
  llmTestCases,
  identifier: variant,
  ...(params.length ? { hyperparameters: Object.fromEntries(params.map((p) => p.split(/=(.*)/s).slice(0, 2))) } : {}),
};
if (argv.includes('--dry-run')) {
  console.log(`Would upload ${llmTestCases.length} test cases as '${variant}' against '${collection}'.`);
  process.exit(0);
}
const key = process.env.CONFIDENT_API_KEY;
if (!key) {
  console.error('Set CONFIDENT_API_KEY first (the user adds it to .env).');
  process.exit(1);
}
const res = await fetch(`${api}/v1/evaluate`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', CONFIDENT_API_KEY: key },
  body: JSON.stringify(body),
});
if (!res.ok) {
  console.error(`Upload failed (${res.status}): ${(await res.text()).slice(0, 500)}`);
  process.exit(1);
}
const payload = await res.json().catch(() => ({}));
const data = payload.data ?? payload;
console.log(`Created test run ${data.id ?? '?'} for '${variant}' (${llmTestCases.length} cases). Grading runs on Confident AI; open Test Runs in the project to follow it.`);
