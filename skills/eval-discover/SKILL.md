---
name: eval-discover
description: Find realistic AI application examples and conduct human-led trace review to discover failure modes. Use before inventing quality metrics; supports managed review or an AI-built local annotation UI.
license: Apache-2.0
metadata:
  author: Confident AI
  version: "1.0.0"
---

# Discover failures with a human

Read [the operating agreement](references/workflow.md), [data sourcing](references/data-sourcing.md), and the selected surface: [managed](references/managed.md) or [local review](references/local-review.md).

## Assemble evidence

Reuse existing traces and review notes. Seek production examples, complaints/incidents, support tickets, expert examples, and targeted synthetic variations in that order as practical. Ask about unresolved source access and retainability before pulling content. Inspect one real execution before a new managed connection.

Create a diverse discovery sample. Include ordinary traffic and random exploration alongside difficult examples; cluster only when it helps. Explain which dimensions the sample covers and which it misses. Fifteen to twenty-five examples can start a review, but stop/grow based on discovery saturation and domain breadth, not a universal count.

## Review loop

1. Show full behavior in its natural form, not a raw JSON cell. Start with open-ended notes: what went wrong, what should have happened, and why it matters.
2. Save human observations immediately. The agent groups them into named failure modes with definitions, evidence IDs, quotations, and ambiguity notes. Let the human revise the grouping.
3. Alternate breadth (new task types) and depth (more instances of a known failure). Revisit earlier examples when the meaning of failure changes.
4. After several human-reviewed records establish a category, optionally delegate one category per background analyzer to find candidates. Without delegation, scan sequentially. Reviewers accept or dismiss suggestions; suggestions never become human ground truth automatically.
5. Track confirmed versus suggested findings, reviewed coverage, and new-category discovery. Pause when further review mostly repeats known categories, then propose the next missing coverage or curation step.

Do not monitor indefinitely or claim a background watcher persists after the session ends. Local autosave must work independently of the agent. Resume from saved annotations and revision IDs on the next turn.

## Exit artifact

Deliver a failure taxonomy with concrete examples, impact, uncertainty, and proposed checks. Separate discovery counts from prevalence estimates. Keep review notes and taxonomy linked to raw traces. Confirm criteria with the domain owner before creating graders. The next step is curated cases and validation labels, not a generic metric bundle.
