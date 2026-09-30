/**
 * Measure a grader against human labels: TPR, TNR, and the disagreements.
 * TypeScript twin of validate.py for Node projects (run with tsx).
 *
 *   npx tsx validate.ts split --mode invented-policy
 *   npx tsx validate.ts run --mode invented-policy --split validation
 *   npx tsx validate.ts run --mode invented-policy --split test      # exactly once
 *   npx tsx validate.ts correct --mode invented-policy --observed-pass-rate 0.82
 *
 * Labels: .eval/default/review-app/annotations.json (labels[modeId] = "pass" | "fail").
 * Graders: GRADERS exported from .eval/default/graders/graders.ts.
 * "Pass" means the failure mode was NOT present; TPR is agreement on passes,
 * TNR is agreement on fails. Shares .eval/default/validation/splits.json with validate.py.
 *
 * Part of eval-skills (Apache-2.0).
 */
import { groupedSplit } from './grouped-split.js';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

type Verdict = 'pass' | 'fail';
type Pair = [human: Verdict, grader: Verdict];
type TraceRecord = { trace_id: string; input?: unknown; output?: unknown; tags?: string[]; metadata?: Record<string, unknown>; steps?: { type?: string; name?: string; input?: unknown; output?: unknown }[] };

const OUT_DIR = '.eval/default/validation';
const SPLITS = `${OUT_DIR}/splits.json`;

function arg(name: string, fallback?: string): string | undefined {
  const i = process.argv.indexOf(name);
  return i > -1 ? process.argv[i + 1] : fallback;
}
const command = process.argv[2];
const mode = arg('--mode');
const force = process.argv.includes('--force');
const labelsPath = arg('--labels', '.eval/default/review-app/annotations.json')!;
const tracesPath = arg('--traces', '.eval/default/traces/traces.jsonl')!;
const gradersPath = arg('--graders', '.eval/default/graders/graders.ts')!;
const fail = (msg: string): never => {
  console.error(msg);
  process.exit(1);
};
if (!mode || !['split', 'run', 'correct'].includes(command ?? '')) fail('usage: validate.ts split|run|correct --mode <failure-mode-id> [...]');

const readJson = (p: string) => JSON.parse(readFileSync(p, 'utf8'));

function loadLabels(): Record<string, Verdict> {
  const annotations = readJson(labelsPath) as Record<string, { labels?: Record<string, string> }>;
  return Object.fromEntries(
    Object.entries(annotations)
      .filter(([, a]) => a.labels?.[mode!] === 'pass' || a.labels?.[mode!] === 'fail')
      .map(([id, a]) => [id, a.labels![mode!] as Verdict]),
  );
}

function loadTraces(): Map<string, TraceRecord> {
  const map = new Map<string, TraceRecord>();
  for (const line of readFileSync(tracesPath, 'utf8').split('\n')) {
    if (line.trim()) {
      const r = JSON.parse(line) as TraceRecord;
      map.set(String(r.trace_id), r);
    }
  }
  return map;
}

/** Turn a normalized trace record into the (case, result) a grader expects. */
export function traceToCaseResult(record: TraceRecord) {
  const steps = record.steps ?? [];
  const retrieval = steps
    .filter((s) => s.type === 'retriever')
    .flatMap((s) => (Array.isArray(s.output) ? s.output : [s.output]))
    .map((x) => (typeof x === 'string' ? x : JSON.stringify(x)));
  const tools = steps.filter((s) => s.type === 'tool').map((s) => ({ name: s.name ?? '', input: s.input, output: s.output }));
  return {
    testCase: { id: record.trace_id, input: record.input, tags: record.tags ?? [], metadata: record.metadata ?? {} },
    result: { output: record.output, retrieval_context: retrieval.length ? retrieval : undefined, tools_called: tools.length ? tools : undefined, trace_id: record.trace_id },
  };
}

function rates(pairs: Pair[]) {
  const count = (h: Verdict, g: Verdict) => pairs.filter(([a, b]) => a === h && b === g).length;
  const tp = count('pass', 'pass'), fn = count('pass', 'fail'), tn = count('fail', 'fail'), fp = count('fail', 'pass');
  return { tp, fn, tn, fp, tpr: tp + fn ? tp / (tp + fn) : null, tnr: tn + fp ? tn / (tn + fp) : null };
}

function roganGladen(pObs: number, tpr: number, tnr: number): number | null {
  const denom = tpr + tnr - 1;
  if (Math.abs(denom) < 1e-6) return null;
  return Math.min(1, Math.max(0, (pObs + tnr - 1) / denom));
}

function split() {
  const splits = existsSync(SPLITS) ? readJson(SPLITS) : {};
  if (splits[mode!] && !force) fail(`Splits for ${mode} already exist. Splits are fixed once drawn; pass --force only if the labels were redone.`);
  const labels = loadLabels();
  const traces = loadTraces();
  const out = groupedSplit(Object.keys(labels).map(id=>({id,group_id:(traces.get(id) as any)?.group_id || (traces.get(id) as any)?.thread_id || id})), [.15,.45,.4], Number(arg('--seed','7')));
  splits[mode!] = { ...out, drawn_at: new Date().toISOString(), test_runs: 0 };
  mkdirSync(OUT_DIR, { recursive: true });
  writeFileSync(SPLITS, JSON.stringify(splits, null, 2));
  const describe = (ids: string[]) => `${ids.filter((i) => labels[i] === 'pass').length} pass / ${ids.filter((i) => labels[i] === 'fail').length} fail`;
  console.log(`Splits for ${mode}: development: ${describe(out.development!)}; validation: ${describe(out.validation!)}; test: ${describe(out.test!)}`);
}

async function run() {
  const which = (arg('--split', 'validation') as 'validation' | 'test');
  const splits = readJson(SPLITS);
  if (!splits[mode!]) fail(`No splits for ${mode}; run split first.`);
  if (which === 'test') {
    if (splits[mode!].test_runs >= 1 && !force) fail('Test was already measured once. Iterate on validation; re-running test turns it into a validation set.');
    splits[mode!].test_runs += 1;
    writeFileSync(SPLITS, JSON.stringify(splits, null, 2));
  }
  const labels = loadLabels();
  const traces = loadTraces();
  const { GRADERS } = await import(pathToFileURL(resolve(gradersPath)).href);
  const grader = GRADERS[mode!];
  if (!grader) fail(`No grader named ${mode} in ${gradersPath}`);
  const ids: string[] = splits[mode!][which];
  const pairs: Pair[] = [];
  const disagreements: unknown[] = [];
  const errors: unknown[] = [];
  const missing = ids.filter((id) => !traces.has(id));
  const concurrency = Number(arg('--concurrency', '8'));
  const queue = ids.filter((id) => traces.has(id));
  await Promise.all(
    Array.from({ length: concurrency }, async () => {
      for (let id = queue.shift(); id; id = queue.shift()) {
        const { testCase, result } = traceToCaseResult(traces.get(id)!);
        try {
          const grade = await grader(testCase, result);
          if (typeof grade?.passed !== 'boolean') throw new Error(`grader returned ${JSON.stringify(grade)}`);
          const human = labels[id]!, judged: Verdict = grade.passed ? 'pass' : 'fail';
          pairs.push([human, judged]);
          if (human !== judged) {
            disagreements.push({ trace_id: id, human, grader: judged, reason: grade.reason, confidence: grade.confidence ?? null, kind: judged === 'pass' ? 'false pass (too lenient)' : 'false fail (too strict)' });
          }
        } catch (error) {
          errors.push({ trace_id: id, error: String(error) });
        }
      }
    }),
  );
  const r = rates(pairs);
  mkdirSync(OUT_DIR, { recursive: true });
  const outPath = `${OUT_DIR}/${mode}-${which}.json`;
  writeFileSync(outPath, JSON.stringify({ mode, split: which, n: pairs.length, ...r, errors, missing_traces: missing, disagreements, measured_at: new Date().toISOString() }, null, 2));
  const fmt = (x: number | null) => (x == null ? 'n/a' : x.toFixed(2));
  console.log(`${mode} on ${which} (n=${pairs.length}): TPR ${fmt(r.tpr)}, TNR ${fmt(r.tnr)} | ${disagreements.length} disagreements, ${errors.length} grader errors, ${missing.length} traces missing`);
  console.log(`Details: ${outPath}`);
}

function correct() {
  const pObs = Number(arg('--observed-pass-rate'));
  if (Number.isNaN(pObs)) fail('Pass --observed-pass-rate: the grader pass rate on unlabeled traffic.');
  const path = `${OUT_DIR}/${mode}-test.json`;
  if (!existsSync(path)) fail('Measure the test split first; the correction uses test TPR/TNR.');
  const report = readJson(path);
  if (report.tpr == null || report.tnr == null) fail('The test split needs both human passes and human fails.');
  const pairs: Pair[] = [
    ...Array<Pair>(report.tp).fill(['pass', 'pass']),
    ...Array<Pair>(report.fn).fill(['pass', 'fail']),
    ...Array<Pair>(report.tn).fill(['fail', 'fail']),
    ...Array<Pair>(report.fp).fill(['fail', 'pass']),
  ];
  const est = roganGladen(pObs, report.tpr, report.tnr);
  if (est == null) fail('TPR + TNR is about 1: the grader is no better than chance, so no correction is possible.');
  const estimates: number[] = [];
  for (let b = 0; b < 2000; b++) {
    const sample = pairs.map(() => pairs[Math.floor(Math.random() * pairs.length)]!);
    const r = rates(sample);
    if (r.tpr == null || r.tnr == null) continue;
    const e = roganGladen(pObs, r.tpr, r.tnr);
    if (e != null) estimates.push(e);
  }
  estimates.sort((a, b) => a - b);
  const ci = estimates.length >= 1000 ? `95% CI ${estimates[Math.floor(0.025 * estimates.length)]!.toFixed(2)}–${estimates[Math.floor(0.975 * estimates.length) - 1]!.toFixed(2)}` : 'CI unavailable (too few labels)';
  console.log(`Observed pass rate ${pObs.toFixed(2)} → corrected ${est!.toFixed(2)} (${ci}), using test TPR ${report.tpr.toFixed(2)} / TNR ${report.tnr.toFixed(2)} on ${pairs.length} labeled traces.`);
}

async function main() {
  if (command === 'split') split();
  else if (command === 'run') await run();
  else correct();
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
