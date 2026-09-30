---
name: eval-dataset
description: Curate replayable AI eval cases from traces, feedback, or grounded synthetic scenarios; preserve provenance and build leakage-resistant splits. Not a generic dataset generation tool.
license: Apache-2.0
metadata:
  author: Confident AI
  version: "1.0.0"
---

# Build a dataset from evidence

Read [the operating agreement](references/workflow.md), [data sourcing](references/data-sourcing.md), and [artifact records](references/artifacts.md). For hosted storage use [managed guidance](references/managed.md).

## Reuse and curate

Inspect existing cases and ask only what cannot be derived: whether they still match traffic, who verified references, and what decisions the eval must support. Preserve useful cases. Distinguish inputs from reference answers, rubrics, and baseline outputs; `expected` does not always mean a single correct sentence.

For every case retain source, permitted retention, failure/category tags, conversation or source group, necessary attachments/context, and reference origin. Capture the environment/fixture necessary to replay an agent. Keep source records unchanged.

Use confirmed failures as regression examples, but also include normal and negative cases. A challenge suite and a representative benchmark answer different questions; label them separately. Generate synthetic cases only to fill specific gaps and have a knowledgeable reviewer verify realism.

## Protect comparisons

Deduplicate and group related conversations, documents, customers where appropriate, and paraphrase families before splitting. Split by group so related examples do not cross boundaries. Stratify by relevant task/category where enough groups exist; do not select development cases just because their baseline scores are low.

Use development for diagnosis, validation for candidate selection, and a final test slice only once when enough data exists. With a small dataset, reserve a credible holdout if possible; otherwise report exploratory results and collect new confirmation cases. Freeze the split before optimization. Never redraw because scores are inconvenient.

Keep answers in grader-only storage outside an acting model's filesystem and tool reach. Remove public benchmark solution access when relevant. Do not rely on “do not read answers” instructions.

## Review and commit

Show actual cases with inputs, attachments, reference origins, and category counts in the chosen review surface. Confirm relevance and retention before committing production-derived data. Store source identifiers or sanitized substitutes when full records cannot be retained.

Record immutable dataset version/hash, sample purpose, grouping rule, and split IDs. Use the optional eval-run artifact helper to validate exported records and create a reproducible group split, or the existing runner's equivalent. Its simple splitter is not a statistical sampling service; inspect category coverage before locking the manifest.

Deliver the runnable input set, protected reference set, review status, and any coverage gaps. Do not mark unreviewed synthetic references as expert-approved.
