# Capture the first trace

Use the bundled Python/TypeScript local OTLP exporters and normalizers described in [toolkit setup](toolkit.md). Both retain original spans for replay and produce normalized records for review. Reuse existing adequate traces instead of adding another SDK unnecessarily.

Default to local capture. `EVAL_SKILLS_TRACE_MODE=confident` explicitly selects hosted export; an API key alone must not switch destinations. Configure redaction before capturing user content. Inspect one real input, output, tool hierarchy, model identity, timing, and available usage before connecting a new managed destination.

For Python, install confident-trace in the app's environment, put `eval_tracing.py` and `local_exporter.py` on its import path, and call `setup_tracing()` before provider imports. Flush/shutdown before reading exports. For TypeScript, use the bundled setup module and the supported `--import confident-trace/register` preload when automatic instrumentation requires it.

Inspect the installed SDK and [integration reference](integrations.md) before modifying an existing OpenTelemetry provider. Empty or incomplete exports are not success. Preserve truncation indicators and missing usage as unknown. The bundled replay CLI has a dry-run mode; uploading production content requires the selected destination and permitted data use.
