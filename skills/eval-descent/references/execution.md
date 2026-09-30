# Reliable execution

## Run identity

Pin dataset/split, app commit and relevant uncommitted diff, prompt/configuration, grader definition/model/mode, environment and fixture versions, and repetition policy. Compute a run fingerprint from these values. A resume against a changed fingerprint is a new run, not a continuation.

Call the actual production code path through a safe function/endpoint/test wrapper. Stub only side effects or state that prevents safe reproducibility, and state what changed. Avoid reconstructing a separate model call that bypasses retries, tools, or context assembly.

## Attempt accounting

Assign stable case and repetition IDs. Append attempt/error records as they occur and a terminal result when a case/repetition finishes. Do not overwrite attempt costs. On resume, skip only valid terminal records belonging to the unchanged run. Rerunning terminal errors should be explicit, retaining the old attempt history.

Distinguish execution errors, judge errors, timeouts, truncated outputs, refusals, and graded capability failures. Agree before scoring how truncation/refusal affects a task's outcome. Always report their counts. Excluding errors from quality averages must not hide availability failures; show both denominators and error rate.

Retry only eligible transient failures with jitter and a cap. Define whether success-after-retry matches production semantics. Record all attempts; never cherry-pick the best output. Use an overall case deadline independent of stream activity. Cancel or close underlying work where supported; a timeout alone does not guarantee the provider stopped billing.

## Usage and cost

Record usage returned by each leaf model call, including tool-loop calls and separate judge calls. Do not sum parent aggregates with children. Track input/output/cache fields according to provider definitions; they are not universally disjoint. Keep unknown usage null. Estimate cost from actual returned model and current provider rates, recording rate source/date, currency, and whether total spend is complete. Do not assume pricing from one provider applies to another.

Separate app cost, grader cost, failed-attempt cost, and agent-analysis costs where measurable. If analysis costs are unavailable, say the total is partial. Keep latency end-to-end and per-call measurements distinct.

## Reports

Derive metrics from raw result records. For classification use aggregate confusion counts rather than averaging per-row precision. For multiple quality metrics show each with its direction, threshold, and denominator. Show unknown values as unknown, not zero. Render traces and artifacts safely.

Use group/case-level paired differences for variant comparisons. Repetitions estimate variability on fixed cases; they do not create independent new tasks. If a variant creates a stochastic intermediate artifact, repeat that build or run no-change controls before attributing a score change to the patch.

Every displayed score must link back to evidence. Save complete configuration and results so a teammate can rerun without chat history. A partial run needs an explicit completed/expected count and cannot be called final.
