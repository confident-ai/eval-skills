# Analyze annotations into failure modes

## Evidence and grouping

Start with the reviewed sample, not a fresh model-generated set of labels. Record source snapshot, annotation IDs, case IDs, trace references, sampling purpose, and excluded or unavailable records. Preserve original human text. Deduplicate imports by stable identity without collapsing independent observations of the same case.

Read each note alongside enough trace context to identify the observed behavior, expected behavior, and impact. Split a compound note into separate analytical observations when useful, retaining its original annotation ID. Record ambiguous or contradicted notes for review; do not silently rewrite them.

Propose groups at a level where a reviewer could decide membership and a concrete check or intervention could follow. Start inductively from observations rather than imposing a metric catalog. For large collections, analyze batches, consolidate candidate definitions across batches, and revisit boundary cases; retain IDs throughout. Search and embeddings can retrieve candidates but do not establish failure meaning.

For example, “ignored the policy” and “invented a 45-day window despite the tool returning 30” can share a mode for contradicting retrieved policy. “No policy was retrieved” needs a separate mode when the evidence shows missing retrieval. Both may produce an incorrect answer, but neither establishes the underlying cause of the other. A single case can exhibit both when its trace supports both. Suggested causes such as prompt ambiguity remain hypotheses until tested.

Review representative members, borderline members, and counterexamples for every proposed mode. Look for categories with inconsistent definitions, categories that always overlap, and miscellaneous groups hiding a new mode. Allow outliers and uncertain assignments. Do not target a predetermined number of clusters.

## Reviewer decisions and local UI

Extend the existing local viewer with a failure-mode list and counts, side-by-side notes and trace evidence, and an unresolved queue. Support merge/split/rename, reassignment, rejection, and confirmation. Save each edit durably with revision checks; preserve the existing annotation text and authorship. The UI must work in both local grading tracks without importing a grader framework.

A mode definition and its individual assignments have separate review states. Confirming a definition does not bulk-approve its members unless the reviewer explicitly chooses that action. Renames preserve IDs; merges and splits create explicit old-to-new mappings and retain prior revisions. Do not rewrite historical reports against a new taxonomy without showing that change.

Check save/reload/export, one merge, one split, and one ambiguous multi-mode assignment. Confirm that each mode still opens the correct annotation and trace and that stale edits cannot overwrite newer decisions. Apply the rendering and local-server protections in [local review](local-review.md).

## Local artifact convention

Reuse existing formats if they preserve these fields. Otherwise save an `analysis/` directory beside the eval bundle. These files supplement the core bundle; the existing bundle validator does not validate this extension.

| File | Required information |
| --- | --- |
| `taxonomy.json` | Schema version, taxonomy ID/revision, source snapshot, modes with stable IDs, names, definitions, inclusion/exclusion rules, example and boundary annotation IDs, proposed/confirmed/retired status, actual reviewer and review time when confirmed, revision lineage |
| `assignments.jsonl` | Assignment ID, annotation ID, case ID, trace reference, mode ID, taxonomy revision, evidence rationale, agent/human origin, suggested/confirmed/rejected/uncertain status, actual reviewer and review time when confirmed |
| `unresolved.jsonl` | Annotation/case IDs, source evidence reference, reason unresolved, candidate mode IDs if any, next review question |
| `report.md` | Sample and exclusions, counts and denominators, priority rationale, confirmed versus proposed findings, unknowns, and next actions |

An assignment can be represented as follows. The IDs are illustrative, not real reviewed evidence:

```json
{"id":"assignment-1","annotation_id":"note-7","case_id":"case-3","trace_ref":"traces/case-3.json","mode_id":"policy-contradiction","taxonomy_revision":1,"rationale":"The note and tool result show a 30-day limit, but the answer states 45 days.","origin":"agent","status":"suggested","reviewed_by":null,"reviewed_at":null}
```

Resolve trace references relative to the eval bundle root, with the same path protections as other artifacts. Before handover, check that assignment IDs are unique, taxonomy revisions and mode IDs exist, annotation-to-case links match their sources, and all referenced evidence resolves. Every input annotation must have an assignment or an explicit unresolved/excluded disposition. Confirmation requires a real reviewer decision. Preserve source export identifiers when importing platform analysis.

## Counts, priorities, and next steps

Report distinct affected cases, not raw note counts. Show confirmed and suggested assignment counts separately and disclose the denominator (for example, 8 of 40 reviewed cases). Multi-label totals may exceed the case count. Repeated runs and multiple notes about one case do not increase the number of independent cases. Discovery counts indicate what appeared in this sample; estimating production rates requires representative sampling and appropriate uncertainty.

Prioritize frequency alongside severity, user impact, and evidence strength. Keep rare severe modes visible rather than multiplying them into an arbitrary score that hides them. Separate a supported failure observation from a speculative repair. Record missing coverage and further examples needed.

Translate reviewed modes into candidate checks and curated cases, retaining mode IDs in criteria metadata. Do not treat taxonomy confirmation as grader calibration: graders still need independent human Pass/Fail labels and validation. New failure modes can reopen discovery. Existing trusted evals can use this analysis to select the next bounded Descent experiment on development data.
