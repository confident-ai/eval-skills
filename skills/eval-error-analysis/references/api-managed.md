# Managed annotation and error analysis

Verified against the available MCP schemas and official documentation on 2026-09-30. No hosted writes or paid evaluations were executed during integration. Other client wrappers may spell fields differently; the connected tool declaration wins.

1. Reuse the selected project, or call `list_projects` and match the user's project. Every other call takes `project_id` plus a `request` object.
2. Call `list_traces` with `request: {pageSize: 25, environment: "production"}` and optional `start`, `end`, `cursor`. Inspect candidates with `get_trace`. Include ordinary traffic as well as difficult cases; discovery counts are not prevalence estimates.
3. Create an authorized queue with `create_annotation_queue`, `request: {name: "Error review", type: "TRACE"}`. Use `THREAD` for conversations; optional `formId` attaches an existing form.
4. Populate it with `add_items_to_annotation_queue`, `request: {queue_id: "<returned-id>", traceUuids: ["<existing-trace-uuid>"]}`; for threads use `threadIds` instead. Queue duplicates are skipped.
5. Give the user the returned platform link when available, otherwise direct them to the queue in their selected project. Humans annotate and explain failures there. Do not create agent-generated feedback as if it came from a human.
6. Track review progress with `list_annotation_queue_items`, `request: {queue_id: "<id>", status: "COMPLETED", limit: 50, offset: 0}`. Read notes with `list_annotations`, filtering by `traceUuid` or `threadId` and paging with `page`/`pageSize`.
7. Have the user open Error Analysis in that queue and review the platform's proposed failure modes and recommended metrics. There is no error-analysis result operation in the inspected MCP inventory. Reuse a supported export if exposed; otherwise ask for the reviewed category list, or draft from exported explanations and obtain human confirmation. Do not claim the agent triggered or retrieved a hosted analysis without evidence.
8. Preserve definitions, counts, source IDs, reviewer decisions, and open questions locally for the next stage. Taxonomy confirmation does not replace grader calibration.

REST fallback for queue creation is `POST /v2/annotation-queues` with `name`, `type`, and optional `formId`. Adding trace references uses `POST /v2/annotation-queues/{annotationQueueId}/items` with `traceUuids`. Use a project-scoped key in the `CONFIDENT_API_KEY` header; never put it in saved artifacts.

Sources: [MCP operations](https://www.confident-ai.com/docs/coding-agents/mcp), [create queue](https://www.confident-ai.com/docs/reference/api/v2/annotation-queues/create-annotation-queue), [add items](https://www.confident-ai.com/docs/reference/api/v2/annotation-queues/items/add-annotation-queue-items), and [platform error analysis](https://www.confident-ai.com/blog/launch-week-q1-2026-day-1-error-analysis).
