# Find realistic inputs

## Reuse first

Inventory available cases, logs, trace exports, incident reports, support tickets, thumbs-down feedback, and expert examples. Read the app prompt, tools, and documentation to understand the task, not to invent a benchmark from scratch.

For each source record where it lives, who can grant access, available timestamps, what identifies a conversation, and whether the content can be retained or uploaded. Prefer existing connectors or an authorized read-only query over scraping unrelated systems. Do not send messages requesting data unless the user authorizes that communication.

Before pulling production content, resolve sensitive fields and retention. Options include sanitized exports, synthetic rewrites preserving failure structure, or source IDs with authorized runtime retrieval. A runtime retrieval design must enforce the promised handling: temporary files, logs, screenshots, and traces can otherwise persist supposedly ephemeral content.

## Sample for discovery

Cover task type, user intent, language, conversation depth, tool usage, retrieval behavior, length, and known trouble spots as relevant. Include random normal traffic alongside complaint-driven and diverse samples. Cluster only if simple stratification is inadequate. Record the selection rule and source window.

A hand-curated discovery batch is not a prevalence estimate. To estimate production failure rate use a representative random/probability sample, or known stratum weights and an appropriate estimator. Never carry a complaint-heavy denominator into a production headline.

## Synthetic gaps

Start with real or expert-written examples and a statement of difficulty. Identify two or three relevant dimensions, such as task × ambiguity × policy exception. Propose combinations and have the domain owner remove unrealistic ones. Generate natural-language inputs in a separate pass; deduplicate and review realism before executing the real app.

Preserve a `synthetic` source marker and the generation rationale. Generated expected answers need independent verification. For multi-turn agents define the scenario, initial state, user behavior, and final outcome; a single QA pair may not exercise the failure.

## Stop conditions

Stop collecting when the agreed review batch is ready, source authorization is exhausted, or new examples no longer reveal useful coverage. Explain gaps. More examples are not automatically more signal, and larger batches do not replace a reviewer.
