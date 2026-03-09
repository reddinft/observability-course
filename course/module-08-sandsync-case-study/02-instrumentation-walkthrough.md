# Instrumentation Walkthrough

> **Estimated reading time:** 10 minutes

## Overview

In this lesson we'll walk through the actual OTEL instrumentation added to SandSync's API during Phase 2 development. You can follow along in the codebase at `github.com/reddinft/sandsync/apps/api/src/telemetry.ts`.

## The Design Decisions

Before writing a line of code, there were a few choices to make:

**SDK or OTEL?** We chose both. The Langfuse SDK handles LLM generations (where we want model name, token usage, and cost tracking). OTEL handles non-LLM spans (fal.ai image generation, Deepgram audio, Supabase writes) — these don't have LLM semantics, so the SDK's `generation` type doesn't fit.

**Auto or manual instrumentation?** Manual. Auto-instrumentation would capture HTTP calls generically, but we wanted semantic span names (`deepgram.transcribe`, not `POST /v1/listen`), story-scoped attributes (`story_id`, `chapter`), and provider attribution. Manual instrumentation costs more upfront but pays off in trace quality.

**Where to flush?** SandSync is a long-running Bun process on Fly.io, not serverless. We flush on SIGTERM and rely on the 5-second batch processor for regular traffic.

## The withSpan() Helper

The core primitive is `withSpan()` — a generic wrapper that handles span lifecycle, error recording, and status setting:

```typescript
export async function withSpan<T>(
  spanName: string,
  attributes: Record<string, string | number | boolean>,
  fn: (span: Span) => Promise<T>
): Promise<T> {
  const span = tracer.startSpan(spanName, {
    kind: SpanKind.CLIENT,
    attributes,
  });

  try {
    const result = await fn(span);
    span.setStatus({ code: SpanStatusCode.OK });
    return result;
  } catch (err) {
    span.recordException(err as Error);
    span.setStatus({
      code: SpanStatusCode.ERROR,
      message: (err as Error).message,
    });
    throw err;
  } finally {
    span.end(); // always end, even if an error was thrown
  }
}
```

The `finally { span.end() }` is critical. A span that never ends is invisible in trace UIs — the waterfall will have a missing bar and the parent span duration will be wrong.

## Per-Provider Wrappers

Each external API call has a typed wrapper that enforces consistent attribute names:

```typescript
// Deepgram STT
export function deepgramSpan<T>(
  audioDurationMs: number,
  storyId: string,
  fn: (span: Span) => Promise<T>
): Promise<T> {
  return withSpan(
    "deepgram.transcribe",
    {
      "service.name": "deepgram",
      "model": "nova-3",
      "audio.duration_ms": audioDurationMs,
      "story_id": storyId,
    },
    fn
  );
}

// fal.ai image generation
export function falImageSpan<T>(
  model: string,
  storyId: string,
  chapterNumber: number,
  fn: (span: Span) => Promise<T>
): Promise<T> {
  return withSpan(
    "fal.image_generate",
    {
      "service.name": "fal",
      "model": model,
      "story_id": storyId,
      "chapter": chapterNumber,
    },
    fn
  );
}
```

The wrapper approach means callers don't have to think about attribute names. `falImageSpan("fal-ai/flux/schnell", storyId, 3, async () => { ... })` always produces a consistently-named span.

## Calling the Wrappers in Practice

Here's how image generation is instrumented in `imagen.ts`:

```typescript
// Before instrumentation:
export async function generateImage(
  prompt: string,
  storyId: string,
  chapterNumber: number
): Promise<string | null> {
  const result = await fal.subscribe("fal-ai/flux/schnell", {
    input: { prompt, image_size: "landscape_4_3" },
  });
  return result.data.images[0]?.url ?? null;
}

// After instrumentation:
export async function generateImage(
  prompt: string,
  storyId: string,
  chapterNumber: number
): Promise<string | null> {
  return falImageSpan("fal-ai/flux/schnell", storyId, chapterNumber, async (span) => {
    const result = await fal.subscribe("fal-ai/flux/schnell", {
      input: { prompt, image_size: "landscape_4_3" },
    });

    const imageUrl = result.data.images[0]?.url ?? null;

    // Add result attributes to the span after we have them
    if (imageUrl) {
      span.setAttribute("image.url", imageUrl);
      span.setAttribute("image.format", "jpeg");
    } else {
      span.setAttribute("image.generated", false);
    }

    return imageUrl;
  });
}
```

The change is minimal. The existing logic is unchanged — we just wrapped it.

## The Groq Ogma Span

The Ogma agent is the most important span to get right because it's in the critical path of every story generation. Here's the instrumented version:

```typescript
// In the Mastra agent wrapper:
export async function runOgmaWithTracing(
  draft: string,
  storyId: string,
  chapterNumber: number
): Promise<string> {
  return groqSpan(OGMA_MODEL_NAME, storyId, "ogma", async (span) => {
    span.setAttribute("ogma.provider", OGMA_PROVIDER);
    span.setAttribute("chapter", chapterNumber);

    const result = await ogma.generate([
      { role: "user", content: draft }
    ]);

    // Record which provider actually handled this
    span.setAttribute("provider.resolved", OGMA_PROVIDER);
    span.setAttribute("content.length", result.text.length);

    return result.text;
  });
}
```

Now every Ogma call has `ogma.provider` in the span — in Langfuse you can filter by this attribute and instantly answer "what % of Ogma calls used Groq vs Anthropic this week?"

## What We Skipped (and Why)

We didn't instrument:
- **Supabase reads** — these are PowerSync-managed; the sync engine handles retries and we don't need per-query traces for now
- **TanStack Router navigation** — client-side routing isn't observable server-side, and the added complexity wasn't worth it pre-hackathon
- **Mastra internal orchestration** — Mastra doesn't yet expose OTEL hooks; we wrapped at the call boundary instead

This is a real tradeoff. Perfect coverage isn't always worth the implementation cost. We covered the three highest-value points (LLM calls, image generation, audio) and left the rest for post-hackathon.

## SDK Init and Shutdown

```typescript
// index.ts — called once at startup
import { initTelemetry, shutdownTelemetry } from "./telemetry";

initTelemetry();

const server = Bun.serve({ /* ... */ });

// Graceful shutdown
process.on("SIGTERM", async () => {
  console.log("[Shutdown] SIGTERM received");
  await shutdownTelemetry(); // flushes OTEL batch processor
  await langfuse.shutdownAsync(); // flushes Langfuse SDK
  server.stop();
  process.exit(0);
});
```

The dual flush (OTEL + Langfuse SDK) is necessary because they're separate pipelines. Missing either one means lost spans on deploy.

## Summary

- `withSpan()` is the core primitive — handles lifecycle, error recording, status in one place
- Per-provider wrappers enforce consistent attribute names across all callers
- Wrap at the call boundary, not inside the provider SDK — this is less invasive and easier to remove
- Always `span.end()` in `finally` — an unclosed span is invisible
- Instrument the high-value paths first; perfect coverage is not the goal
