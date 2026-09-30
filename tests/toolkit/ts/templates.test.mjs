// Runtime tests for the Node/TypeScript templates. Run from tests/ts after `npm ci`:
//   npm run typecheck && npm test
import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const skills = join(here, '..', '..', '..', 'skills');
const tsx = join(here, 'node_modules', '.bin', 'tsx');
const t = (...parts) => join(skills, ...parts);

function project() {
  const dir = mkdtempSync(join(tmpdir(), 'eval-skills-'));
  mkdirSync(join(dir, '.eval/default'), { recursive: true });
  // Resolve packages from this folder, as a user's project resolves its own.
  spawnSync('ln', ['-s', join(here, 'node_modules'), join(dir, 'node_modules')]);
  writeFileSync(join(dir, 'package.json'), JSON.stringify({ type: 'module' }));
  return dir;
}
const run = (cmd, args, cwd, env = {}) => spawnSync(cmd, args, { cwd, encoding: 'utf8', env: { ...process.env, ...env } });
const writeJsonl = (path, rows) => {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, rows.map((r) => JSON.stringify(r)).join('\n') + '\n');
};
const readJsonl = (path) => readFileSync(path, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l));

test('local exporter + normalizer: a traced call becomes a review record', () => {
  const dir = project();
  for (const f of ['eval-tracing.ts', 'local-exporter.ts']) copyFileSync(t('eval-trace', 'templates', 'typescript', f), join(dir, f));
  writeFileSync(
    join(dir, 'app.ts'),
    `import { span, updateTrace, shutdown } from 'confident-trace';
import { setupTracing } from './eval-tracing.js';
setupTracing('demo', { instrumentations: [] });
const lookupOrder = span({ name: 'lookup_order', type: 'tool' }, async (id: string) => ({ status: 'delivered', id }));
const answer = span({ name: 'answer', type: 'agent' }, async (q: string) => {
  updateTrace({ input: q, threadId: 'conv-1', tags: ['orders'] });
  const r = await lookupOrder('A17');
  const out = 'Order A17 is ' + r.status + '.';
  updateTrace({ output: out });
  return out;
});
await answer('Where is order A17?');
await shutdown();`,
  );
  const res = run(tsx, ['app.ts'], dir, { EVAL_SKILLS_TRACE_MODE: 'local', CONFIDENT_API_KEY: '' });
  assert.equal(res.status, 0, res.stderr);
  const norm = run('node', [t('eval-trace', 'templates', 'typescript', 'normalize-traces.mjs')], dir);
  assert.equal(norm.status, 0, norm.stderr);
  const [record] = readJsonl(join(dir, '.eval/default/traces/traces.jsonl'));
  assert.equal(record.input, 'Where is order A17?');
  assert.equal(record.output, 'Order A17 is delivered.');
  assert.equal(record.thread_id, 'conv-1');
  assert.deepEqual(record.steps.map((s) => [s.type, s.name]), [['tool', 'lookup_order']]);
  const replay = run('node', [t('eval-trace', 'templates', 'typescript', 'replay-spans.mjs'), '--dry-run'], dir);
  assert.match(replay.stdout, /Would send 1 export batches/);
});

test('review server (Node): host check, token, validation', async () => {
  const dir = project();
  writeJsonl(join(dir, '.eval/default/traces/traces.jsonl'), [{ trace_id: 't0', input: '<script>x</script>', output: 'ok' }]);
  const port = 20000 + Math.floor(Math.random() * 20000);
  const server = spawn('node', [t('eval-discover', 'templates', 'review-app', 'server.mjs'), '--port', String(port)], { cwd: dir });
  try {
    await new Promise((resolve) => server.stdout.once('data', resolve));
    const base = `http://127.0.0.1:${port}`;
    const page = await (await fetch(`${base}/`)).text();
    const token = page.match(/name="session-token" content="([^"]+)"/)[1];
    assert.ok(token.length > 20);
    const post = (body, headers) => fetch(`${base}/api/annotations`, { method: 'POST', headers: { 'Content-Type': 'application/json', ...headers }, body: JSON.stringify(body) });
    assert.equal((await post({ trace_id: 't0', verdict: 'fail' }, {})).status, 403);
    assert.equal((await post({ trace_id: 't0', verdict: 'maybe' }, { 'X-Session-Token': token })).status, 400);
    assert.equal((await post({ revision:0, reviewed_by:'fixture-reviewer', trace_id: 't0', verdict: 'fail', note: 'x' }, { 'X-Session-Token': token })).status, 200);
    const saved = JSON.parse(readFileSync(join(dir, '.eval/default/review-app/annotations.json'), 'utf8'));
    assert.equal(saved.t0.verdict, 'fail');
  } finally {
    server.kill();
  }
});

test('runner (TS): errors are not scored, resume is idempotent, report escapes', () => {
  const dir = project();
  writeJsonl(join(dir, '.eval/default/dataset/goldens.jsonl'), Array.from({ length: 12 }, (_, i) => ({ id: `c${String(i).padStart(2, '0')}`, input: `q${i}`, tags: ['t'] })));
  mkdirSync(join(dir, '.eval/default/scripts'), { recursive: true });
  mkdirSync(join(dir, '.eval/default/graders'), { recursive: true });
  writeFileSync(
    join(dir, '.eval/default/scripts/app-adapter.ts'),
    `export async function runCase(c: { id: string }) {
  const i = Number(c.id.slice(1));
  if (i === 7) await new Promise((r) => setTimeout(r, 3000));
  if (i === 11) throw new Error('boom');
  return { output: i % 4 ? '<b>30 days</b>' : '45 days', model: 'demo' };
}`,
  );
  writeFileSync(join(dir, '.eval/default/graders/graders.ts'), `export const GRADERS = { window: (_c: unknown, r: { output: unknown }) => ({ passed: String(r.output).includes('30 days'), reason: 'x' }) };`);
  copyFileSync(t('eval-run', 'templates', 'run-evals.ts'), join(dir, '.eval/default/scripts/run-evals.ts'));
  const args = ['.eval/default/scripts/run-evals.ts', '--variant', 'baseline', '--reps', '2', '--timeout-s', '1'];
  const first = run(tsx, args, dir);
  assert.equal(first.status, 0, first.stderr);
  const rows = readJsonl(join(dir, '.eval/default/runs/baseline/results.jsonl'));
  assert.equal(rows.length, 20);
  assert.ok(!rows.some((r) => ['c07', 'c11'].includes(r.case_id)));
  const classes = new Set(readJsonl(join(dir, '.eval/default/runs/baseline/errors.jsonl')).map((e) => e.failure_class));
  assert.ok(classes.has('timeout') && classes.has('harness'));
  run(tsx, args, dir);
  const again = readJsonl(join(dir, '.eval/default/runs/baseline/results.jsonl'));
  assert.equal(new Set(again.map((r) => `${r.case_id}#${r.rep}`)).size, again.length);
  assert.ok(again.every((r) => r.case_hash && r.harness_hash));
  const summary = JSON.parse(readFileSync(join(dir, '.eval/default/runs/baseline/summary.json'), 'utf8'));
  assert.equal(summary.cases_scored, 10); // intervals are over cases, not the 20 runs
  const report = run('node', [t('eval-run', 'templates', 'report.mjs')], dir);
  assert.equal(report.status, 0, report.stderr);
  const html = readFileSync(join(dir, '.eval/default/runs/report.html'), 'utf8');
  assert.ok(!html.includes('<b>30 days</b>') && html.includes('&lt;b&gt;30 days&lt;/b&gt;'));
  // A changed case with the same id must not be silently reused on resume.
  const cases = readJsonl(join(dir, '.eval/default/dataset/goldens.jsonl'));
  cases[0].input = 'a different question';
  writeJsonl(join(dir, '.eval/default/dataset/goldens.jsonl'), cases);
  const blocked = run(tsx, args, dir);
  assert.notEqual(blocked.status, 0);
  assert.match(blocked.stderr, /different case definition/);
  assert.equal(run(tsx, [...args, '--discard-stale'], dir).status, 0);
  assert.ok(existsSync(join(dir, '.eval/default/runs/baseline/stale.jsonl')));
  const up = run('node', [t('eval-run', 'templates', 'upload-results.mjs'), '--variant', 'baseline', '--collection', 'core', '--dry-run'], dir);
  assert.match(up.stdout, /Would upload 20 test cases/);
});

test('validate (TS): fixed splits, test measured once', () => {
  const dir = project();
  const traces = [];
  const annotations = {};
  for (let i = 0; i < 40; i++) {
    const bad = i % 3 === 0;
    traces.push({ trace_id: `t${i}`, input: 'q', output: bad ? '45 days' : '30 days' });
    annotations[`t${i}`] = { labels: { window: bad ? 'fail' : 'pass' } };
  }
  writeJsonl(join(dir, '.eval/default/traces/traces.jsonl'), traces);
  mkdirSync(join(dir, '.eval/default/review-app'), { recursive: true });
  writeFileSync(join(dir, '.eval/default/review-app/annotations.json'), JSON.stringify(annotations));
  mkdirSync(join(dir, '.eval/default/graders'), { recursive: true });
  writeFileSync(join(dir, '.eval/default/graders/graders.ts'), `export const GRADERS = { window: (_c: unknown, r: { output: unknown }) => ({ passed: String(r.output).includes('30 days'), reason: 'x' }) };`);
  copyFileSync(t('eval-grade', 'templates', 'validate.ts'), join(dir, 'validate.ts'));
  copyFileSync(t('eval-grade', 'templates', 'grouped-split.ts'), join(dir, 'grouped-split.ts'));
  assert.equal(run(tsx, ['validate.ts', 'split', '--mode', 'window'], dir).status, 0);
  assert.notEqual(run(tsx, ['validate.ts', 'split', '--mode', 'window'], dir).status, 0);
  const validation = run(tsx, ['validate.ts', 'run', '--mode', 'window', '--split', 'validation'], dir);
  assert.match(validation.stdout, /TPR 1\.00, TNR 1\.00/);
  assert.equal(run(tsx, ['validate.ts', 'run', '--mode', 'window', '--split', 'test'], dir).status, 0);
  assert.notEqual(run(tsx, ['validate.ts', 'run', '--mode', 'window', '--split', 'test'], dir).status, 0);
  assert.ok(existsSync(join(dir, '.eval/default/validation/window-test.json')));
});

test('review server (Node): revisions, uncertainty, separate taxonomy approval and export', async () => {
  const dir=project();writeJsonl(join(dir,'.eval/default/traces/traces.jsonl'),[{trace_id:'t0',case_id:'c0',input:'q',output:'a'}]);
  const port=18866;const server=spawn('node',[t('eval-discover','templates','review-app','server.mjs'),'--port',String(port)],{cwd:dir});
  try {
    await new Promise((resolve,reject)=>{server.stdout.once('data',resolve);server.once('error',reject);server.once('exit',code=>{if(code)reject(new Error('server exit '+code));});});
    const base=`http://127.0.0.1:${port}`;const html=await(await fetch(base)).text();const token=html.match(/name="session-token" content="([^"]+)"/)[1];
    const post=(path,body)=>fetch(base+path,{method:'POST',headers:{'Content-Type':'application/json','X-Session-Token':token},body:JSON.stringify(body)});
    const body={trace_id:'t0',revision:0,reviewed_by:'fixture-human',verdict:'uncertain',note:'ambiguous',labels:{x:'uncertain'}};
    const saved=await(await post('/api/annotations',body)).json();assert.equal(saved.revision,1);
    assert.equal((await post('/api/annotations',body)).status,409);
    const proposed={revision:0,reviewed_by:'fixture-human',modes:[{id:'x',definition:'Wrong fact',status:'confirmed'}],assignments:[{id:'a',annotation_id:saved.id,case_id:'c0',trace_id:'t0',mode_id:'x',origin:'agent',status:'suggested'}]};
    assert.equal((await post('/api/taxonomy',proposed)).status,200);
    const exported=await(await fetch(base+'/api/export')).json();assert.equal(exported.taxonomy.assignments[0].status,'suggested');assert.equal(exported.taxonomy.history.length,1);
  } finally {server.kill();}
});


test('runner (TS): app projection, partial usage, configuration resume and portable export', () => {
  const dir=project();
  writeJsonl(join(dir,'.eval/default/dataset/goldens.jsonl'),[{id:'c',group_id:'g',input:'q',expected:'SECRET',source:{kind:'synthetic'}}]);
  mkdirSync(join(dir,'.eval/default/scripts'),{recursive:true});mkdirSync(join(dir,'.eval/default/graders'),{recursive:true});
  writeFileSync(join(dir,'.eval/default/scripts/app-adapter.ts'),`export async function runCase(c:any){if('expected' in c || 'source' in c)throw new Error('reference leaked');return {output:'answer',usage:{input_tokens:3}};}`);
  writeFileSync(join(dir,'.eval/default/graders/graders.ts'),`export const GRADERS={check:(c:any,r:any)=>{if(c.expected!=='SECRET')throw new Error('missing reference');return {passed:true,reason:'ok',usage:{output_tokens:2}};}};`);
  copyFileSync(t('eval-run','templates','run-evals.ts'),join(dir,'.eval/default/scripts/run-evals.ts'));
  writeFileSync(join(dir,'config.json'),JSON.stringify({model:'fixture-a'}));
  const args=['.eval/default/scripts/run-evals.ts','--variant','baseline','--config','config.json'];
  const result=run(tsx,args,dir);assert.equal(result.status,0,result.stderr);
  const summary=JSON.parse(readFileSync(join(dir,'.eval/default/runs/baseline/summary.json'),'utf8'));
  assert.deepEqual(summary.usage_totals,{input_tokens:3,output_tokens:null});assert.equal(summary.usage_complete,false);
  assert.equal(summary.usage_by_stage.judge.measured_tokens.output_tokens,2);
  assert.deepEqual(readJsonl(join(dir,'.eval/default/runs/baseline/attempts.jsonl')).map(a=>a.stage),['app','judge']);
  const py=process.env.PYTHON || 'python3';
  const exported=run(py,[t('eval-run','templates','export_bundle.py'),'--variant','baseline','--output',join(dir,'portable')],dir);assert.equal(exported.status,0,exported.stderr);
  const valid=run(py,[t('eval-run','scripts','artifacts.py'),'validate',join(dir,'portable')],dir);assert.equal(valid.status,0,valid.stderr);
  writeFileSync(join(dir,'config.json'),JSON.stringify({model:'fixture-b'}));assert.notEqual(run(tsx,args,dir).status,0);
});

test('grouped split: Python and TypeScript use identical case partitions', () => {
  const dir=project();const records=Array.from({length:36},(_,i)=>({id:'c'+i,group_id:'g'+Math.floor(i/3)}));writeFileSync(join(dir,'records.json'),JSON.stringify(records));
  copyFileSync(t('eval-grade','templates','grouped-split.ts'),join(dir,'grouped-split.ts'));
  writeFileSync(join(dir,'check.ts'),`import {groupedSplit} from './grouped-split.ts';import {readFileSync} from 'node:fs';console.log(JSON.stringify(groupedSplit(JSON.parse(readFileSync('records.json','utf8')))));`);
  const ts=run(tsx,['check.ts'],dir);assert.equal(ts.status,0,ts.stderr);
  const py=run(process.env.PYTHON || 'python3',['-c',`import sys,json;sys.path.insert(0,${JSON.stringify(t('eval-grade','templates'))});from grouped_split import grouped_split;print(json.dumps(grouped_split(json.load(open('records.json')))))`],dir);assert.equal(py.status,0,py.stderr);
  assert.deepEqual(JSON.parse(ts.stdout),JSON.parse(py.stdout));
});
