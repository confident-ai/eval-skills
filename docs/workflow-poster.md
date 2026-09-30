# From evidence to better AI

Text companion to the [workflow poster](../assets/eval-workflow-poster.png).

Start at your current stage. Build trust before optimizing.

## Where are you starting?

| Current state | Next action |
| --- | --- |
| In production? | Use real traffic and incidents. Otherwise, start with a runnable prototype. |
| Already tracing? | Inspect a real trace. If none exists, capture one locally. |
| Have a dataset? | Audit coverage and provenance. Fill gaps with realistic cases. |
| Have review notes? | Analyze existing annotations. Otherwise, review examples first. |
| Already have evals? | Validate the graders and baseline. Reuse what you can trust. |

Enter at the first missing piece; skip stages supported by trustworthy evidence. A prototype that cannot run yet can support scenarios and an evaluation specification, but not a measured baseline.

## The evaluation workflow

1. **Inspect evidence.** Read inputs, outputs, tools and context. Deliver a trace you can explain.
2. **Review examples.** Collect human notes on what failed and why it matters. Deliver durable annotations.
3. **Analyze errors.** Group, refine and prioritize failure modes with a reviewer. Deliver an evidence-linked taxonomy.
4. **Build trusted evals.** Curate cases. Validate checks against human judgment. Deliver calibrated graders and a reproducible baseline.
5. **Descent.** Test one hypothesis. Check regressions. Keep or revert. Deliver a measured improvement when supported by the evidence.
6. **Maintain.** Catch regressions and bring new production failures back into review. Deliver fresh evidence.

New failures reopen review. This is an iterative process; existing trustworthy evidence lets you enter later in the loop.

Human judgment defines quality. Evals measure it. Descent improves it.
