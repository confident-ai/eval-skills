# Runnable toolkit integration verification

Verified locally on 2026-09-30. This records the integration checks, not a claim of hosted certification.

## Source and scope

The source was frozen at revision `d7ede2d7541801b15fe91ad95dd766da355f1ce8`, including working-tree fixes and its ongoing skill renames. The temporary snapshot records capture time, dirty files, and file checksums; pre-copy and post-copy manifests matched. The original source was not used after capture. Source material included tracing/export/replay, review infrastructure, sampling, graders, calibration, runners, reports, uploaders, monitoring, plugin metadata, and tests.

The source's structural lint encountered transitional rename/link errors. In a disposable copy, aliases for the old skill paths allowed its 27 Python tests to pass without changing the implementations. Destination names, routes, and contracts were integrated independently.

## Checks completed

- Repository validation, synchronized resources, plugin validation, and individual validation of all ten skills.
- Installation of every skill alone in both language configurations, without sibling folders.
- 19 existing portable-contract unittest cases.
- 31 Python toolkit tests, including integration checks for grouping, revisions, reference isolation, usage, exports, and existing workspace preservation.
- TypeScript typechecking and seven runtime tests, including a Python/TypeScript split-equivalence fixture and portable export of TypeScript results.
- Browser acceptance against both local review servers: annotate/reload, conflict handling, uncertain labels, blind labeling, separate category and assignment confirmation, merge/split/reassignment, export, reopening traces, and inert untrusted content.
- Credential-free sample journey through actual local trace capture, normalization, sampling, synthetic reviewer fixtures, taxonomy, curated cases, deterministic grades, baseline and candidate runs, paired comparison, HTML report, and validated portable export. Synthetic review fixtures do not constitute human approval. Three cases do not establish a statistically reliable improvement.

## Limits and follow-up

Managed operation names and the error-analysis handoff were checked against available MCP schemas and official documentation. No hosted projects were modified, no traces were uploaded, and no paid judges were run. REST recipes, real account permissions, hosted result availability, paid calibration, and CI execution on GitHub require separate verification. Platform error analysis remains a user-facing handoff unless a results API is explicitly available and verified.

The local validation environment used Python 3.13 and Node 23; CI additionally targets Python 3.10/3.12 and Node 22. The final npm audit reports 12 moderate advisories in upstream SDK dependencies, with no high or critical advisories after the compatible protobuf patch. The SDKs are dependencies of the test harness, not prerequisites for the standard-library review servers or deterministic examples.

Timeouts bound how long the runner waits; they cannot guarantee cancellation of an external request or worker thread. Unknown provider usage stays unknown. Live providers should supply usage and cancellation support through their adapters.
