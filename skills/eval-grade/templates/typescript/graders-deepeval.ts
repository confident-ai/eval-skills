/**
 * Graders for the local track, using DeepEval metrics as standalone graders.
 *
 * Copy to .eval/default/graders/graders.ts. Replace the examples with one grader per
 * failure mode (ids from .eval/default/eval-skills.json). Every grader follows the
 * eval-skills grader contract and throws (instead of returning a fail) when it
 * can't decide.
 *
 * Judge mode comes from EVAL_SKILLS_JUDGE_MODE:
 *   jev  -> DeepEval evalMode "system_one" (Jev decides; needs TYPESAFE_API_KEY and @typesafe-ai/sdk)
 *   llm  -> an LLM judge (set EVAL_SKILLS_JUDGE_MODEL; Anthropic shown below)
 *
 * Part of eval-skills (Apache-2.0).
 */
import { FaithfulnessMetric, GEval, JevEval, Noul } from 'deepeval/metrics';
import { AnthropicModel } from 'deepeval/models';
import { LLMTestCase, SingleTurnParams } from 'deepeval/test-case';

export type EvalCase = { id: string; input?: unknown; expected_output?: string; context?: string[]; [k: string]: unknown };
export type AppResult = { output: unknown; retrieval_context?: string[]; tools_called?: { name: string; input?: unknown; output?: unknown }[] };
export type Grade = { passed: boolean; reason: string; score?: number; confidence?: number | null };
export type Grader = (testCase: EvalCase, result: AppResult) => Grade | Promise<Grade>;

const JUDGE_MODE = process.env.EVAL_SKILLS_JUDGE_MODE ?? 'jev';

/** LLM judge for llm mode. Pass a model object; a bare "claude-..." string is routed to OpenAI. */
const judgeModel = () => new AnthropicModel({ model: process.env.EVAL_SKILLS_JUDGE_MODEL ?? 'claude-sonnet-5-5', temperature: 0 });

const text = (v: unknown) => (typeof v === 'string' ? v : v == null ? '' : JSON.stringify(v));

function toTestCase(c: EvalCase, r: AppResult): LLMTestCase {
  return new LLMTestCase({
    input: text(c.input),
    actualOutput: text(r.output),
    expectedOutput: c.expected_output,
    context: c.context,
    retrievalContext: r.retrieval_context,
  });
}

async function gradeWith(metric: { measure: (tc: LLMTestCase) => unknown; isSuccessful: () => boolean | undefined; score?: number; reason?: string; error?: unknown; confidence?: number | null }, tc: LLMTestCase): Promise<Grade> {
  await metric.measure(tc); // throws on missing fields or API errors; the runner records those separately
  if (metric.error) throw new Error(String(metric.error));
  return { passed: Boolean(metric.isSuccessful()), reason: metric.reason ?? '', score: metric.score, confidence: metric.confidence ?? null };
}

// --- Example 1: a code check (no judge). -------------------------------------
const COMPETITORS = /\b(acme|globex)\b/i;
const mentionsCompetitor: Grader = (_c, r) => {
  const match = text(r.output).match(COMPETITORS);
  return { passed: !match, reason: match ? `Mentions "${match[0]}".` : 'No competitor named.', score: match ? 0 : 1 };
};

// --- Example 2: a custom judgment criterion ("invented-policy"). ------------
const PASS_STATEMENT =
  'Every return window, fee, and eligibility rule stated in the actual output appears in the retrieval context, or the actual output states none.';

const inventedPolicy: Grader = (c, r) => {
  const evaluationParams = [SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.RETRIEVAL_CONTEXT];
  const metric =
    JUDGE_MODE === 'jev'
      ? new JevEval({ name: 'invented-policy', evaluationParams, questions: [new Noul({ statement: PASS_STATEMENT })], threshold: 0.5 })
      : new GEval({
          name: 'invented-policy',
          criteria: 'PASS if every return window, fee, and eligibility rule in the actual output appears in the retrieval context (or none is stated). FAIL otherwise.',
          evaluationParams,
          model: judgeModel(),
          strictMode: true,
        });
  return gradeWith(metric, toTestCase(c, r));
};

// --- Example 3: a built-in metric ("unsupported-answer"). -------------------
const unsupportedAnswer: Grader = (c, r) => {
  const metric =
    JUDGE_MODE === 'jev'
      ? new FaithfulnessMetric({ evalMode: 'system_one', threshold: 0.5 })
      : new FaithfulnessMetric({ model: judgeModel(), strictMode: true });
  return gradeWith(metric, toTestCase(c, r));
};

// --- Example 4: tool use ("wrong-tool"): objective, so plain code. ----------
const wrongTool: Grader = (c, r) => {
  const expected = ((c.expected_tools as { name: string }[] | undefined) ?? []).map((t) => t.name);
  const called = (r.tools_called ?? []).map((t) => t.name);
  const missing = expected.filter((name) => !called.includes(name));
  return { passed: missing.length === 0, reason: missing.length ? `Expected ${missing.join(', ')}; called ${called.join(', ') || 'nothing'}.` : 'Expected tools were called.' };
};

export const GRADERS: Record<string, Grader> = {
  'mentions-competitor': mentionsCompetitor,
  'invented-policy': inventedPolicy,
  'unsupported-answer': unsupportedAnswer,
  'wrong-tool': wrongTool,
};
