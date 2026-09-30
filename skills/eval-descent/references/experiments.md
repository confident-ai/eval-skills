# Controlled improvement

Begin with a trustworthy baseline and an explicit goal: improve a named quality criterion, reduce latency/cost while preserving quality, or migrate a model while recovering behavior. Define protected metrics and meaningful regression limits.

Record editable scope, exclusions, run scope, budget, maximum rounds, and plateau rule before starting. A reasonable default proposal is three rounds, extending only by agreement; plateau detection needs enough comparable rounds and a threshold above measured noise. Never spend past the approved ceiling because an idea seems promising.

Use development traces to propose changes and validation scores to select candidates. Keep final test content and outcomes untouched until final confirmation. If the available evidence cannot support three splits, state the weaker claim, use grouped validation, and obtain new cases for final confirmation rather than renaming repeatedly used validation “test.”

One hypothesis per round: identify the behavior, evidence, intervention, expected wins, and likely regressions. Save source diff and artifact snapshot. If the judge changes, preserve old results and regrade all candidates before ranking. If execution semantics change, rerun comparable app outputs.

Confirm a setting is accepted and reaches the relevant model/subagents. Check engagement separately from quality: for a retrieval fix, did the app retrieve the intended context, and did answers improve? A score jump without an explainable mechanism deserves investigation.

Stalls require categorization: missing capability, grader disagreement, infrastructure, structure/routing, or variance. Choose the next intervention accordingly. Avoid accumulating vague instructions or memorizing nouns from the development cases.

At finish restore the supported winner, run final confirmation, show paired deltas and uncertainty, disclose incomplete spend, and provide before/after evidence. If no improvement clears the decision threshold, say so. Do not automatically merge, deploy, or publish.
