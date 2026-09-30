/**
 * Graders for the local track, written without an eval library.
 *
 * Copy to .eval/default/graders/graders.ts next to judge.ts. Replace the examples with
 * one grader per failure mode (ids from .eval/default/eval-skills.json). Every grader
 * follows the eval-skills grader contract and throws (instead of returning a
 * fail) when it can't decide.
 *
 * Part of eval-skills (Apache-2.0).
 */
import { binaryJudge, type JudgeExample } from './judge.js';

export type EvalCase = { id: string; input?: unknown; expected_output?: string; [k: string]: unknown };
export type AppResult = { output: unknown; retrieval_context?: string[]; tools_called?: { name: string; input?: unknown; output?: unknown }[] };
export type Grade = { passed: boolean; reason: string; score?: number; confidence?: number | null };
export type Grader = (testCase: EvalCase, result: AppResult) => Grade | Promise<Grade>;

const text = (v: unknown) => (typeof v === 'string' ? v : v == null ? '' : JSON.stringify(v));

// --- Example 1: a code check ("missing-order-id"). ---------------------------
const ORDER_ID = /\b[A-Z]\d{2,}\b/;
const ASKS_FOR_ID = /order (number|id)\??/i;
const missingOrderId: Grader = (c, r) => {
  const failed = ORDER_ID.test(text(c.input)) && ASKS_FOR_ID.test(text(r.output));
  return { passed: !failed, reason: failed ? 'Asked for the order number after the user gave it.' : 'OK.', score: failed ? 0 : 1 };
};

// --- Example 2: a structural check ("bad-json"). -----------------------------
const badJson: Grader = (_c, r) => {
  let data: Record<string, unknown>;
  try {
    data = JSON.parse(text(r.output));
  } catch (error) {
    return { passed: false, reason: `Not valid JSON: ${(error as Error).message}`, score: 0 };
  }
  const missing = ['answer', 'sources'].filter((k) => !(k in data));
  return { passed: missing.length === 0, reason: missing.length ? `Missing fields: ${missing.join(', ')}` : 'Valid JSON with required fields.' };
};

// --- Example 3: an LLM judge ("invented-policy"). ----------------------------
// Few-shot examples come from the validate-graders TRAIN split only.
const INVENTED_POLICY_EXAMPLES: JudgeExample[] = [];

const inventedPolicy: Grader = async (_c, r) => {
  const { critique, verdict } = await binaryJudge({
    criterion: 'Does the reply state a return window, fee, or eligibility rule that is not in the policy text?',
    passDefinition: 'Every window, fee, and rule in the reply appears in the policy text, or the reply states none.',
    failDefinition: "The reply states a window, fee, or rule the policy text doesn't contain, or contradicts it.",
    fields: {
      'Policy text': (r.retrieval_context ?? []).join('\n\n') || '(none retrieved)',
      'Assistant reply': text(r.output),
    },
    examples: INVENTED_POLICY_EXAMPLES,
  });
  return { passed: verdict === 'pass', reason: critique, score: verdict === 'pass' ? 1 : 0 };
};

export const GRADERS: Record<string, Grader> = {
  'missing-order-id': missingOrderId,
  'bad-json': badJson,
  'invented-policy': inventedPolicy,
};
