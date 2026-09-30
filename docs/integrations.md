# Framework integrations

`confident-trace` instruments common SDKs and frameworks automatically once
`init()` runs (called for you by `setup_tracing()` / `setupTracing()`). The
table covers the frameworks we see most. For anything else, see the
[confident-trace README](https://github.com/confident-ai/confident-trace).

## Python

| Framework | What to do |
|---|---|
| OpenAI, Anthropic, Google GenAI, AWS Bedrock (boto3) | Nothing beyond `init()`. |
| LangChain, LangGraph, Deep Agents | Nothing beyond `init()`; the callback bridge is registered automatically. |
| LlamaIndex, CrewAI, Agno, smolagents | Nothing beyond `init()`. Model calls come from the provider integration; framework steps come from the framework's own instrumentation. |
| OpenAI Agents SDK | `pip install "confident-trace[openai-agents]"`, then `init()`. |
| Pydantic AI, Strands, Google ADK, Microsoft Agent Framework, AgentCore, LiveKit Agents, Claude Agent SDK | Native OpenTelemetry; `init()` exports their spans. Some need the framework's own tracing switched on (check its docs). |
| LiteLLM, OpenRouter, Portkey | Nothing beyond `init()`. Proxied gateways: pass `litellm_proxy_urls=[...]` (and similar) to `init()`. |

Limit what's instrumented with `instrumentations=("openai", "langchain")`.
Pass `instrumentations=()` when another instrumentor already covers the SDK.

## Node.js (22+)

Automatic mode needs both `init()` and the preload flag on the start command:

```bash
node --import confident-trace/register dist/index.js
node --import tsx --import confident-trace/register src/index.ts
```

| Framework | What to do |
|---|---|
| OpenAI, Anthropic, Google GenAI, Vercel AI SDK, LangChain, LangGraph, Mastra, OpenAI Agents | `init()` + preload. |
| Bundled apps (Webpack, Vite, Next.js server bundles) | The preload can't see bundled SDKs. Use `init({ instrumentations: [] })` plus manual adapters: `instrumentOpenAI(client)` from `confident-trace/openai`, `instrumentAnthropic(client)` from `confident-trace/anthropic`. |
| LangChain / LangGraph (manual) | `new ConfidentLangChainCallbackHandler()` from `confident-trace/langchain`, or `new ConfidentLangGraphCallbackHandler()` from `confident-trace/langgraph`, passed in `callbacks`. |
| Vercel AI SDK (manual) | `createVercelAITracer()` from `confident-trace/vercel-ai`, passed to the AI SDK's OpenTelemetry integration. |
| OpenAI Agents (manual) | `setTraceProcessors([new ConfidentOpenAIAgentsProcessor()])` with the processor from `confident-trace/openai-agents`. |
| Existing OTel provider | `createSpanProcessor()` from `confident-trace/otel` in the provider's `spanProcessors`. |

`runtime.getInstrumentationStatus()` shows whether the preload registered and
which integrations attached.

## Conversations

Set the same `thread_id` (Python) / `threadId` (Node) on every turn of a
conversation. In Python, `ct.turn(thread_id=...)` starts a fresh trace per
turn; in Node, `turn({ threadId }, fn)` does the same.

## Content capture

Content capture is on by default and truncated at 16 KiB per attribute.
`init(capture_content=False)` / `init({ captureContent: false })` records
structure only. Redactors run before anything is serialized: Python takes a
global `redact=` on `init()`; Node takes `redact` per `span()`/`withSpan()`
scope, inherited by nested scopes.
