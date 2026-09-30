#!/usr/bin/env node
/**
 * Build a static HTML report from .eval/default/runs/<variant>/ (results.jsonl + summary.json).
 * Node twin of report.py; same output.
 *
 *   node report.mjs [--runs .eval/default/runs] [--out .eval/default/runs/report.html]
 *
 * One page, no JavaScript, no external assets. Every piece of case text is
 * HTML-escaped: inputs and outputs are untrusted.
 *
 * Part of eval-skills (Apache-2.0). Node standard library only.
 */
import { existsSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const arg = (name, fallback) => {
  const i = process.argv.indexOf(name);
  return i > -1 ? process.argv[i + 1] : fallback;
};
const runsDir = arg('--runs', '.eval/default/runs');
const outPath = arg('--out', join(runsDir, 'report.html'));

const CSS = `body{font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;margin:24px;color:#1d1d1b;background:#f7f7f5}
h1{font-size:20px}h2{font-size:16px;margin-top:28px}
table{border-collapse:collapse;background:#fff;width:100%}th,td{border:1px solid #e2e1dc;padding:6px 8px;text-align:left;vertical-align:top}
th{background:#f0efea;font-weight:600}.num{text-align:right;font-variant-numeric:tabular-nums}
.pass{color:#1f7a4d}.fail{color:#b3261e}.muted{color:#6b6b66}
pre{white-space:pre-wrap;overflow-wrap:anywhere;margin:4px 0;font:12px/1.4 ui-monospace,Menlo,monospace;background:#f7f7f5;padding:6px;border-radius:4px}
details summary{cursor:pointer}
@media (prefers-color-scheme:dark){body{background:#161615;color:#ecebe6}table{background:#1f1f1d}th{background:#262624}th,td{border-color:#33332f}pre{background:#161615}}`;

const escape = (s) =>
  String(s).replace(/[&<>"']/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#x27;' })[ch]);
const pct = (x) => (x == null ? '–' : `${Math.round(100 * x)}%`);
const signed = (x) => `${x >= 0 ? '+' : ''}${x.toFixed(2)}`;
const text = (v, limit = 4000) => {
  const s = typeof v === 'string' ? v : JSON.stringify(v, null, 2) ?? '';
  return escape(s.length <= limit ? s : `${s.slice(0, limit)} …`);
};
const readJsonl = (p) => (existsSync(p) ? readFileSync(p, 'utf8').split('\n').filter((l) => l.trim()).map((l) => JSON.parse(l)) : []);

const variants = readdirSync(runsDir, { withFileTypes: true })
  .filter((d) => d.isDirectory() && existsSync(join(runsDir, d.name, 'results.jsonl')))
  .map((d) => d.name)
  .sort((a, b) => (a === 'baseline' ? -1 : b === 'baseline' ? 1 : a.localeCompare(b)));
const summaries = Object.fromEntries(
  variants.map((v) => [v, existsSync(join(runsDir, v, 'summary.json')) ? JSON.parse(readFileSync(join(runsDir, v, 'summary.json'), 'utf8')) : {}]),
);
const rows = Object.fromEntries(variants.map((v) => [v, readJsonl(join(runsDir, v, 'results.jsonl'))]));
const modes = [...new Set(Object.values(summaries).flatMap((s) => Object.keys(s.per_failure_mode ?? {})))].sort();

const out = [
  '<!doctype html><html lang=en><head><meta charset=utf-8>',
  `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">`,
  `<title>Eval report</title><style>${CSS}</style></head><body><h1>Eval report</h1>`,
  '<p class=muted>Pass = the failure mode was not observed. Intervals are 95%. Differences inside the interval are noise, not wins.</p>',
  '<h2>Runs</h2><table><tr><th>Variant</th><th class=num>All pass</th><th>95% CI</th>',
  ...modes.map((m) => `<th class=num>${escape(m)}</th>`),
  '<th class=num>p50 s</th><th class=num>p95 s</th><th class=num>Errors</th><th>vs baseline</th></tr>',
];
for (const [name, s] of Object.entries(summaries)) {
  const ci = s.ci95_all ?? [null, null];
  const lat = s.latency_s ?? {};
  const err = s.errors ?? {};
  const c = s.compare ?? {};
  const verdict = c.n_cases ? `${signed(c.delta)} (${signed(c.ci95[0])} to ${signed(c.ci95[1])}): ${escape(c.verdict)}` : '–';
  out.push(
    `<tr><td>${escape(name)}</td><td class=num>${pct(s.pass_rate_all)}</td><td>${pct(ci[0])}–${pct(ci[1])}</td>`,
    ...modes.map((m) => `<td class=num>${pct(s.per_failure_mode?.[m]?.pass_rate)}</td>`),
    `<td class=num>${lat.p50 ?? '–'}</td><td class=num>${lat.p95 ?? '–'}</td><td class=num>${(err.app ?? 0) + (err.grader ?? 0)}</td><td>${verdict}</td></tr>`,
  );
}
out.push('</table>');

const caseIds = [...new Set(Object.values(rows).flat().map((r) => r.case_id))].sort();
out.push('<h2>Cases</h2><table><tr><th>Case</th><th>Tag</th>', ...variants.map((v) => `<th class=num>${escape(v)}</th>`), '</tr>');
for (const cid of caseIds) {
  const byVariant = Object.fromEntries(variants.map((v) => [v, rows[v].filter((r) => r.case_id === cid)]));
  const first = Object.values(byVariant).flat()[0];
  const cells = [`<td><details><summary>${escape(cid)}</summary><pre>${text(first.input)}</pre>`];
  for (const [v, rs] of Object.entries(byVariant)) {
    for (const r of rs) {
      const reasons = Object.entries(r.grades)
        .map(([m, g]) => `<div class=${g.passed ? 'pass' : 'fail'}>${escape(m)}: ${escape(g.reason ?? '')}</div>`)
        .join('');
      cells.push(`<div class=muted>${escape(v)} rep ${r.rep}</div><pre>${text(r.output)}</pre>${reasons}`);
    }
  }
  cells.push(`</details></td><td>${escape((first.tags ?? ['–'])[0])}</td>`);
  for (const rs of Object.values(byVariant)) {
    if (!rs.length) {
      cells.push('<td class=num>–</td>');
      continue;
    }
    const p = rs.filter((r) => r.passed_all).length / rs.length;
    cells.push(`<td class='num ${p === 1 ? 'pass' : p === 0 ? 'fail' : ''}'>${Math.round(p * 100)}%</td>`);
  }
  out.push(`<tr>${cells.join('')}</tr>`);
}
out.push('</table></body></html>');
writeFileSync(outPath, out.join(''));
console.log(`Wrote ${outPath}`);
