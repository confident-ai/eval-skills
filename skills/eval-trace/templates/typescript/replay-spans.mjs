#!/usr/bin/env node
/**
 * Send locally recorded spans to an OTLP/HTTP endpoint, such as Confident AI.
 *
 *   CONFIDENT_API_KEY=... node replay-spans.mjs [--in .eval/default/traces] [--endpoint URL] [--dry-run]
 *
 * Use this when moving from a local track to Confident AI so your trace
 * history comes with you. Each line of `spans-*.jsonl` is already an OTLP/JSON
 * export request, so it is posted as-is. Replaying the same files twice sends
 * duplicates; move replayed files aside afterwards.
 *
 * Part of eval-skills (Apache-2.0). Node standard library only (Node 22+).
 */
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

function arg(name, fallback) {
  const i = process.argv.indexOf(name);
  return i > -1 ? process.argv[i + 1] : fallback;
}

const src = arg('--in', '.eval/default/traces');
const endpoint = arg('--endpoint', process.env.CONFIDENT_OTEL_ENDPOINT ?? 'https://otel.confident-ai.com/v1/traces');
const dryRun = process.argv.includes('--dry-run');
const apiKey = process.env.CONFIDENT_API_KEY ?? '';
if (!apiKey && !dryRun) {
  console.error('Set CONFIDENT_API_KEY first (the user adds it to .env).');
  process.exit(1);
}

async function post(body, attempts = 4) {
  for (let attempt = 0; attempt < attempts; attempt++) {
    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-confident-api-key': apiKey },
        body,
        signal: AbortSignal.timeout(30_000),
      });
      if (res.ok) return;
      if (![429, 500, 502, 503, 504].includes(res.status) || attempt === attempts - 1) {
        throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      }
    } catch (error) {
      if (attempt === attempts - 1) throw error;
    }
    await new Promise((r) => setTimeout(r, 1000 * 2 ** attempt));
  }
}

let sent = 0;
for (const file of readdirSync(src).filter((f) => /^spans-.*\.jsonl$/.test(f)).sort()) {
  for (const line of readFileSync(join(src, file), 'utf8').split('\n')) {
    if (!line.trim()) continue;
    if (!dryRun) await post(line);
    sent++;
  }
}
console.log(`${dryRun ? 'Would send' : 'Sent'} ${sent} export batches to ${endpoint}`);
