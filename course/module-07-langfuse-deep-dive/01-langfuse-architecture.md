# Langfuse Architecture

> **Estimated reading time:** 9 minutes

## Overview

Langfuse is an open-source observability platform built specifically for LLM applications. Unlike general-purpose APM tools that were retrofitted for AI, Langfuse was designed from the ground up around the primitives that matter for language models: traces, generations, prompts, scores, and datasets.

In this lesson we'll walk through what Langfuse actually is under the hood — its data model, ingestion pipeline, and how it fits into a broader observability stack.

## The Core Data Model

Langfuse organises data around five concepts:

**Traces** are the top-level container. One trace = one user request or job. A trace has an `id`, `name`, optional `userId`/`sessionId` for grouping, `input`/`output` fields, metadata, and tags. Every other object belongs to a trace.

**Spans** are operations within a trace. They have a `startTime`, `endTime`, and `name`. They can be nested — a trace for "generate story chapter" might have spans for `ogma.review`, `imagen.generate`, `supabase.upsert`.

**Generations** are a special type of span for LLM calls. They extend spans with LLM-specific fields:
- `model` — the model used (`claude-3-haiku-20240307`, `llama-3.1-8b-instant`)
- `modelParameters` — temperature, max_tokens, etc.
- `input` / `output` — the actual prompt and completion
- `usage` — `inputTokens`, `outputTokens`, `totalTokens`
- `promptName` + `promptVersion` — links to the prompt registry

**Scores** are evaluation signals attached to any trace or generation. They can be numeric (e.g. quality: 0.87) or categorical (e.g. hallucination: "none"). Scores come from: LLM-as-a-judge, human annotation, or automated rule checks.

**Datasets** are collections of input/output pairs used for evaluation runs. You define expected outputs, run your pipeline against the dataset, and score the results.

```
Trace
├── Span: pipeline.run
│   ├── Generation: anansi.draft (model: claude-haiku, tokens: 847)
│   ├── Generation: ogma.review (model: groq/llama-3.1-8b, tokens: 312)
│   └── Span: imagen.generate
│       └── Span: supabase.upload
└── Score: quality (0.82, source: llm-judge)
```

## Ingestion Pipeline

Langfuse receives data via three paths:

**SDK (recommended)** — The `langfuse` npm/Python package buffers events in memory and flushes them to `POST /api/public/ingestion` in batches. Flushing is async and non-blocking — it won't slow down your request path.

**OTEL (OTLP)** — Since Langfuse v3.22.0, it accepts OpenTelemetry spans at `/api/public/otel`. Spans are mapped to Langfuse's data model using `gen_ai.*` semantic conventions. This is ideal if you're already using OTEL instrumentation.

**REST API** — Direct POST to `/api/public/traces`, `/api/public/generations`, etc. Useful for backfilling data or integrations that don't need SDK overhead.

Once received, events are:
1. Validated and deduped by `id`
2. Persisted to ClickHouse (analytics) + Postgres (metadata)
3. Indexed for search and filtering
4. Aggregated for cost/usage dashboards

## Self-Hosted vs Cloud

Langfuse is fully open source (MIT licensed). The self-hosted and cloud versions are functionally identical — the only difference is who operates the infrastructure.

| | Self-Hosted | Cloud (Hobby) | Cloud (Pro+) |
|---|---|---|---|
| Cost | Your infra costs | Free | $59/mo |
| Data privacy | Complete | EU/US region | EU/US region |
| Setup | Docker Compose (20 min) | Instant | Instant |
| Trace limit | Unlimited | 50k/mo | Unlimited |
| Prompt management | ✅ | ✅ | ✅ |
| LLM-as-judge eval | ✅ | ✅ | ✅ |
| SSO | ✅ (SAML) | ❌ | ✅ |

For **production systems with sensitive data** (patient records, financial data), self-hosted is the default choice. For hackathons, internal tools, and early-stage products, Cloud Hobby or Pro is faster to get started.

## The Langfuse UI Tour

The web UI is the primary way teams explore trace data. The key views:

**Traces** — searchable table of all traces. Filter by userId, sessionId, tags, date range. Click into a trace to see the full span tree with timing waterfall.

**Generations** — dedicated view for LLM calls. Shows model distribution, token usage, cost over time, latency percentiles. This is where you spot expensive models or token bloat.

**Prompts** — version-controlled prompt registry. Create a prompt, assign it a version, reference it from the SDK with `langfuse.getPrompt("story-draft", { version: 2 })`. Changes are tracked; you can A/B test prompt versions.

**Scores** — aggregate view of evaluation scores. Track quality trends over time, compare scores across model versions.

**Datasets** — manage evaluation datasets and run benchmarks.

**Dashboard** — customisable overview. Cost trends, error rates, p99 latency, model usage breakdown.

## How Langfuse Fits in the Stack

Langfuse is not a replacement for Prometheus/Grafana or distributed tracing — it's a complement. A well-instrumented LLM application typically has both:

```
Application
├── OpenTelemetry SDK
│   ├── → Langfuse (via OTLP) — LLM-specific: prompts, generations, scores, cost
│   └── → Tempo/Jaeger — distributed traces for infrastructure (DB, cache, queues)
├── Prometheus metrics — RED metrics, custom business metrics
└── Structured logs → Loki — error context, audit trail
```

Langfuse excels at the LLM layer. For everything else, use the purpose-built tools.

## Summary

- Langfuse's data model: **Traces → Spans → Generations**, with **Scores** and **Datasets** for evaluation
- Ingestion via SDK (buffered), OTEL (OTLP endpoint), or REST
- Self-hosted and Cloud are functionally identical; choose based on data sensitivity and ops capacity
- Langfuse is a complement to, not replacement for, general-purpose observability tools
