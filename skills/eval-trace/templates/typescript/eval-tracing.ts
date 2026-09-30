/**
 * Tracing setup for eval-skills. Call `setupTracing()` once at startup.
 *
 * Where traces go is chosen by an environment variable, so switching between
 * local files and Confident AI never needs a code change:
 *
 *   EVAL_SKILLS_TRACE_MODE=confident  send to Confident AI (needs CONFIDENT_API_KEY)
 *   EVAL_SKILLS_TRACE_MODE=local      write OTLP/JSON lines to .eval/default/traces/
 *   EVAL_SKILLS_TRACE_MODE=off        no tracing
 *
 * When unset, the mode is `local`, even when a managed API key exists.
 *
 * Automatic SDK instrumentation also needs the preload flag on your start
 * command: `node --import confident-trace/register dist/index.js`.
 *
 * Part of eval-skills (Apache-2.0). Copy next to `local-exporter.ts`.
 */
import { init } from 'confident-trace';
import { JsonlSpanExporter } from './local-exporter.js';

type InitOptions = NonNullable<Parameters<typeof init>[0]>;

export function traceMode(): 'confident' | 'local' | 'off' {
  const mode = (process.env.EVAL_SKILLS_TRACE_MODE ?? '').trim().toLowerCase();
  if (mode === 'confident' || mode === 'local' || mode === 'off') return mode;
  if (mode) throw new Error('EVAL_SKILLS_TRACE_MODE must be local, confident, or off');
  return 'local';
}

/** Start tracing and return the confident-trace runtime (undefined when off). */
export function setupTracing(serviceName = 'ai-app', options: InitOptions = {}) {
  const mode = traceMode();
  if (mode === 'off') return undefined;
  const resourceAttributes = { 'service.name': serviceName, ...(options.resourceAttributes ?? {}) };
  if (mode === 'confident') return init({ ...options, resourceAttributes });
  return init({
    ...options,
    apiKey: '',
    exporter: new JsonlSpanExporter(process.env.EVAL_SKILLS_TRACES_DIR ?? '.eval/default/traces'),
    resourceAttributes,
  });
}
