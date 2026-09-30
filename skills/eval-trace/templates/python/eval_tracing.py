"""Tracing setup for eval-skills. Call ``setup_tracing()`` once at startup.

Where traces go is chosen by an environment variable, so switching between
local files and Confident AI never needs a code change:

    EVAL_SKILLS_TRACE_MODE=confident  send to Confident AI (needs CONFIDENT_API_KEY)
    EVAL_SKILLS_TRACE_MODE=local      write OTLP/JSON lines to .eval/default/traces/
    EVAL_SKILLS_TRACE_MODE=off        no tracing

When the variable is unset, traces stay local even when a managed API key exists.
Inspect a real execution before explicitly selecting the managed destination.

Part of eval-skills (Apache-2.0). Copy next to ``local_exporter.py``.
"""

from __future__ import annotations

import os

import confident_trace as ct

try:  # works whether this file is imported as part of a package or not
    from .local_exporter import JsonlSpanExporter
except ImportError:
    from local_exporter import JsonlSpanExporter


def trace_mode() -> str:
    mode = os.getenv("EVAL_SKILLS_TRACE_MODE", "").strip().lower()
    if mode in {"confident", "local", "off"}:
        return mode
    if mode:
        raise ValueError("EVAL_SKILLS_TRACE_MODE must be local, confident, or off")
    return "local"


def setup_tracing(service_name: str = "ai-app", **init_kwargs):
    """Start tracing and return the confident-trace runtime (or None when off).

    Extra keyword arguments go to ``confident_trace.init`` unchanged, for
    example ``instrumentations=("openai",)`` or ``redact=my_redactor``.
    """
    mode = trace_mode()
    if mode == "off":
        return None
    resource = {"service.name": service_name, **init_kwargs.pop("resource_attributes", {})}
    if mode == "confident":
        return ct.init(resource_attributes=resource, **init_kwargs)
    traces_dir = os.getenv("EVAL_SKILLS_TRACES_DIR", ".eval/default/traces")
    return ct.init(
        api_key="",
        exporter=JsonlSpanExporter(traces_dir),
        resource_attributes=resource,
        **init_kwargs,
    )
