# SandSync Architecture

> **Estimated reading time:** 8 minutes

## What is SandSync?

SandSync is a multi-agent AI storytelling app built for the PowerSync hackathon (March 2026). It generates Caribbean folklore stories with AI-narrated audio, illustrated chapters, and offline-first sync via PowerSync. The codebase is fully open source at `github.com/reddinft/sandsync`.

We're using it throughout this course because it's a real production system — not a toy app built for demos. It has real tradeoffs, real bugs, and real observability needs.

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│                   SandSync Web App                  │
│        TanStack Router + React + PowerSync          │
│                 (Offline-first sync)                │
└──────────────────────┬──────────────────────────────┘
                       │ REST + PowerSync
┌──────────────────────▼──────────────────────────────┐
│                 sandsync-api (Fly.io syd)            │
│           Bun + Mastra Framework + Hono              │
│                                                     │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐             │
│  │  Anansi │  │  Ogma   │  │Firefly  │             │
│  │Storytell│  │Language │  │Builder  │             │
│  │er Agent │  │Guardian │  │ Agent   │             │
│  └────┬────┘  └────┬────┘  └────┬────┘             │
│       │            │            │                   │
│  ┌────▼────────────▼────────────▼─────────────┐    │
│  │           story-pipeline.ts                 │    │
│  │    Mastra workflow: draft→review→enrich      │    │
│  └─────────────────────────────────────────────┘    │
└──────────────────────┬──────────────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         │             │             │
┌────────▼───┐ ┌───────▼────┐ ┌─────▼──────┐
│  Supabase  │ │  Groq API  │ │  fal.ai    │
│  Postgres  │ │ Llama 3.1  │ │ FLUX/Wan   │
│  + Storage │ │  8B Inst.  │ │ Image/Vid  │
└────────────┘ └────────────┘ └────────────┘
```

## The Agent Team

SandSync uses a named-agent pattern inspired by Caribbean mythology:

**Anansi** (Storyteller) — Primary story generation agent. Uses `claude-3-haiku` to draft chapter text based on the story prompt, character list, and previous chapters. Anansi is fast and creative but sometimes takes liberties with cultural accuracy.

**Ogma** (Language Guardian) — Quality review agent. In Irish mythology, Ogma invented the Ogham script and was the god of eloquence. In SandSync, Ogma reviews Anansi's drafts for prose quality and cultural authenticity. Uses a **provider cascade**: `ollama (qwen2.5:latest, if local)` → `groq (llama-3.1-8b-instant)` → `anthropic (claude-haiku)`.

**Firefly** (Builder) — Enrichment agent. Generates image prompts, triggers the fal.ai FLUX pipeline, and assembles the final chapter with media URLs.

## The Provider Cascade

The most interesting observability challenge in SandSync is Ogma's provider cascade. Here's the actual code:

```typescript
function resolveOgmaModel() {
  if (process.env.OLLAMA_BASE_URL) {
    const modelName = process.env.OLLAMA_MODEL || "qwen2.5:latest";
    const ollama = createOllama({ baseURL: process.env.OLLAMA_BASE_URL + "/api" });
    return { model: ollama(modelName), name: modelName, provider: "ollama" };
  }
  if (process.env.GROQ_API_KEY) {
    const groq = createGroq({ apiKey: process.env.GROQ_API_KEY });
    return { model: groq("llama-3.1-8b-instant"), name: "llama-3.1-8b-instant", provider: "groq" };
  }
  return { model: anthropic("claude-haiku-20240307"), name: "claude-haiku-20240307", provider: "anthropic" };
}
```

This creates an observability problem: **which provider was actually used?** Without instrumentation, a slow Ogma call could be slow Ollama, slow Groq, or slow Anthropic — and you'd have no way to know from metrics alone.

## The Observability Gap

Before adding OTEL, SandSync's observability looked like:
- ✅ Health endpoint: `GET /health` → `{ ok: true, mastra: true, supabase: true }`
- ✅ Fly.io machine metrics (CPU, memory, restarts)
- ❌ No per-request latency breakdown
- ❌ No provider attribution for slow requests
- ❌ No token cost tracking
- ❌ No error classification (is it Groq failing or Anthropic failing?)
- ❌ No story quality metrics

A typical "Ogma is slow" incident would show up as: users reporting slow story generation. With no traces, debugging means adding console.log and reproducing the issue. With traces, you open Langfuse and immediately see whether it was Ollama timing out (>10s), Groq hitting rate limits (429), or Anthropic being slow (unusual).

## What We Instrumented

The OTEL layer in SandSync (`apps/api/src/telemetry.ts`) wraps:

| Span Name | Provider | Key Attributes |
|---|---|---|
| `deepgram.transcribe` | Deepgram | `audio.duration_ms`, `story_id` |
| `fal.image_generate` | fal.ai | `model`, `story_id`, `chapter` |
| `fal.video_generate` | fal.ai | `model`, `story_id`, `chapter` |
| `groq.generate` | Groq | `model`, `story_id`, `agent` |

Plus Langfuse SDK generations for every Anansi/Ogma/Firefly LLM call with token usage, cost, and model attribution.

## What the Data Reveals

In the next two lessons we'll walk through real (redacted) production traces and look at what we actually found — including a latency surprise in the Ogma cascade and an unexpected token cost pattern in Anansi's drafts.

## Summary

- SandSync is a 3-agent system: Anansi (draft) → Ogma (review) → Firefly (enrich)
- Ogma's provider cascade (ollama → groq → anthropic) creates attribution ambiguity without traces
- Pre-instrumentation: only health endpoint + platform metrics
- Post-instrumentation: per-span latency, provider attribution, token cost, error classification
