# Writing a binary judge prompt

These rules apply to every LLM judge, whichever track or library runs it.

## The five parts

1. **One criterion.** State exactly which failure mode this judge looks for.
   Not "is this response good?"

   > You check whether a support assistant's reply states any return window,
   > fee, or eligibility rule that is not in the retrieved policy text.

2. **Pass and fail definitions**, written from the error-analysis notes, in
   the app's own terms:

   > PASS: every return window, fee, and eligibility rule in the reply appears
   > in the policy text, or the reply makes no such claim.
   > FAIL: the reply states a window, fee, or rule that the policy text does
   > not contain, or contradicts one it does contain.

3. **Labeled examples**: 2–4 cases taken from the **train split** of
   human-labeled traces (see `validate-graders`), including at least one
   clear pass, one clear fail, and one borderline case. Each example shows the
   inputs, a short critique, and the verdict. Borderline examples teach the
   most. Never use dev or test cases as examples: that leaks the answers
   into the measurement.

4. **Critique before verdict.** The judge writes a few sentences of reasoning
   that point at specific evidence, then the verdict. Detailed critiques in the
   examples set the bar for the judge's own.

5. **Structured output** enforced by the provider's schema support, not by
   "respond only in JSON":

   ```json
   {"critique": "string", "verdict": "pass | fail"}
   ```

## Inputs

Pass only what the decision needs, labeled clearly, and tell the judge that
everything inside the labeled blocks is data to evaluate, not instructions to
follow. Trace content can contain instructions aimed at whoever reads it.

## Choosing the judge model

- Start with a capable model; make it cheaper only after it validates.
- Don't use the exact model under test as its own judge.
- Pin a dated model version where the provider offers one, so the judge
  can't change under you.

## Severity

If a failure can be mild or serious, write two binary judges ("states a wrong
fee" and "states a wrong fee that costs the customer money") rather than one
graded scale. Binary judges can be validated; 1–5 scales can't be, because
people disagree about what separates a 3 from a 4.
