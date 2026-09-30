# Regression and production feedback

## CI

Use the existing test system. Separate fast code checks from paid judge runs. Pin dataset and grader versions. A regression gate needs an owner, baseline, pass rule, missing-data rule, and cost/time limit. Smoke-test intentionally good and bad outputs plus a runner error to verify the check actually blocks or warns as intended.

Never expose secrets to arbitrary pull-request code. Follow the CI provider's trusted-execution model. Do not use a privileged pull-request workflow to execute untrusted changes merely to obtain model credentials. Missing credentials should produce a clearly skipped/incomplete evaluation according to policy, not a fake success.

For managed users inspect [Confident Actions](https://github.com/confident-ai/confident-actions) and use the supported eval gate setup. Verify the generated `confident_eval.py` callback invokes the real application and the gate submits the intended outputs against a pinned dataset. Risk scanning is separate scope.

## Production

Agree on traffic sampling, data handling, cost ceiling, retention, evaluation unit, alert threshold, and responsible person. Conversations need an explicit completion boundary before final-outcome grading. Reference-free checks cannot validate facts that require inaccessible ground truth.

Track representative traffic separately from complaint/failure-triggered review. Keep source-to-case lineage so confirmed production failures become regression cases. Alert only on meaningful changes with sample counts and error context; deduplicate repeated alerts.

## Refresh and handover

New model, prompt, tool, retrieval index, language, or user population can invalidate assumptions. Review fresh traces for failure categories, calibrate on new human labels, and version changes. Preserve stable regression cases alongside a refreshed representative benchmark.

Save the CI command, baseline, sampling rule, reviewers, alert routing, and revalidation triggers. Recurring jobs and external notifications require the user's scheduling/communication authorization. Documentation of a schedule is not proof that it is running.
