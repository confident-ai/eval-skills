/**
 * Run the app over the dataset, grade every output, and report with confidence intervals.
 * TypeScript twin of run_evals.py for Node projects (run with `npx tsx`); same files, same format.
 *
 *   npx tsx run-evals.ts --variant baseline --reps 2
 *   npx tsx run-evals.ts --variant baseline --reps 2 --dry-run
 *   npx tsx run-evals.ts --variant v1 --reps 2 --compare baseline
 *   npx tsx run-evals.ts --variant v1 --ids .eval/default/runs/test_ids.json
 *   npx tsx run-evals.ts --variant v2 --ids .eval/default/runs/select_ids.json --compare baseline --compare-ids .eval/default/runs/validation_ids.json
 *
 * Reads .eval/default/dataset/goldens.jsonl, calls runCase() from .eval/default/scripts/app-adapter.ts,
 * applies every grader in GRADERS (.eval/default/graders/graders.ts), and writes
 * .eval/default/runs/<variant>/{results.jsonl, errors.jsonl, summary.json}.
 *
 * Rows carry a hash of their case and of the harness (adapter, graders, app code
 * in git); resume skips only matching rows and refuses to mix in stale ones.
 * Intervals are computed over cases, with repetitions averaged within a case.
 *
 * Part of eval-skills (Apache-2.0).
 */
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { appendFileSync, existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { basename, dirname, extname, join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

type Case = { id: string; tags?: string[]; input?: unknown; scenario?: unknown; [k: string]: unknown };
type Result = { output: unknown; model?: string; usage?: Record<string, number>; trace_id?: string; [k: string]: unknown };
type Grade = { passed: boolean; reason?: string; score?: number; confidence?: number | null };
type Row = { trace?: unknown; group_id?: string; case_id: string; rep: number; tags: string[]; input: unknown; output: unknown; grades: Record<string, Grade>; passed_all: boolean; latency_s: number; attempts: number; model?: string; usage?: Record<string, number>; trace_id?: string; case_hash?: string; harness_hash?: string; at: string };

function arg(name: string, fallback?: string) {
  const i = process.argv.indexOf(name);
  return i > -1 ? process.argv[i + 1] : fallback;
}
const variant = arg('--variant') ?? (console.error('--variant is required'), process.exit(1));
const reps = Number(arg('--reps', '1'));
const dataset = arg('--dataset', '.eval/default/dataset/goldens.jsonl')!;
const appPath = arg('--app', '.eval/default/scripts/app-adapter.ts')!;
const gradersPath = arg('--graders', '.eval/default/graders/graders.ts')!;
const outRoot = arg('--out', '.eval/default/runs')!;
const concurrency = Number(arg('--concurrency', '8'));
const timeoutMs = Number(arg('--timeout-s', '180')) * 1000;
const maxAttempts = Number(arg('--max-attempts', '4'));
const compareTo = arg('--compare');
const dryRun = process.argv.includes('--dry-run');
const discardStale = process.argv.includes('--discard-stale');

const readJsonl = <T>(path: string): T[] =>
  existsSync(path) ? readFileSync(path, 'utf8').split('\n').filter((l) => l.trim()).map((l) => JSON.parse(l) as T) : [];
const append = (path: string, row: unknown) => appendFileSync(path, JSON.stringify(row) + '\n');

class CaseTimeout extends Error {}
function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  let timer: NodeJS.Timeout;
  return Promise.race([
    promise.finally(() => clearTimeout(timer)),
    new Promise<T>((_, reject) => (timer = setTimeout(() => reject(new CaseTimeout(`exceeded ${ms / 1000}s`)), ms))),
  ]);
}

function classify(error: unknown): string {
  const text = `${(error as Error)?.name ?? ''} ${String(error)} ${(error as { status?: number })?.status ?? ''}`.toLowerCase();
  if (error instanceof CaseTimeout) return 'timeout';
  if (['ratelimit', 'rate_limit', 'overloaded', '429', '503', '529', 'apiconnection', 'temporarily'].some((h) => text.includes(h))) return 'rate-limit';
  if (['refus', 'content_filter', 'safety'].some((h) => text.includes(h))) return 'refusal';
  return 'harness';
}

function wilson(passes: number, n: number, z = 1.96): [number, number] {
  if (!n) return [0, 0];
  const p = passes / n, denom = 1 + (z * z) / n;
  const centre = (p + (z * z) / (2 * n)) / denom;
  const half = (z * Math.sqrt((p * (1 - p)) / n + (z * z) / (4 * n * n))) / denom;
  return [Math.max(0, centre - half), Math.min(1, centre + half)];
}

const sha = (data: string | Buffer) => createHash('sha256').update(data).digest('hex').slice(0, 16);

/** Stable JSON (sorted keys) so the same case always hashes the same. */
function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value && typeof value === 'object') {
    return `{${Object.keys(value).sort().map((k) => `${JSON.stringify(k)}:${canonical((value as Record<string, unknown>)[k])}`).join(',')}}`;
  }
  return JSON.stringify(value) ?? 'null';
}
const caseHash = (c: Case) => sha(canonical(c));

/** HEAD plus a hash of uncommitted changes outside .eval/default/ (eval files are hashed directly). */
function gitState(): string {
  try {
    const head = execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim();
    const diff = execFileSync('git', ['diff', 'HEAD', '--no-ext-diff', '--', '.', ':(exclude).eval'], { stdio: ['ignore', 'pipe', 'ignore'] });
    return `${head}:${sha(diff)}`;
  } catch {
    return 'no-git';
  }
}

/** Identifies the code that produced a row: adapter, graders module and its siblings, app code in git. */
function harnessHash(): string {
  const h = createHash('sha256');
  const paths = [appPath];
  if (gradersPath !== 'none') {
    const dir = dirname(gradersPath), ext = extname(gradersPath);
    paths.push(...readdirSync(dir).filter((f) => extname(f) === ext).sort().map((f) => join(dir, f)));
  }
  for (const p of paths) {
    h.update(basename(p));
    h.update(existsSync(p) ? readFileSync(p) : '');
  }
  h.update(canonical({reps,timeoutMs,maxAttempts,config:arg('--config') ? JSON.parse(readFileSync(arg('--config')!, 'utf8')) : null}));
  h.update(`only=${arg('--only') ?? ''}|app-version=${arg('--app-version') ?? gitState()}`);
  return h.digest('hex').slice(0, 16);
}

/** Average repetitions within each case, then put the interval over cases. */
function usageSummary(values: (Record<string, number | null> | undefined)[]) {
  return Object.fromEntries(['input_tokens','output_tokens'].map(k=>{const known=values.map(v=>v?.[k]).filter((v):v is number=>typeof v==='number' && Number.isFinite(v));return [k,known.length?known.reduce((a,b)=>a+b,0):null];}));
}
function caseLevel(rows: Row[], value: (r: Row) => boolean | undefined) {
  const byCase = new Map<string, number[]>();
  for (const r of rows) {
    const v = value(r);
    if (v !== undefined) byCase.set(r.group_id || r.case_id, [...(byCase.get(r.group_id || r.case_id) ?? []), Number(v)]);
  }
  const means = [...byCase.values()].map((v) => v.reduce((a, b) => a + b, 0) / v.length);
  if (!means.length) return { pass_rate: null, ci95: [null, null] as [number | null, number | null], n_cases: 0, n_runs: 0 };
  const p = means.reduce((a, b) => a + b, 0) / means.length;
  return { pass_rate: p, ci95: wilson(p * means.length, means.length), n_cases: means.length, n_runs: [...byCase.values()].reduce((a, v) => a + v.length, 0) };
}

async function main() {
  let cases = readJsonl<Case>(dataset);
  const idsFile = arg('--ids');
  if (idsFile) {
    const keep = new Set<string>(JSON.parse(readFileSync(idsFile, 'utf8')));
    cases = cases.filter((c) => keep.has(c.id));
  }
  const limit = arg('--limit');
  if (limit) cases = cases.slice(0, Number(limit));
  const outDir = `${outRoot}/${variant}`;
  const resultsPath = `${outDir}/results.jsonl`, errorsPath = `${outDir}/errors.jsonl`;
  const hashes = { case: new Map(cases.map((c) => [c.id, caseHash(c)])), harness: harnessHash() };
  const fresh = (r: Row) => hashes.case.get(r.case_id) === r.case_hash && r.harness_hash === hashes.harness;

  // Resume only from rows produced by these exact cases and this exact harness.
  const existing = readJsonl<Row>(resultsPath);
  const stale = existing.filter((r) => hashes.case.has(r.case_id) && !fresh(r));
  if (stale.length && !dryRun) {
    if (!discardStale) {
      console.error(`${stale.length} rows in ${resultsPath} came from a different case definition, app, or grader version, so resuming would mix old results into this run. Use a new --variant for the changed code, or pass --discard-stale to move them to stale.jsonl and re-run those slots.`);
      process.exit(1);
    }
    for (const r of stale) append(`${outDir}/stale.jsonl`, r);
    writeFileSync(resultsPath, existing.filter((r) => !stale.includes(r)).map((r) => JSON.stringify(r) + '\n').join(''));
  }
  const done = new Set(existing.filter((r) => fresh(r)).map((r) => `${r.case_id}#${r.rep}`));
  const todo = cases.flatMap((c) => Array.from({ length: reps }, (_, rep) => ({ c, rep }))).filter(({ c, rep }) => !done.has(`${c.id}#${rep}`));

  // --graders none collects outputs only (managed track: graders run on Confident AI).
  let graders: Record<string, (c: Case, r: Result) => Grade | Promise<Grade>> =
    gradersPath === 'none' ? {} : ((await import(pathToFileURL(resolve(gradersPath)).href)) as { GRADERS: typeof graders }).GRADERS;
  const only = arg('--only');
  if (only) graders = Object.fromEntries(Object.entries(graders).filter(([k]) => only.split(',').includes(k)));
  console.log(`Scope: ${cases.length} cases × ${reps} reps = ${cases.length * reps} slots (${done.size} already done, ${todo.length} to run); graders: ${Object.keys(graders).join(', ') || 'none'}; concurrency ${concurrency}; per-call soft timeout ${timeoutMs / 1000}s → ${outDir}${stale.length ? `; ${stale.length} stale rows would block a resume` : ''}`);
  if (dryRun) return;

  mkdirSync(outDir, { recursive: true });
  const { runCase } = (await import(pathToFileURL(resolve(appPath)).href)) as { runCase: (c: Case) => Result | Promise<Result> };
  let finished = 0;
  let lastLog = Date.now();

  async function runOne(c: Case, rep: number) {
    const started = performance.now();
    let result: Result | undefined;
    let attempts = 0;
    const ledgerPath = join(outDir,'attempts.jsonl');
    const recordCall = (stage:string,status:string,value:any,grader?:string) => append(ledgerPath,{case_id:c.id,rep,attempt:readJsonl<any>(ledgerPath).filter(a=>a.case_id===c.id&&a.rep===rep).length+1,stage,status,grader,usage:value?.usage??null,cost_usd:value?.cost_usd??null});
    while (!result) {
      attempts++;
      try {
        result = await withTimeout(Promise.resolve().then(() => runCase(Object.fromEntries(['id','input','scenario','attachments'].filter(k=>k in c).map(k=>[k,c[k]])) as Case)), timeoutMs);
        recordCall("app","ok",result);
      } catch (error) {
        const kind = classify(error);
        recordCall("app",kind,error);
        append(errorsPath, { case_id: c.id, rep, stage: 'app', failure_class: kind, attempt: attempts, error: String(error).slice(0, 2000), at: new Date().toISOString() });
        if (kind === 'rate-limit' && attempts < maxAttempts) {
          await new Promise((r) => setTimeout(r, Math.min(60_000, 1000 * 2 ** attempts) * (0.5 + Math.random())));
          continue;
        }
        return;
      }
    }
    const latency = (performance.now() - started) / 1000;
    const grades: Record<string, Grade> = {};
    let graderFailed = false;
    for (const [modeId, grader] of Object.entries(graders)) {
      try {
        const grade = await withTimeout(Promise.resolve().then(() => grader(c, result!)), timeoutMs);
        if (typeof grade?.passed !== 'boolean') throw new Error(`grader returned ${JSON.stringify(grade)}`);
        grades[modeId] = grade;
        recordCall("judge","ok",grade,modeId);
      } catch (error) {
        graderFailed = true;
        recordCall("judge",classify(error),error,modeId);
        append(errorsPath, { case_id: c.id, rep, stage: 'grader', grader: modeId, failure_class: classify(error), error: String(error).slice(0, 2000), at: new Date().toISOString() });
      }
    }
    if (graderFailed) return; // leave the slot empty so a resume re-runs it
    append(resultsPath, {
      case_id: c.id, group_id: String(c.group_id || c.id), rep, tags: c.tags ?? [], input: c.input ?? c.scenario, output: result.output,
      ...Object.fromEntries(['retrieval_context', 'tools_called', 'turns'].filter((k) => result![k] != null).map((k) => [k, result![k]])),
      grades,
      passed_all: Object.values(grades).every((g) => g.passed), latency_s: Number(latency.toFixed(3)), attempts,
      trace: result.trace, model: result.model, usage: result.usage, trace_id: result.trace_id,
      case_hash: hashes.case.get(c.id), harness_hash: hashes.harness, at: new Date().toISOString(),
    } satisfies Row);
  }

  const queue = [...todo];
  await Promise.all(
    Array.from({ length: concurrency }, async () => {
      for (let item = queue.shift(); item; item = queue.shift()) {
        await runOne(item.c, item.rep);
        finished++;
        if (Date.now() - lastLog > 15_000 || finished === todo.length) {
          console.log(`  ${finished}/${todo.length} done`);
          lastLog = Date.now();
        }
      }
    }),
  );

  const rows = readJsonl<Row>(resultsPath).filter(fresh);
  if (!Object.keys(graders).length) {
    console.log(`\nCollected outputs for ${rows.length} of ${cases.length * reps} slots in ${resultsPath}. Upload them for grading with upload-results.mjs.`);
    return;
  }
  const errors = readJsonl<{ stage: string }>(errorsPath);
  const modes = [...new Set(rows.flatMap((r) => Object.keys(r.grades)))].sort();
  const perMode = Object.fromEntries(modes.map((m) => [m, caseLevel(rows, (r) => r.grades[m]?.passed)]));
  const overall = caseLevel(rows, (r) => r.passed_all);
  const byTag = new Map<string, Row[]>();
  for (const r of rows) byTag.set(r.tags[0] ?? 'untagged', [...(byTag.get(r.tags[0] ?? 'untagged') ?? []), r]);
  const perTag = Object.fromEntries([...byTag].map(([t, rs]) => [t, caseLevel(rs, (r) => r.passed_all)]));
  const lat = rows.map((r) => r.latency_s).sort((a, b) => a - b);
  const pct = (q: number) => (lat.length ? lat[Math.min(lat.length - 1, Math.floor(q * lat.length))] : null);
  const summary: Record<string, unknown> = {
    cases: cases.length, reps, rows: rows.length,
    pass_rate_all: overall.pass_rate, ci95_all: overall.ci95, cases_scored: overall.n_cases,
    interval_method: 'Wilson over cases; repetitions averaged within each case',
    noise_floor_approx: overall.n_cases ? 1 / Math.sqrt(overall.n_cases) : null,
    per_failure_mode: perMode, per_tag: perTag, latency_s: { p50: pct(0.5), p95: pct(0.95) },
    usage_totals: usageSummary(rows.map(r=>r.usage)),
    usage_complete: rows.length>0 && rows.every(r=>r.usage?.input_tokens!=null&&r.usage?.output_tokens!=null),
    usage_by_stage: Object.fromEntries(['app','judge'].map(stage=>{const calls=readJsonl<any>(join(outDir,'attempts.jsonl')).filter(a=>a.stage===stage);return [stage,{measured_tokens:usageSummary(calls.map(a=>a.usage)),calls:calls.length,missing_usage_calls:calls.filter(a=>a.usage==null).length}];})),
    models_seen: [...new Set(rows.map((r) => r.model).filter(Boolean))],
    errors: { app: errors.filter((e) => e.stage === 'app').length, grader: errors.filter((e) => e.stage === 'grader').length },
    missing_slots: cases.length * reps - rows.length,
  };

  if (compareTo) {
    const perCase = (rs: Row[]) => {
      const m = new Map<string, number[]>();
      for (const r of rs) m.set(r.group_id || r.case_id, [...(m.get(r.group_id || r.case_id) ?? []), Number(r.passed_all)]);
      return new Map([...m].map(([k, v]) => [k, v.reduce((a, b) => a + b, 0) / v.length]));
    };
    const compareIds = arg('--compare-ids'); // decide on a subset (e.g. validation) even when the run covers more
    const keep = compareIds ? new Set<string>(JSON.parse(readFileSync(compareIds, 'utf8'))) : null;
    const inScope = (r: Row) => !keep || keep.has(r.case_id);
    const a = perCase(rows.filter(inScope)), b = perCase(readJsonl<Row>(`${outRoot}/${compareTo}/results.jsonl`).filter(inScope));
    const shared = [...a.keys()].filter((k) => b.has(k)).sort();
    const diffs = shared.map((k) => a.get(k)! - b.get(k)!);
    if (diffs.length) {
      const boots = Array.from({ length: 2000 }, () => diffs.reduce((s) => s + diffs[Math.floor(Math.random() * diffs.length)]!, 0) / diffs.length).sort((x, y) => x - y);
      const [lo, hi] = [boots[50]!, boots[1949]!];
      summary.compare = {
        baseline: compareTo, ids: compareIds ?? null, n_cases: shared.length, delta: diffs.reduce((s, d) => s + d, 0) / diffs.length, ci95: [lo, hi],
        verdict: lo > 0 ? 'better' : hi < 0 ? 'worse' : 'within noise',
        flipped_to_pass: shared.filter((k) => a.get(k)! > b.get(k)!), flipped_to_fail: shared.filter((k) => a.get(k)! < b.get(k)!),
      };
    }
  }
  writeFileSync(`${outDir}/summary.json`, JSON.stringify(summary, null, 2));

  const fmt = (x: unknown) => (typeof x === 'number' ? x.toFixed(2) : 'n/a');
  const [lo, hi] = summary.ci95_all as [number, number];
  console.log(`\n${variant}: all graders pass ${fmt(summary.pass_rate_all)} over ${overall.n_cases} cases (${rows.length} runs; 95% CI over cases ${lo.toFixed(2)}–${hi.toFixed(2)}; noise ≈ ±${fmt(summary.noise_floor_approx)})`);
  for (const [m, s] of Object.entries(perMode)) console.log(`  ${m}: ${fmt(s.pass_rate)} (95% CI ${fmt(s.ci95[0])}–${fmt(s.ci95[1])}, ${s.n_cases} cases)`);
  if (summary.missing_slots) console.log(`  ${summary.missing_slots} slots missing: see errors.jsonl; re-run the same command to retry them.`);
  const c = summary.compare as { delta: number; ci95: [number, number]; verdict: string } | undefined;
  if (c) console.log(`  vs ${compareTo}: Δ ${c.delta >= 0 ? '+' : ''}${c.delta.toFixed(2)} (95% CI ${c.ci95[0].toFixed(2)} to ${c.ci95[1].toFixed(2)}) → ${c.verdict}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
