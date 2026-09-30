# Offline example

This tiny, intentionally imperfect routing app demonstrates records, code grading, trace links, and resume without network calls. It is not a production benchmark, AI inference, or a substitute for expert annotation.

```bash
python3 examples/offline_eval.py --output /tmp/eval-skills-example
python3 skills/eval-run/scripts/artifacts.py validate /tmp/eval-skills-example
python3 examples/offline_eval.py --output /tmp/eval-skills-example
```

The second run skips completed case/repetition pairs. Two of three cases pass because the toy app misses an invoice request without the word “charged.” Inspect `report.md` and `traces/` in the output directory. Expected labels are synthetic demonstration specifications, not claimed human-review results.

The example fingerprints its source and input cases. A changed fingerprint requires a new output directory. It is deliberately not a general runner: real applications require the timeout, cancellation, retry, fixture, and usage policies in eval-run.

The three independent groups permit demonstrating a split command, but three cases cannot support a trustworthy statistical claim:

```bash
python3 skills/eval-run/scripts/artifacts.py split /tmp/eval-skills-example --output /tmp/eval-skills-splits.json
```

See `tests/scenarios.md` for prototype, production, and existing-eval walkthrough fixtures. Do not mount expected-answer bundles into an acting model's workspace.

## Review and audit fixtures

`fixtures/production-agent/` contains a fictional tool-using policy agent trace. It is production-shaped, not real production evidence. Use it to test whether discovery shows the retrieved policy and identifies the actual contradiction without inventing human labels.

`fixtures/existing-evals/` contains the same fictional behavior with a failing raw result and an intentionally incorrect `claimed-summary.json`. Use it to test whether audit recomputes the result instead of repeating the claimed success rate. These bundles contain no authentic reviewer labels or measured model usage.
