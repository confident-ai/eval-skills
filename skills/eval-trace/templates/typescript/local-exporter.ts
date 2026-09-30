/**
 * Write finished OpenTelemetry spans to local JSON Lines files.
 *
 * Each line is one OTLP/JSON ExportTraceServiceRequest (the shape an OTLP/HTTP
 * collector accepts with `Content-Type: application/json`), so the files can
 * be replayed to any OTLP endpoint later, including Confident AI.
 *
 * Part of eval-skills (Apache-2.0). Copy into your project.
 */
import { appendFileSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';
import type { ReadableSpan, SpanExporter } from '@opentelemetry/sdk-trace-base';

type ExportResult = { code: 0 | 1; error?: Error };
type AnyValue = Record<string, unknown>;

function anyValue(value: unknown): AnyValue {
  if (typeof value === 'boolean') return { boolValue: value };
  if (typeof value === 'number') {
    return Number.isInteger(value) ? { intValue: String(value) } : { doubleValue: value };
  }
  if (Array.isArray(value)) return { arrayValue: { values: value.map(anyValue) } };
  return { stringValue: String(value) };
}

function attributes(attrs: Record<string, unknown> | undefined) {
  return Object.entries(attrs ?? {})
    .filter(([, v]) => v !== undefined)
    .map(([key, v]) => ({ key, value: anyValue(v) }));
}

function nanos([seconds, nanoseconds]: [number, number]): string {
  return (BigInt(seconds) * 1_000_000_000n + BigInt(nanoseconds)).toString();
}

function toSpan(span: ReadableSpan) {
  const ctx = span.spanContext();
  // SDK v2 exposes parentSpanContext; v1 exposed parentSpanId.
  const parent =
    (span as unknown as { parentSpanContext?: { spanId: string } }).parentSpanContext?.spanId ??
    (span as unknown as { parentSpanId?: string }).parentSpanId;
  const out: Record<string, unknown> = {
    traceId: ctx.traceId,
    spanId: ctx.spanId,
    name: span.name,
    // OTLP numbers SpanKind from UNSPECIFIED=0; the SDK starts at INTERNAL=0.
    kind: span.kind + 1,
    startTimeUnixNano: nanos(span.startTime),
    endTimeUnixNano: nanos(span.endTime),
    attributes: attributes(span.attributes),
    status: span.status.message
      ? { code: span.status.code, message: span.status.message }
      : { code: span.status.code },
  };
  if (parent) out.parentSpanId = parent;
  if (span.events.length) {
    out.events = span.events.map((e) => ({
      timeUnixNano: nanos(e.time),
      name: e.name,
      attributes: attributes(e.attributes),
    }));
  }
  return out;
}

export function toOtlpJson(spans: ReadableSpan[]) {
  const resources = new Map<unknown, { resource: unknown; scopes: Map<string, { scope: unknown; spans: unknown[] }> }>();
  for (const span of spans) {
    let entry = resources.get(span.resource);
    if (!entry) {
      entry = { resource: { attributes: attributes(span.resource.attributes) }, scopes: new Map() };
      resources.set(span.resource, entry);
    }
    const scope =
      (span as unknown as { instrumentationScope?: { name: string; version?: string } }).instrumentationScope ??
      (span as unknown as { instrumentationLibrary?: { name: string; version?: string } }).instrumentationLibrary ??
      { name: '' };
    const key = `${scope.name}@${scope.version ?? ''}`;
    let scoped = entry.scopes.get(key);
    if (!scoped) {
      scoped = { scope: { name: scope.name, version: scope.version ?? '' }, spans: [] };
      entry.scopes.set(key, scoped);
    }
    scoped.spans.push(toSpan(span));
  }
  return {
    resourceSpans: [...resources.values()].map((r) => ({
      resource: r.resource,
      scopeSpans: [...r.scopes.values()],
    })),
  };
}

/** Appends each exported batch to `<directory>/spans-YYYY-MM-DD.jsonl`. */
export class JsonlSpanExporter implements SpanExporter {
  constructor(private readonly directory = '.eval/default/traces') {
    mkdirSync(directory, { recursive: true });
  }

  export(spans: ReadableSpan[], resultCallback: (result: ExportResult) => void): void {
    try {
      if (spans.length) {
        const day = new Date().toISOString().slice(0, 10);
        appendFileSync(join(this.directory, `spans-${day}.jsonl`), JSON.stringify(toOtlpJson(spans)) + '\n');
      }
      resultCallback({ code: 0 });
    } catch (error) {
      // Never break the application because of tracing.
      resultCallback({ code: 1, error: error as Error });
    }
  }

  async shutdown(): Promise<void> {}

  async forceFlush(): Promise<void> {}
}
