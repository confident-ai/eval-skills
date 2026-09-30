<img src="assets/eval-skills-banner-radial-4s.svg" alt="Eval Skills — an illuminated celestial atlas revealing patterns across a star-filled landscape" width="100%" />

# Eval Skills

**Find real failures. Build evals you trust. Improve what matters.**

Skills for coding agents that guide you from your first inspectable AI execution to human error analysis, validated graders, repeatable experiments, and production feedback. Works with Claude Code, Codex, Cursor, and other assistants that support Agent Skills.

Start with your application's stage, not a metric catalog. Reuse the traces, datasets, evaluators, and review tools you already have. The first useful outcome is one real execution you can understand—not an account setup or a dashboard project.

## Where are you starting?

```mermaid
flowchart TD
    A[Choose one AI feature and its intended outcome] --> B{Already in production?}
    B -->|Yes| C{Already collecting usable traces?}
    B -->|No| D{Runnable prototype?}
    D -->|No| E[Define realistic scenarios and the smallest runnable path]
    E --> C
    D -->|Yes| C
    C -->|Yes| F[Inspect an existing real trace]
    C -->|No| G[Capture one real execution locally]
    G --> F
    F --> H{Enough detail to explain behavior?}
    H -->|No| I[Repair missing inputs, outputs, tools, or context]
    I --> F
    H -->|Yes| J{Already have a dataset?}
    J -->|Yes| K[Audit provenance, coverage, labels, and freshness]
    J -->|No| L[Find real examples and fill evidence gaps]
    K --> M{Already have evals?}
    L --> M
    M -->|Yes| N[Audit graders and human validation]
    M -->|No| O[Review traces and record human observations]
    N --> P{Evidence and grading trustworthy?}
    P -->|No| O
    O --> OA[Analyze annotations into reviewed failure modes]
    OA --> Q[Curate cases and define failure-specific checks]
    Q --> R[Validate checks against human judgment]
    R --> S[Run a reproducible baseline]
    P -->|Yes| S
    S --> T[Descent: reduce failures in bounded experiments]
    T --> U[Check held-out results and regressions]
    U --> V[Maintain CI checks and production feedback]
    V --> O
```

A prototype that cannot run yet can produce scenarios and an evaluation specification. It cannot produce a measured baseline. Production teams with trustworthy evals can go straight to experiments or maintenance.

## Install

Install the suite with the Skills CLI:

```bash
npx skills add https://github.com/confident-ai/codex-eval-skills
```

Or install from a local checkout before publication:

```bash
npx skills add /absolute/path/to/eval-skills
```

For manual installation, copy the desired directories under `skills/` into your assistant's skills directory. Each skill contains its own references; no sibling skill is required to resolve a file link. Install the full suite for automatic handoffs. If only one skill is installed, it explains the next outcome instead of assuming another skill exists.

Start with:

> Use eval-start to inspect this application and help me build evals from real failures.

Already know the task? Invoke a focused skill directly:

> Use eval-discover to help me review these traces and identify failure modes.
>
> Use eval-error-analysis to group our review notes into failure modes and prioritize them.
>
> Use eval-grade to check whether this judge agrees with our expert labels.
>
> Use eval-descent to reduce latency without regressing the validated quality checks.

## Skills

| Skill | Use it when |
| --- | --- |
| [eval-start](skills/eval-start/SKILL.md) | You need the right next step or want to resume an evaluation workflow. |
| [eval-audit](skills/eval-audit/SKILL.md) | Existing evidence, evals, or headline numbers need examination. |
| [eval-trace](skills/eval-trace/SKILL.md) | You need the first real trace or missing diagnostic context. |
| [eval-discover](skills/eval-discover/SKILL.md) | You need realistic data and human-led failure discovery. |
| [eval-error-analysis](skills/eval-error-analysis/SKILL.md) | You have annotations to cluster into reviewed failure modes and priorities. |
| [eval-dataset](skills/eval-dataset/SKILL.md) | You need reusable cases, trustworthy references, and independent splits. |
| [eval-grade](skills/eval-grade/SKILL.md) | You need failure-specific checks calibrated against human judgment. |
| [eval-run](skills/eval-run/SKILL.md) | You need repeatable runs, reliable accounting, and inspectable results. |
| [eval-descent](skills/eval-descent/SKILL.md) | You want controlled application improvements against validated evals. |
| [eval-maintain](skills/eval-maintain/SKILL.md) | You need regression gates, fresh production evidence, or recalibration. |

**Descent** is our bounded improvement loop: choose an evidence-backed hypothesis, test a change, check regressions, and keep or revert it. The name describes reducing failures; the process does not require gradients.

## Three example journeys

**Prototype, no logs.** Run one real request locally. Inspect its full execution. Gather a few expert examples, then generate variations aimed at plausible failures. Review outputs before designing graders. Do not call synthetic scenarios production-representative without evidence.

**Production agent, lots of traces.** Reuse the existing exporter. Sample across customer tasks, failures, and normal traffic. Review in a shared workspace or a fitted local viewer. Human notes become failure categories, and confirmed examples become regression cases. Discovery samples do not estimate production prevalence.

**Existing evals, questionable score.** Recompute the headline from raw results, inspect the grader's false passes and false failures, and verify references. Fix the measurement before optimizing the application. Compare variants using unchanged cases and grader versions.

The runnable [offline example](examples/README.md) exercises the portable format and deterministic grading without credentials. The [workflow scenarios](tests/scenarios.md) cover agent behavior and track selection.

## Choose how the workflow runs

The same process works across three setups. Choose after inspecting a real execution and identifying what you need next.

| Track | What you get | What you maintain |
| --- | --- | --- |
| **Fully managed** | Shared tracing, review, annotation, datasets, and experiment history through [Confident AI](skills/eval-start/references/managed.md), saving agent tokens on custom tooling and making evals simpler to run | Your application and domain-specific quality decisions |
| **Local, managed graders** | An AI-built review UI and local artifacts, with ready-made graders from [DeepEval](skills/eval-grade/references/deepeval.md) | Local UI, runner, storage, and grader configuration |
| **Fully local, build from scratch** | An AI-built review UI, code checks, and custom or existing judges | Local UI, runner, storage, and graders |

Setup instructions and judging-mode choices live in the skills. Local refers to review, storage, and orchestration; model-based graders can still call external services. Preserve your cases, annotations, and results so you can [change setups later](docs/portability.md).

## What this repository provides

Instructions, targeted references, portable interchange examples, and small validation helpers. It does not ship a dashboard, require an eval framework, or promise automatic domain expertise. Most of the work is discovering and understanding failures; grader integration is one part of that process.

- [Artifact contract](docs/artifacts.md): portable evidence and experiment records.
- [Development and validation](CONTRIBUTING.md): tests and contribution expectations.
- [Sources and acknowledgments](ACKNOWLEDGMENTS.md): methodological influences and integration references.
- [License](LICENSE): Apache License 2.0.

The banner's [static PNG](assets/eval-skills-banner.png) is available separately. Its animated wrapper respects reduced-motion preferences.
