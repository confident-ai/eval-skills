# Validate the measurement

A judge is a fallible classifier, even when its output is confident. Define what matters before selecting a model.

## Labeling protocol

Select independent examples with both passing and failing behavior. Have a domain owner label each criterion without seeing the automated verdict. Record uncertain labels separately and resolve ambiguous definitions before fitting thresholds. If multiple experts disagree, reconcile the criterion; do not hide disagreement in a majority vote without explanation.

Separate examples used in judge prompts from development calibration and untouched final validation. Group related conversations/documents before splitting. Balance examples enough to inspect each class, but do not claim a balanced calibration set represents production prevalence. No universal sample count guarantees acceptable uncertainty.

## Measurements

Report raw confusion counts with Pass as the positive class:

- True positive rate: TP / (TP + FN), agreement on human passes.
- True negative rate: TN / (TN + FP), agreement on human failures.
- False pass: human Fail, judge Pass.
- False fail: human Pass, judge Fail.

Missing denominators are undefined, not zero. Explain what error is costly for this application and agree on acceptable uncertainty. Use confidence intervals and show class counts. For correlated examples use group-aware uncertainty. Higher point estimates alone do not establish a better judge.

Iterate only on development evidence. Review disagreement traces and reasons. Refine criteria, prompt examples, or judge choice; then run final validation once. If it fails, return with new development/final evidence rather than repeatedly tuning against the same test labels.

For score-based checks, lock thresholds on development labels. For pairwise judges randomize presentation order, allow ties/both-bad, and freeze references. Audit order sensitivity and judge failures.

## Optional rate correction

If estimating population pass rates using a calibrated binary judge, a correction such as `(observed_pass_rate + TNR - 1) / (TPR + TNR - 1)` requires stable class-conditional error rates between validation and production and a denominator safely away from zero. It is not a universal repair for biased sampling or domain drift. Propagate uncertainty from both validation and production samples. Report raw and adjusted estimates with assumptions; skip correction when those assumptions are not defensible.

## Before approval

Exercise known pass/fail examples, empty output, an unrelated confident answer, incomplete evidence, and attempted instructions inside candidate text. Verify parse failures become grader errors, not arbitrary grades. Show the human several scored outputs with evidence and reasons. The grader remains provisional until disagreement and uncertainty are acceptable for the intended decision.

Save criterion version, judge identity/configuration, prompt examples, split IDs, threshold, raw verdicts, human labels, uncertainty, and limitations. If the judge or mode changes, regrade stored outputs and calibrate again. Jev confidence is decisiveness, not measured truth.
