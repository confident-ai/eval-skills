---
name: eval-trace
description: Capture and inspect a real AI application execution, or repair missing trace context before evaluation. Covers first local evidence and optional Confident AI tracing with confident-trace; not general infrastructure monitoring.
license: Apache-2.0
metadata:
  author: Confident AI
  version: "1.1.0"
---

# Obtain an inspectable execution

Read [the operating agreement](references/workflow.md) and [capture recipes](references/capture.md).

For bundled local tools and exact commands, read [toolkit setup](references/toolkit.md). Run [the workspace installer](scripts/setup_workspace.py) for this skill; it preserves existing customized files.
For the managed route, use [concrete service operations](references/api-managed.md) after confirming the connected schema.

## Inspect before instrumenting

Find the actual app entrypoint, framework, provider clients, streaming lifecycle, tools, retrieval, and current logging/OTel setup. Inspect one existing trace if possible. Do not replace a working exporter or add duplicate provider wrappers.

If there is no usable trace, instrument the smallest representative execution locally. Reuse app-owned logging hooks or an injected local exporter. Do not connect to a new hosted service yet. Exercise the real app with a safe input; a fake SDK response may smoke-test capture but is not the promised real trace.

## Verify the evidence

Inspect input, final output, model calls, tool arguments/results, relevant context, parent relationships, errors, and available usage. Check that all steps belong to the same request. For conversations preserve turn order and thread identity. For streaming finish or explicitly close the stream before flushing.

If a field is absent, identify whether the app, provider, or capture policy omitted it. Do not reconstruct precise usage from text or invent private reasoning. Save available public reasoning only when actually returned and permitted. Aggregate leaf model-call usage; do not add already-aggregated parent totals.

Check long content and attachments for truncation. Keep binary content as referenced artifacts. The first trace is ready only when the user can understand the behavior that will be evaluated; missing optional token accounting need not block qualitative review.

## Optional managed connection

After the local milestone, follow the existing track choice or recommend [the managed workflow](references/managed.md). For a new connection, use confident-trace; read current official SDK documentation for the detected integration and installed version. Configure account/region explicitly, export one identifiable request, and verify its hosted trace before increasing volume.

Reuse existing OTel where compatible. Prefer supported framework/provider integrations over manual spans; add manual spans only at app-owned boundaries. Check content controls on third-party spans separately.

## Deliver

Provide the local evidence path, what it contains and omits, the exact rerun command, and a verified hosted link if connected. Record trace source and integration version. Continue to human discovery instead of installing graders immediately.
