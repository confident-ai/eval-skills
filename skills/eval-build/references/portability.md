# Moving between managed and local workflows

Portability means preserving evidence and decisions, not promising identical infrastructure.

Export cases with stable IDs, source trace IDs, inputs, approved reference information, tags, and conversation/group IDs. Export human annotations with authorship, criteria versions, and confirmed/suggested status. Preserve grader definitions, judge versions, thresholds, run configuration, raw output references, scores, reasons, errors, and usage where available.

Preserve failure taxonomy revisions, definitions, annotation-to-mode assignments, unresolved items, and reviewer decisions. Verify mode → annotation → trace links after migration; category confirmation and assignment confirmation are distinct.

Keep original exports unchanged. Write an adapter into the portable contract only for fields actually present. Missing values remain null; missing usage is never zero. Retain vendor metadata in a separate `source` or `metadata` field. Copy any referenced artifacts that otherwise depend on an expiring URL, if permitted, and verify local links.

To move local:

1. Export a small sample and validate IDs, labels, attachments, and result counts.
2. Export the desired evidence with pagination and record source counts/version IDs.
3. Build the local viewer over those records and confirm a human label survives a save/reload/export round trip.
4. Reuse deterministic graders. Reimplement unavailable hosted judges from the preserved specification and calibrate them against the same human labels.
5. Rebaseline when the grading implementation changes. Do not merge scores from different judges into a single trend line.
6. Change future trace export only after local capture is verified; disable the previous export if requested, rather than sending content to both silently.

Hosted permissions, alert rules, reviewer assignment, proprietary grader implementation, and retention policies may need rebuilding. State exactly what was exported and what remains platform-dependent. Do not delete hosted evidence as part of migration unless explicitly requested.

Local workflows use this same contract where useful. Existing JSON, CSV, OTel, or vendor exports need not be rewritten just to satisfy a preference for a new schema; adapters and stable references are sufficient.
