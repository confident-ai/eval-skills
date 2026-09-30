---
name: eval-error-analysis
description: Cluster human review annotations into evidence-linked failure modes, refine a taxonomy with the reviewer, and prioritize errors. Use when review notes already exist, especially for local workflows; this does not generate validated grader labels.
license: Apache-2.0
metadata:
  author: Confident AI
  version: "1.0.0"
---

# Turn annotations into failure modes

Read [the operating agreement](references/workflow.md) and [analysis procedure and artifacts](references/error-analysis.md). For local work, use [local review guidance](references/local-review.md); for an existing managed workflow, use [managed guidance](references/managed.md).

## Start from reviewed evidence

Locate existing annotations, their source traces, sampling rules, and any taxonomy revisions. Preserve original notes and author/status information. Inspect the behavior behind the notes before grouping it. If there are no human observations, prepare a review queue and use `eval-discover` if installed; agent-generated observations remain suggestions.

Reuse a managed platform's existing analysis and exports when available. For either local track, perform the analysis over local records and extend the existing review UI. No grader framework or new hosted connection is required.

## Propose and refine

Group notes by the observable failure and expected behavior. Use semantic search or embeddings only to find candidate neighbors; inspect evidence to decide membership. Similar wording can describe different failures, and different wording can describe the same failure.

Give each proposed mode a stable ID, clear definition, inclusion/exclusion rules, representative evidence, and boundary examples. Allow multiple modes per annotation and an unresolved queue. Separate observed symptoms from hypothesized root causes. Do not force every record into a category or turn a broad label such as “hallucination” into a supposedly actionable taxonomy.

Present groups beside original annotations and traces. Let the reviewer merge, split, rename, move, reject, and confirm proposals. Preserve revision history and reviewer decisions. Human approval of a category does not automatically confirm every assignment or produce per-criterion Pass/Fail labels. If review is unavailable, finish the proposed taxonomy, evidence links, and review queue without claiming confirmation.

## Prioritize and hand over

Count distinct cases per mode and state the reviewed denominator and sampling purpose. Multi-label counts can overlap. Rank using observed frequency, product impact, and uncertainty; rare severe failures must remain visible. Do not infer production prevalence from a discovery sample.

Save a versioned taxonomy, annotation-to-mode mappings, unresolved items, and a concise analysis report using the reference's local artifact convention or an equivalent existing format. Verify evidence links and save/reload/export behavior when changing a UI. Report unverified interactions honestly.

Hand confirmed modes and examples to case curation and grader design (`eval-dataset` and `eval-grade` when installed). With a trusted baseline, use the prioritized development failures to guide `eval-descent`. Keep held-out evidence out of the optimization loop.
