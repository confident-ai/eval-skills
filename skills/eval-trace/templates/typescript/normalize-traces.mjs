#!/usr/bin/env node
/**
 * Turn raw OTLP/JSON span files into one review record per trace.
 *
 *   node normalize-traces.mjs [--in .eval/default/traces] [--out .eval/default/traces/traces.jsonl]
 *
 * Reads every `spans-*.jsonl` written by `local-exporter.ts` and writes
 * `traces.jsonl` in the eval-skills review-record shape (see
 * references/trace-schema.md). Safe to re-run: the output is rebuilt each time.
 *
 * Part of eval-skills (Apache-2.0). Node standard library only.
 */
import { mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';

function arg(name, fallback) {
  const i = process.argv.indexOf(name);
  return i > -1 ? process.argv[i + 1] : fallback;
}

function value(v) {
  if ('stringValue' in v) return v.stringValue;
  if ('boolValue' in v) return v.boolValue;
  if ('intValue' in v) return Number(v.intValue);
  if ('doubleValue' in v) return v.doubleValue;
  if ('arrayValue' in v) return (v.arrayValue.values ?? []).map(value);
  if ('kvlistValue' in v) return Object.fromEntries((v.kvlistValue.values ?? []).map((kv) => [kv.key, value(kv.value)]));
  return null;
}

const attrs = (items) => Object.fromEntries((items ?? []).map((i) => [i.key, value(i.value)]));

function decode(v) {
  if (typeof v !== 'string') return v;
  try {
    return JSON.parse(v);
  } catch {
    return v;
  }
}

/** Decorated functions record their arguments; show the useful part. */
function unwrapCall(v) {
  if (v && typeof v === 'object' && !Array.isArray(v) && Object.keys(v).sort().join() === 'args,kwargs') {
    if (v.args.length === 1 && !Object.keys(v.kwargs).length) return v.args[0];
    if (!v.args.length) return v.kwargs;
  }
  if (Array.isArray(v) && v.length === 1) return v[0];
  return v;
}

function stepType(a) {
  if (a['confident.span.type']) return String(a['confident.span.type']);
  const op = a['gen_ai.operation.name'];
  if (['chat', 'text_completion', 'generate_content'].includes(op)) return 'llm';
  if (op === 'execute_tool') return 'tool';
  if (op === 'invoke_agent') return 'agent';
  return 'custom';
}

function loadSpans(dir) {
  const byTrace = new Map();
  const files = readdirSync(dir).filter((f) => /^spans-.*\.jsonl$/.test(f)).sort();
  for (const file of files) {
    for (const line of readFileSync(join(dir, file), 'utf8').split('\n')) {
      if (!line.trim()) continue;
      for (const rs of JSON.parse(line).resourceSpans ?? []) {
        const resource = attrs(rs.resource?.attributes);
        for (const ss of rs.scopeSpans ?? []) {
          for (const span of ss.spans ?? []) {
            const s = { ...span, _attrs: attrs(span.attributes), _resource: resource };
            if (!byTrace.has(s.traceId)) byTrace.set(s.traceId, []);
            byTrace.get(s.traceId).push(s);
          }
        }
      }
    }
  }
  return byTrace;
}

const ns = (x) => BigInt(x);

function toRecord(traceId, spans) {
  const ids = new Set(spans.map((s) => s.spanId));
  const roots = spans.filter((s) => !s.parentSpanId || !ids.has(s.parentSpanId));
  const root = (roots.length ? roots : spans).reduce((a, b) => (ns(a.startTimeUnixNano) <= ns(b.startTimeUnixNano) ? a : b));
  const ra = root._attrs;
  const traceAttrs = {};
  for (const s of spans) {
    for (const [k, v] of Object.entries(s._attrs)) {
      if (k.startsWith('confident.trace.') && (!(k in traceAttrs) || s === root)) traceAttrs[k] = v;
    }
  }
  const start = ns(root.startTimeUnixNano);
  const end = spans.reduce((m, s) => (ns(s.endTimeUnixNano) > m ? ns(s.endTimeUnixNano) : m), 0n);
  const steps = [];
  for (const s of [...spans].sort((a, b) => (ns(a.startTimeUnixNano) < ns(b.startTimeUnixNano) ? -1 : 1))) {
    if (s === root) continue;
    const a = s._attrs;
    const step = { type: stepType(a), name: a['gen_ai.tool.name'] ?? s.name };
    step.input = unwrapCall(decode(a['confident.span.input'] ?? a['gen_ai.input.messages']));
    step.output = decode(a['confident.span.output'] ?? a['gen_ai.output.messages']);
    if (a['gen_ai.system_instructions']) step.system = decode(a['gen_ai.system_instructions']);
    const model = a['gen_ai.response.model'] ?? a['gen_ai.request.model'];
    if (model) step.model = model;
    if (a['gen_ai.usage.input_tokens'] != null) step.input_tokens = a['gen_ai.usage.input_tokens'];
    if (a['gen_ai.usage.output_tokens'] != null) step.output_tokens = a['gen_ai.usage.output_tokens'];
    if (s.status?.code === 2) step.error = s.status.message || a['error.type'] || 'error';
    steps.push(step);
  }
  const tags = traceAttrs['confident.trace.tags'] ?? [];
  const metadata = decode(traceAttrs['confident.trace.metadata']) ?? {};
  for (const key of ['environment', 'user_id', 'customer_id']) {
    if (traceAttrs[`confident.trace.${key}`]) metadata[key] = traceAttrs[`confident.trace.${key}`];
  }
  if (root._resource['service.name']) metadata.service ??= root._resource['service.name'];
  return {
    trace_id: traceId,
    thread_id: traceAttrs['confident.trace.thread_id'] ?? ra['gen_ai.conversation.id'] ?? null,
    started_at: new Date(Number(start / 1_000_000n)).toISOString(),
    duration_ms: Number((end - start) / 100_000n) / 10,
    name: traceAttrs['confident.trace.name'] ?? root.name,
    input: unwrapCall(decode(traceAttrs['confident.trace.input'] ?? ra['confident.span.input'])),
    output: decode(traceAttrs['confident.trace.output'] ?? ra['confident.span.output']),
    tags: Array.isArray(tags) ? tags : [tags],
    metadata,
    steps,
    error: root.status?.code === 2 ? root.status.message || 'error' : null,
  };
}

const src = arg('--in', '.eval/default/traces');
const dst = arg('--out', join(src, 'traces.jsonl'));
const records = [...loadSpans(src)].map(([id, spans]) => toRecord(id, spans));
records.sort((a, b) => a.started_at.localeCompare(b.started_at));
mkdirSync(dirname(dst), { recursive: true });
writeFileSync(dst, records.map((r) => JSON.stringify(r)).join('\n') + (records.length ? '\n' : ''));
console.log(`Wrote ${records.length} traces to ${dst}`);
