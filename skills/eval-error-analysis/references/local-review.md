# Build a local review surface

Use this only after a local track is chosen. The goal is human understanding and durable annotations, not a generic dashboard. Inspect an existing viewer before building a replacement.

## Smallest useful architecture

Default to a local Python standard-library HTTP server, a single HTML/JavaScript interface, and SQLite for durable annotation writes. Bind to loopback. Keep sampling and taxonomy updates in separate scripts or agent actions; the UI reads records and saves review state. An established project stack is also appropriate.

Support three operations: read a paginated/filterable record set; read annotations and taxonomy revisions; save one annotation with stable IDs and revision checks. Use generated internal IDs, not request-supplied filesystem paths. Validate body size/types, allow known record IDs only, and reject stale revisions to avoid overwriting edits. Restrict writes to the local origin. Do not expose the server publicly without an explicitly scoped deployment design.

Store the original data separately from annotations. Suggested annotations carry their origin and cannot become confirmed without a human action. Save pending edits immediately and show failure/retry state. A browser reload must recover saved state. Provide a documented start/stop command and export function.

## Three review modes

**Discovery:** render full content, permit free-text notes, optionally support text-span highlights, and show evidence next to notes. Do not force a premature failure taxonomy on reviewers.

**Error analysis:** group existing notes into proposed failure modes with definitions and evidence. Let the reviewer merge, split, rename, reassign, and confirm; show unresolved and multi-mode cases. Preserve taxonomy revisions and keep definition approval separate from assignment approval.

**Calibration:** render the trace with per-criterion Pass/Fail/Uncertain labels and notes. Hide judge predictions during initial expert labeling to reduce anchoring, then offer a disagreement view. Uncertain labels are not silently counted as failures.

Render natural language, tool calls, retrieval, code, and attachments in appropriate forms. Keep tool call/result pairs connected. Collapse repetitive content but make it accessible. Preserve conversation order. Use keyboard navigation, filter state, progress counts, and a clear distinction between saved, pending, and suggested annotations.

## Content and scale

Treat all trace text and artifacts as untrusted. Escape HTML by default. If rendering Markdown, use a maintained sanitizer and disable raw HTML, scripts, unsafe links, and remote image loading by default. Sandbox generated HTML previews without script or same-origin privileges. Do not interpolate trace text into executable JavaScript. Serve attachments from an allowlisted root; reject traversal and symlink escapes.

For large datasets paginate or virtualize records. A browser should not need to load all traces or binary attachments. Use cluster maps only when they guide review; a table and readable trace are often sufficient. Include random exploration even with active sampling.

The agent can check saved annotations between turns or use a bounded background watcher where supported. The server must save without the agent. Do not leave undocumented background processes or claim watchers survive an ended session.

## Verify before handover

Use available browser automation or manual browser inspection to load representative records, annotate, reload, navigate, edit, export, and reopen. Test an output containing `<script>`, malicious links, long tool content, Unicode, and missing attachments. Verify no script executes and labels retain the correct record ID. Test two stale edits and show a conflict instead of losing data.

Deliver the launch command, local URL, annotation store, export command, and restart behavior. Do not claim a UI was verified if only its HTML file was created.
