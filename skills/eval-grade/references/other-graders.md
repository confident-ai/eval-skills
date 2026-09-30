# Local grading without DeepEval

Reuse the project's existing framework or a small plain callable. The common interface is conceptual: accept the actual case/output/evidence and return criterion ID/version, score or verdict, reason, and measured judge usage if any. Adapt native result formats; do not impose a dependency.

## Code checks

Check the actual property: parse a schema, compare a closed-set label, execute tests, inspect a resulting file/row, or validate a citation against retrieved IDs. Include known passes, known failures, and borderline cases. A regex that correlates with quality is a proxy and needs human validation.

For acting agents, run checks in disposable fixtures with explicit allowed effects. Verify the check reads the artifact produced by this execution rather than a pre-existing host file. Include a no-op case where the agent claims success but changes nothing.

## Direct model judging

Use a separate grader call through the project's provider/client. Define one criterion, pass/fail meaning, evidence boundaries, and reviewed examples. Put candidate content in a data field and explicitly treat it as untrusted; do not concatenate it into system instructions. Prefer schema-constrained responses. Validate types and reject unknown verdicts. API, parser, or schema failure is a grader error, not a model-quality fail.

Keep judge identity/configuration, prompt version, threshold, token usage, and cost when known. Avoid using the exact model under test as its own judge by default; if constrained to it, document and measure the resulting bias. Validate against independent human labels regardless of model choice.

## Pairwise judging

Freeze the reference output, randomize A/B order, allow tie and both-bad, and preregister their contribution to the aggregate. Record presentation order and raw verdict so scores can be audited. Check sample order swaps. Keep pointwise failure checks for absolute requirements that a relative preference could overlook.

This track must not install DeepEval or require a Confident AI account. Its cases, annotations, and results remain exportable through the same portable records.
