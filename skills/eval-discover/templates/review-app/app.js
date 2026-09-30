// Trace Review app for eval-skills (Apache-2.0).
// Trace content is untrusted: everything from a trace is inserted with
// textContent, never innerHTML. Keep it that way when customizing.
'use strict';

const TOKEN = document.querySelector('meta[name="session-token"]').content;
const state = {
  traces: [],
  annotations: {},
  modes: [],
  taxonomy: {revision:0,modes:[],assignments:[]},
  mode: 'review',
  index: 0,
  version: null,
  activeLabel: 0,
  view: 'review',
};
const $ = (id) => document.getElementById(id);

function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value == null) continue;
    if (key === 'className') node.className = value;
    else if (key === 'dataset') Object.assign(node.dataset, value);
    else if (key === 'open') node.open = Boolean(value);
    else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child == null || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

// ---------------------------------------------------------------------------
// CUSTOMIZE: domain rendering.
// Make each value look like what it is (an email as an email, a table as a
// table, code in monospace). Always build DOM nodes and set text with
// textContent / el(); never assign trace content to innerHTML.
// ---------------------------------------------------------------------------

function isMessages(value) {
  return Array.isArray(value) && value.length > 0 && value.every((m) => m && typeof m === 'object' && 'role' in m);
}

function messageText(message) {
  const parts = Array.isArray(message.parts) ? message.parts : Array.isArray(message.content) ? message.content : null;
  if (parts) {
    return parts
      .map((p) => (typeof p === 'string' ? p : p.content ?? p.text ?? JSON.stringify(p, null, 2)))
      .join('\n');
  }
  return typeof message.content === 'string' ? message.content : JSON.stringify(message.content ?? message, null, 2);
}

function renderValue(value, { big = false } = {}) {
  if (value == null || value === '') return el('p', { className: 'text muted' }, '(empty)');
  if (typeof value === 'string') return el('p', { className: big ? 'text big' : 'text' }, value);
  if (isMessages(value)) {
    return el(
      'div',
      {},
      value.map((m) => el('div', { className: 'msg' }, el('div', { className: 'role' }, m.role), el('p', { className: 'text' }, messageText(m)))),
    );
  }
  return el('pre', { className: 'json' }, JSON.stringify(value, null, 2));
}

function renderStep(step) {
  const type = step.type || 'custom';
  const meta = [step.name, step.model, step.input_tokens != null ? `${step.input_tokens}→${step.output_tokens ?? '?'} tok` : null]
    .filter(Boolean)
    .join(' · ');
  const body = [];
  if (step.system != null) {
    body.push(el('details', { className: 'block' }, el('summary', {}, 'System instructions'), renderValue(step.system)));
  }
  if (step.input != null) body.push(el('div', { className: 'block-title' }, 'Input'), renderValue(step.input));
  if (step.output != null) body.push(el('div', { className: 'block-title' }, 'Output'), renderValue(step.output));
  if (step.error) body.push(el('p', { className: 'text' }, `Error: ${step.error}`));
  const long = JSON.stringify(step).length > 2500;
  return el('details', { className: `block ${type}`, open: !long }, el('summary', {}, type, el('span', { className: 'sub' }, meta)), body);
}

// ---------------------------------------------------------------------------

function renderTrace() {
  const trace = state.traces[state.index];
  const header = $('trace-header');
  const body = $('trace-body');
  header.replaceChildren();
  body.replaceChildren();
  if (!trace) {
    body.append(el('p', { className: 'muted' }, 'No traces to review yet. Your agent adds them to samples.json.'));
    return;
  }
  const chips = [
    el('h1', {}, trace.name || trace.trace_id),
    el('span', { className: 'chip' }, trace.trace_id.slice(0, 12)),
    trace.thread_id ? el('span', { className: 'chip' }, `thread ${trace.thread_id}`) : null,
    trace.duration_ms != null ? el('span', { className: 'chip' }, `${trace.duration_ms} ms`) : null,
    ...(trace.tags || []).map((t) => el('span', { className: 'chip' }, t)),
    trace.error ? el('span', { className: 'chip error' }, `error: ${trace.error}`) : null,
  ];
  header.append(...chips.filter(Boolean));

  const meta = state.mode === 'label' ? [] : Object.entries(trace.metadata || {});
  if (meta.length) {
    body.append(el('dl', { className: 'kv' }, meta.flatMap(([k, v]) => [el('dt', {}, k), el('dd', {}, typeof v === 'string' ? v : JSON.stringify(v))])));
  }
  body.append(el('div', { className: 'block user' }, el('div', { className: 'block-title' }, 'User input'), renderValue(trace.input, { big: true })));
  if ((trace.steps || []).length) body.append(el('div', { className: 'steps' }, trace.steps.map(renderStep)));
  body.append(el('div', { className: 'block output' }, el('div', { className: 'block-title' }, 'Final output'), renderValue(trace.output, { big: true })));
}

function currentAnnotation() {
  const trace = state.traces[state.index];
  return (trace && state.annotations[trace.trace_id]) || { verdict: null, note: '', labels: {} };
}

function renderPanel() {
  const a = currentAnnotation();
  document.querySelectorAll('.verdict').forEach((b) => b.classList.toggle('selected', b.dataset.verdict === a.verdict));
  const note = $('note');
  if (document.activeElement !== note) note.value = a.note || '';

  const labelGroup = $('label-group');
  labelGroup.hidden = state.mode !== 'label';
  $('verdict-group').hidden = state.mode === 'label';
  if (state.mode === 'label') {
    labelGroup.replaceChildren(
      ...state.modes.filter(m => m.status !== 'retired').map((m, i) =>
        el(
          'div',
          { className: `label-row${i === state.activeLabel ? ' active' : ''}` },
          el('strong', {}, m.id),
          el('p', { className: 'def' }, m.definition || ''),
          el(
            'div',
            { className: 'choices' },
            ['pass', 'fail', 'uncertain'].map((v) =>
              el('button', {
                type: 'button',
                className: `verdict ${v}${(a.labels || {})[m.id] === v ? ' selected' : ''}`,
                onclick: () => setLabel(m.id, v),
              }, v === 'pass' ? 'Pass' : v === 'fail' ? 'Fail' : 'Uncertain'),
            ),
          ),
        ),
      ),
    );
    if (!state.modes.length) labelGroup.append(el('p', { className: 'muted' }, 'No failure modes in failure_modes.json yet.'));
  }

  const reviewed = state.traces.filter((t) => isReviewed(state.annotations[t.trace_id])).length;
  $('counter').textContent = state.traces.length
    ? `${state.index + 1} of ${state.traces.length} · ${reviewed} reviewed`
    : '0 traces';
}

function isReviewed(a) {
  if (!a) return false;
  if (state.mode === 'label') return Object.keys(a.labels || {}).length > 0;
  return Boolean(a.verdict || (a.note || '').trim());
}

function render() {
  renderTrace();
  renderPanel();
  if (state.view === 'progress') renderProgress();
}

let noteTimer = null;
let writes = Promise.resolve();
function save(patch) {
  const id = state.traces[state.index]?.trace_id;
  writes = writes.then(() => saveNow(patch, id));
  return writes;
}

async function saveNow(patch, traceId) {
  const trace = state.traces.find(t => t.trace_id === traceId);
  if (!trace) return;
  const next = { ...(state.annotations[traceId] || {}), ...patch };
  const reviewer = $('reviewer').value.trim();
  if (!reviewer) { $('save-status').textContent = 'Enter your reviewer name before saving.'; return; }
  localStorage.setItem('eval-reviewer', reviewer);
  state.annotations[trace.trace_id] = next;
  try {
    localStorage.setItem(`review:${trace.trace_id}`, JSON.stringify(next));
  } catch {
    /* storage can be unavailable; the server copy is the source of truth */
  }
  $('save-status').textContent = 'Saving…';
  try {
    const res = await fetch('/api/annotations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Session-Token': TOKEN },
      body: JSON.stringify({ trace_id: trace.trace_id, revision: next.revision ?? 0, reviewed_by: reviewer, verdict: next.verdict ?? null, note: next.note ?? '', labels: next.labels ?? {} }),
    });
    if (!res.ok) throw new Error((await res.json()).error || res.statusText);
    state.annotations[trace.trace_id] = await res.json();
    localStorage.removeItem(`review:${trace.trace_id}`);
    $('save-status').textContent = `Saved ${new Date().toLocaleTimeString()}`;
  } catch (err) {
    $('save-status').textContent = `Not saved: ${err.message}`;
  }
  renderPanel();
}

function setVerdict(verdict) {
  const a = currentAnnotation();
  save({ verdict: a.verdict === verdict ? null : verdict });
}

function setLabel(modeId, value) {
  const labels = { ...(currentAnnotation().labels || {}) };
  labels[modeId] = labels[modeId] === value ? null : value;
  save({ labels });
}

function go(delta) {
  if (!state.traces.length) return;
  flushNote();
  state.index = Math.min(state.traces.length - 1, Math.max(0, state.index + delta));
  state.activeLabel = 0;
  render();
  window.scrollTo({ top: 0 });
}

function goTo(traceId) {
  const i = state.traces.findIndex((t) => t.trace_id === traceId);
  if (i === -1) return;
  flushNote();
  state.index = i;
  showView('review');
  render();
}

function nextUnreviewed() {
  const n = state.traces.length;
  for (let step = 1; step <= n; step++) {
    const i = (state.index + step) % n;
    if (!isReviewed(state.annotations[state.traces[i].trace_id])) return go(i - state.index);
  }
}

function flushNote() {
  if (noteTimer) {
    clearTimeout(noteTimer);
    noteTimer = null;
    save({ note: $('note').value });
  }
}

function renderProgress() {
  taxonomyControls();
  const counts = { pass: 0, fail: 0, defer: 0, notes: 0 };
  for (const t of state.traces) {
    const a = state.annotations[t.trace_id];
    if (!a) continue;
    if (a.verdict) counts[a.verdict] += 1;
    if ((a.note || '').trim()) counts.notes += 1;
  }
  const reviewed = state.traces.filter((t) => isReviewed(state.annotations[t.trace_id])).length;
  const stat = (n, l) => el('div', { className: 'stat' }, el('div', { className: 'n' }, n), el('div', { className: 'l' }, l));
  $('stats').replaceChildren(
    stat(`${reviewed}/${state.traces.length}`, 'reviewed'),
    stat(counts.pass, 'pass'),
    stat(counts.fail, 'fail'),
    stat(counts.defer, 'deferred'),
    stat(counts.notes, 'with notes'),
  );
  const modes = [...state.modes].sort((a, b) => (b.count || 0) - (a.count || 0));
  $('modes').replaceChildren(
    ...(modes.length
      ? modes.map((m) =>
          el(
            'div',
            { className: 'mode' },
            el('div', { className: 'head' }, el('span', { className: 'id' }, m.id), el('span', { className: 'count' }, `${m.count ?? 0} traces`)),
            el('p', { className: 'text' }, m.definition || ''),
            el('div', { className: 'examples' }, (m.examples || []).slice(0, 12).map((id) => el('button', { type: 'button', onclick: () => goTo(String(id)) }, String(id).slice(0, 10)))),
          ),
        )
      : [el('p', { className: 'muted' }, 'None yet. Write notes as you review; your agent groups them into failure modes.')]),
  );
}

function showView(view) {
  state.view = view;
  $('view-review').hidden = view !== 'review';
  $('view-progress').hidden = view !== 'progress';
  document.querySelectorAll('.tab').forEach((t) => t.classList.toggle('active', t.dataset.view === view));
  if (view === 'progress') renderProgress();
}

async function load(initial = false) {
  const res = await fetch('/api/data');
  const data = await res.json();
  const currentId = state.traces[state.index]?.trace_id;
  const before = state.traces.length;
  state.mode = data.mode;
  state.version = JSON.stringify(data.version);
  state.traces = data.traces;
  state.modes = data.failure_modes || [];
  state.taxonomy = data.taxonomy || {revision:0,modes:state.modes,assignments:[]};
  // Keep in-flight edits for the trace on screen; take the server copy for the rest.
  const local = currentId ? state.annotations[currentId] : null;
  state.annotations = data.annotations || {};
  if (local && currentId) state.annotations[currentId] = local;
  const i = state.traces.findIndex((t) => t.trace_id === currentId);
  state.index = i >= 0 ? i : 0;
  $('mode-badge').textContent = state.mode === 'label' ? 'label mode' : 'review mode';
  if (!initial && state.traces.length > before) {
    const banner = $('banner');
    banner.textContent = `${state.traces.length - before} new traces added to review.`;
    banner.hidden = false;
    setTimeout(() => (banner.hidden = true), 6000);
  }
  render();
}

async function poll() {
  try {
    const meta = await (await fetch('/api/meta')).json();
    if (JSON.stringify(meta.version) !== state.version && document.activeElement !== $('note')) await load();
  } catch {
    /* server stopped; try again on the next tick */
  }
}

document.querySelectorAll('.verdict[data-verdict]').forEach((b) => b.addEventListener('click', () => setVerdict(b.dataset.verdict)));
document.querySelectorAll('.tab').forEach((t) => t.addEventListener('click', () => showView(t.dataset.view)));
$('prev').addEventListener('click', () => go(-1));
$('next').addEventListener('click', () => go(1));
$('note').addEventListener('input', () => {
  clearTimeout(noteTimer);
  $('save-status').textContent = 'Editing…';
  noteTimer = setTimeout(() => {
    noteTimer = null;
    save({ note: $('note').value });
  }, 500);
});
$('note').addEventListener('blur', flushNote);

document.addEventListener('keydown', (e) => {
  if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return;
  if (e.target === $('note')) {
    if (e.key === 'Escape') $('note').blur();
    return;
  }
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  const labelMode = state.mode === 'label';
  const key = e.key;
  if (key === 'ArrowRight' || key === 'j') go(1);
  else if (key === 'ArrowLeft' || key === 'k') go(-1);
  else if (key === 'u') nextUnreviewed();
  else if (key === 'n') {
    e.preventDefault();
    $('note').focus();
  } else if (!labelMode && key === '1') setVerdict('pass');
  else if (!labelMode && key === '2') setVerdict('fail');
  else if (!labelMode && key === '3') setVerdict('defer');
  else if (labelMode && state.modes.length && (key === '1' || key === '2')) {
    setLabel(state.modes[state.activeLabel].id, key === '1' ? 'pass' : 'fail');
    state.activeLabel = Math.min(state.modes.length - 1, state.activeLabel + 1);
    renderPanel();
  } else if (labelMode && (key === ']' || key === '[') && state.modes.length) {
    state.activeLabel = (state.activeLabel + (key === '[' ? state.modes.length - 1 : 1)) % state.modes.length;
    renderPanel();
  }
});
window.addEventListener('beforeunload', flushNote);

load(true).then(() => setInterval(poll, 5000));

// Taxonomy proposals and memberships are reviewed separately.
async function editTaxonomy(action, mutate) {
  const reviewer = $('reviewer').value.trim();
  if (!reviewer) { alert('Enter your reviewer name first.'); return; }
  const next = structuredClone(state.taxonomy);
  if (mutate(next) === false) return;
  const res = await fetch('/api/taxonomy', {method:'POST', headers:{'Content-Type':'application/json','X-Session-Token':TOKEN}, body:JSON.stringify({...next,reviewed_by:reviewer,action})});
  const data = await res.json();
  if (!res.ok) { alert(data.error); return; }
  state.taxonomy = data; state.modes = data.modes; renderProgress();
}
function newMode(id) {
  if (!id?.trim()) return null;
  const definition = prompt('Observable definition for ' + id);
  return definition?.trim() ? {id:id.trim(),name:id.trim(),definition,status:'proposed'} : null;
}
function taxonomyControls() {
  const box = $('taxonomy-controls');
  const button = (name, fn) => el('button',{type:'button',onclick:fn},name);
  box.replaceChildren(el('h2',{},'Review taxonomy'), el('p',{},'Definitions and assignments are confirmed separately. Merges and splits preserve prior revisions.'),
    button('Add mode',()=>editTaxonomy('add',t=>{const m=newMode(prompt('Stable mode ID'));if(!m)return false;t.modes.push(m);})),
    button('Merge modes',()=>editTaxonomy('merge',t=>{
      const from=(prompt('Mode IDs to merge, separated by commas')||'').split(',').map(x=>x.trim());
      if(from.length<2 || from.some(id=>!t.modes.some(m=>m.id===id && m.status!=='retired')))return false;
      const m=newMode(prompt('New merged mode ID'));if(!m)return false;m.parents=from;t.modes.push(m);
      for(const old of t.modes)if(from.includes(old.id))old.status='retired';
      for(const a of t.assignments)if(from.includes(a.mode_id)){a.mode_id=m.id;a.status='suggested';delete a.reviewed_by;delete a.reviewed_at;}
    })),
    button('Split mode',()=>editTaxonomy('split',t=>{
      const id=prompt('Mode ID to split'); const old=t.modes.find(m=>m.id===id&&m.status!=='retired');if(!old)return false;
      const first=newMode(prompt('First new mode ID'));if(!first)return false;
      const second=newMode(prompt('Second new mode ID'));if(!second)return false;
      old.status='retired'; t.modes.push({...first,parents:[id]},{...second,parents:[id]});
      for(const a of t.assignments)if(a.mode_id===id){a.previous_mode_id=id;a.mode_id=null;a.status='uncertain';delete a.reviewed_by;delete a.reviewed_at;}
    })));
  for(const m of state.modes) {
    const assigned = state.taxonomy.assignments.filter(a=>a.mode_id===m.id && a.status!=='rejected');
    const confirmed = new Set(assigned.filter(a=>a.status==='confirmed').map(a=>a.case_id)).size;
    const suggested = new Set(assigned.filter(a=>a.status!=='confirmed').map(a=>a.case_id)).size;
    box.append(el('article',{className:'mode'},el('strong',{},m.name||m.id),el('p',{},m.definition),el('p',{},`${m.status||'proposed'} · ${confirmed} confirmed cases · ${suggested} proposed cases`),
      button('Rename '+m.id,()=>editTaxonomy('rename',t=>{const name=prompt('Display name',m.name||m.id);if(!name)return false;t.modes.find(x=>x.id===m.id).name=name;})),
      button('Confirm definition '+m.id,()=>editTaxonomy('confirm-definition',t=>{t.modes.find(x=>x.id===m.id).status='confirmed';})),
      button('Retire '+m.id,()=>editTaxonomy('retire',t=>{t.modes.find(x=>x.id===m.id).status='retired';}))));
  }
  box.append(el('h3',{},'Annotations and unresolved assignments'));
  for(const [traceId,note] of Object.entries(state.annotations)) {
    const annotationId=note.id||'note:'+traceId;
    const assignments=state.taxonomy.assignments.filter(a=>a.annotation_id===annotationId);
    const select=el('select',{'aria-label':'Mode for '+traceId},state.modes.filter(m=>m.status!=='retired').map(m=>el('option',{value:m.id},m.name||m.id)));
    box.append(el('article',{className:'mode'},button('Open trace '+traceId,()=>goTo(traceId)),el('p',{},note.note),select,
      button('Suggest assignment '+traceId,()=>editTaxonomy('assign',t=>{
        if(!select.value)return false;t.assignments.push({id:crypto.randomUUID(),annotation_id:annotationId,case_id:note.case_id||traceId,trace_id:traceId,mode_id:select.value,origin:'human',status:'suggested'});
      })),...assignments.map(a=>el('div',{},`${a.mode_id||'Unresolved'} — ${a.status} `,
        button('Confirm assignment '+a.id,()=>editTaxonomy('confirm-assignment',t=>{if(!a.mode_id)return false;t.assignments.find(x=>x.id===a.id).status='confirmed';})),
        button('Reassign '+a.id,()=>editTaxonomy('reassign',t=>{if(!select.value)return false;Object.assign(t.assignments.find(x=>x.id===a.id),{mode_id:select.value,status:'suggested',reviewed_by:null,reviewed_at:null});})),
        button('Reject '+a.id,()=>editTaxonomy('reject',t=>{t.assignments.find(x=>x.id===a.id).status='rejected';})))),
      assignments.length ? null : el('p',{},'Unresolved: no mode assigned')));
  }
}
$('reviewer').value=localStorage.getItem('eval-reviewer')||'';
