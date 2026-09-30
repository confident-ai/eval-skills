#!/usr/bin/env node
/**
 * Local trace review server for eval-skills. Node standard library only (Node 18+).
 *
 *   node server.mjs --traces .eval/default/traces/traces.jsonl --dir .eval/default/review-app [--port 8765] [--mode review|label]
 *
 * Same API and files as server.py:
 *   samples.json         trace ids to review, in order (written by the agent; all traces if absent)
 *   annotations.json     {trace_id: {verdict, note, labels, updated_at}} (written by this server)
 *   failure_modes.json   [{id, definition, count, examples}] (written by the agent, shown read-only)
 *
 * Security: binds to 127.0.0.1 only, rejects requests whose Host header isn't
 * this server, requires a per-session token on every write, and sends a strict
 * Content-Security-Policy. Trace content is untrusted; the app renders it as text.
 *
 * Part of eval-skills (Apache-2.0).
 */
import { randomBytes, timingSafeEqual } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, renameSync, statSync, writeFileSync } from 'node:fs';
import { createServer } from 'node:http';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

function arg(name, fallback) {
  const i = process.argv.indexOf(name);
  return i > -1 ? process.argv[i + 1] : fallback;
}

const tracesPath = arg('--traces', '.eval/default/traces/traces.jsonl');
const dir = arg('--dir', '.eval/default/review-app');
const port = Number(arg('--port', '8765'));
const mode = arg('--mode', 'review');
const staticDir = arg('--static', dirname(fileURLToPath(import.meta.url)));
if (!['review', 'label'].includes(mode)) throw new Error('--mode must be review or label');

const STATIC = {
  '/': ['index.html', 'text/html; charset=utf-8'],
  '/app.js': ['app.js', 'text/javascript; charset=utf-8'],
  '/app.css': ['app.css', 'text/css; charset=utf-8'],
};
const CSP =
  "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; " +
  "img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'";
const MAX_BODY = 1_000_000;
const token = randomBytes(24).toString('base64url');
const allowedHosts = new Set([`127.0.0.1:${port}`, `localhost:${port}`]);
const annotationsPath = join(dir, 'annotations.json');
const samplesPath = join(dir, 'samples.json');
const modesPath = join(dir, 'failure_modes.json');
const taxonomyPath = join(dir, 'taxonomy.json');
const conflict = msg => Object.assign(new Error(msg), {status:409});
const taxonomy = () => readJson(taxonomyPath, {revision:0,modes:readJson(modesPath,[]),assignments:[],history:[]});
mkdirSync(dir, { recursive: true });

const readJson = (path, fallback) => {
  try {
    return JSON.parse(readFileSync(path, 'utf8'));
  } catch {
    return fallback;
  }
};
const mtime = (path) => (existsSync(path) ? statSync(path).mtimeMs / 1000 : 0);

function writeJsonAtomic(path, data) {
  const tmp = join(dirname(path), `.${Date.now()}.${process.pid}.tmp`);
  writeFileSync(tmp, JSON.stringify(data, null, 2));
  renameSync(tmp, path);
}

function traces() {
  const records = new Map();
  if (existsSync(tracesPath)) {
    for (const line of readFileSync(tracesPath, 'utf8').split('\n')) {
      if (!line.trim()) continue;
      const record = JSON.parse(line);
      records.set(String(record.trace_id), record);
    }
  }
  const sample = readJson(samplesPath, null);
  if (Array.isArray(sample)) return sample.map(String).filter((id) => records.has(id)).map((id) => records.get(id));
  return [...records.values()];
}

const meta = () => ({ mode, version: [mtime(tracesPath), mtime(samplesPath), mtime(modesPath), mtime(taxonomyPath)] });

function annotate(payload) {
  const { trace_id: traceId, verdict = null, note = '', labels = {} } = payload ?? {};
  if (typeof traceId !== 'string' || !traceId) throw new Error('trace_id is required');
  if (![null, 'pass', 'fail', 'defer', 'uncertain'].includes(verdict)) throw new Error('verdict must be pass, fail, defer, or null');
  if (typeof note !== 'string' || note.length > 20_000) throw new Error('note must be a string under 20k characters');
  if (typeof labels !== 'object' || Array.isArray(labels) || Object.values(labels).some((v) => ![null, 'pass', 'fail', 'uncertain'].includes(v))) {
    throw new Error('labels must map failure-mode ids to pass, fail, or null');
  }
  if (!traces().some(t => t.trace_id === traceId)) throw new Error('unknown trace');
  if (typeof payload.reviewed_by !== 'string' || !payload.reviewed_by.trim()) throw new Error('reviewed_by is required');
  const annotations = readJson(annotationsPath, {});
  const current = annotations[traceId] || {};
  if (payload.revision !== (current.revision || 0)) throw conflict('Stale annotation; reload before saving');
  annotations[traceId] = {
    id: current.id || 'note:' + traceId,
    case_id: traces().find(t => t.trace_id === traceId)?.case_id || traceId,
    origin: current.origin || 'human',
    reviewed_by: payload.reviewed_by,
    revision: (current.revision || 0) + 1,
    verdict,
    note,
    labels: Object.fromEntries(Object.entries(labels).filter(([, v]) => v != null)),
    updated_at: new Date().toISOString(),
  };
  writeJsonAtomic(annotationsPath, annotations);
  return annotations[traceId];
}

function saveTaxonomy(payload) {
  const current = taxonomy();
  if (payload.revision !== current.revision) throw conflict('Stale taxonomy; reload before saving');
  const {modes, assignments, reviewed_by: reviewer} = payload;
  if (typeof reviewer !== 'string' || !reviewer.trim()) throw new Error('reviewed_by is required');
  if (!Array.isArray(modes) || !Array.isArray(assignments)) throw new Error('modes and assignments must be lists');
  const ids = new Set();
  for (const m of modes) {
    if (!m || typeof m.id !== 'string' || !m.id || ids.has(m.id)) throw new Error('unique mode IDs required');
    ids.add(m.id);
    if (typeof m.definition !== 'string' || !m.definition.trim()) throw new Error('mode definition required');
    if (!['proposed','confirmed','retired'].includes(m.status || 'proposed')) throw new Error('invalid mode status');
  }
  const notes = new Map(Object.entries(readJson(annotationsPath,{})).map(([k,v]) => [v.id || 'note:'+k,[k,v]]));
  const seen = new Set();
  for (const a of assignments) {
    if (!a || !a.id || seen.has(a.id)) throw new Error('unique assignment IDs required');
    seen.add(a.id);
    const note = notes.get(a.annotation_id);
    if (!note || a.trace_id !== note[0] || a.case_id !== (note[1].case_id || note[0])) throw new Error('assignment evidence mismatch');
    if (!['suggested','confirmed','rejected','uncertain'].includes(a.status)) throw new Error('invalid assignment status');
    if (!ids.has(a.mode_id) && !(a.mode_id === null && a.status === 'uncertain')) throw new Error('unknown mode');
  }
  const now = new Date().toISOString();
  for (const [key,records] of [['modes',modes],['assignments',assignments]]) {
    const old = new Map(current[key].map(x => [x.id,x]));
    for (const item of records) if (item.status === 'confirmed') {
      const prior = old.get(item.id) || {};
      const changed = ['definition','mode_id','annotation_id'].some(k => item[k] !== prior[k]);
      item.reviewed_by = changed || prior.status !== 'confirmed' ? reviewer : prior.reviewed_by || reviewer;
      item.reviewed_at = changed || prior.status !== 'confirmed' ? now : prior.reviewed_at || now;
    }
  }
  const value = {revision:current.revision+1,modes,assignments,history:[...(current.history||[]),{revision:current.revision,modes:current.modes,assignments:current.assignments,action:payload.action||'edit',reviewed_by:reviewer,at:now}]};
  writeJsonAtomic(taxonomyPath,value); return value;
}

function send(res, status, body, contentType) {
  res.writeHead(status, {
    'Content-Type': contentType,
    'Content-Length': Buffer.byteLength(body),
    'Content-Security-Policy': CSP,
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'no-referrer',
    'Cache-Control': 'no-store',
  });
  res.end(body);
}
const json = (res, status, data) => send(res, status, JSON.stringify(data), 'application/json');

function tokenOk(header) {
  const a = Buffer.from(String(header ?? ''));
  const b = Buffer.from(token);
  return a.length === b.length && timingSafeEqual(a, b);
}

const server = createServer((req, res) => {
  if (!allowedHosts.has(req.headers.host ?? '')) return json(res, 403, { error: 'unexpected Host header' });
  const path = (req.url ?? '/').split('?')[0];

  if (req.method === 'GET') {
    if (STATIC[path]) {
      const [name, type] = STATIC[path];
      let body = readFileSync(join(staticDir, name), 'utf8');
      if (name === 'index.html') body = body.replace('__SESSION_TOKEN__', token);
      return send(res, 200, body, type);
    }
    if (path === '/api/data' || path === '/api/export') {
      return json(res, 200, { ...meta(), traces: traces(), annotations: readJson(annotationsPath, {}), failure_modes: taxonomy().modes, taxonomy: taxonomy() });
    }
    if (path === '/api/meta') return json(res, 200, meta());
    return json(res, 404, { error: 'not found' });
  }

  if (req.method === 'POST') {
    if (!tokenOk(req.headers['x-session-token'])) return json(res, 403, { error: 'missing or wrong session token' });
    if (!['/api/annotations','/api/taxonomy'].includes(path)) return json(res, 404, { error: 'not found' });
    if (!String(req.headers['content-type'] ?? '').startsWith('application/json')) {
      return json(res, 415, { error: 'send application/json' });
    }
    const chunks = [];
    let size = 0;
    req.on('data', (chunk) => {
      size += chunk.length;
      if (size > MAX_BODY) req.destroy();
      else chunks.push(chunk);
    });
    req.on('end', () => {
      try {
        json(res, 200, (path === '/api/annotations' ? annotate : saveTaxonomy)(JSON.parse(Buffer.concat(chunks).toString('utf8'))));
      } catch (error) {
        json(res, error.status || 400, { error: error.message });
      }
    });
    return;
  }
  json(res, 405, { error: 'method not allowed' });
});

server.listen(port, '127.0.0.1', () => {
  console.log(`Review app (${mode} mode): http://127.0.0.1:${port}/  (Ctrl+C to stop)`);
});
