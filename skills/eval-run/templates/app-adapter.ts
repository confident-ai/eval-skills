/**
 * Adapter between the eval runner and the real application.
 *
 * Copy to .eval/default/scripts/app-adapter.ts and implement runCase(). It must call
 * the app's REAL entry point (the same function, route, or command production
 * uses), not a re-creation of its LLM call. Stub only side effects that can't
 * run safely (sending emails, writing to production databases).
 *
 * runCase returns the "result" half of the eval-skills grader contract:
 *   { output, retrieval_context?, tools_called?, turns?, model?, usage?, trace_id? }
 * Take `model` and `usage` from the response, not from config.
 *
 * Throw on failure. The runner classifies the error (timeout, rate limit,
 * harness error) and records it in errors.jsonl instead of scoring it.
 *
 * Part of eval-skills (Apache-2.0).
 */
export type EvalCase = { id: string; input?: unknown; scenario?: string; tags?: string[]; [k: string]: unknown };
export type AppResult = {
  output: unknown;
  retrieval_context?: string[];
  tools_called?: { name: string; input?: unknown; output?: unknown }[];
  turns?: { role: 'user' | 'assistant'; content: string }[];
  model?: string;
  usage?: { input_tokens?: number; output_tokens?: number };
  trace_id?: string;
};

export async function runCase(testCase: EvalCase): Promise<AppResult> {
  // Example for a single-turn app:
  //
  //   import { answer } from '../../src/agent.js';
  //   const reply = await answer(String(testCase.input));
  //   return { output: reply };
  throw new Error(`Implement runCase() to call the application's real entry point (case ${testCase.id}).`);
}
