# Langfuse SDK Walkthrough

> **Estimated reading time:** 10 minutes

## Overview

The Langfuse SDK is the primary way to instrument your code. In this lesson we'll walk through the TypeScript SDK (v4.x) — creating traces, adding generations, recording scores, and integrating with the prompt registry.

All examples are based on the SandSync codebase. You can follow along at `github.com/reddinft/sandsync`.

## Installation

```bash
# TypeScript / Bun
bun add langfuse

# Python
pip install langfuse
```

## Initialisation

```typescript
import { Langfuse } from "langfuse";

const langfuse = new Langfuse({
  publicKey: process.env.LANGFUSE_PUBLIC_KEY!,
  secretKey: process.env.LANGFUSE_SECRET_KEY!,
  baseUrl: process.env.LANGFUSE_BASE_URL ?? "https://cloud.langfuse.com",

  // Flush buffered events every 2 seconds (default 5s)
  flushInterval: 2000,

  // In production: never log SDK internals to console
  debug: process.env.NODE_ENV === "development",
});
```

The SDK is a singleton — initialise once at app startup, reuse everywhere.

## Creating a Trace

A trace represents one complete user-facing operation. In SandSync, each story generation is a trace:

```typescript
async function generateStoryChapter(
  storyId: string,
  chapterNumber: number,
  userId: string
) {
  const trace = langfuse.trace({
    name: "story.generate_chapter",
    userId,
    sessionId: storyId, // group all chapters under one story session
    input: { storyId, chapterNumber },
    metadata: {
      environment: process.env.NODE_ENV,
      appVersion: "2.0.0",
    },
    tags: ["story-generation", `chapter-${chapterNumber}`],
  });

  try {
    const result = await runPipeline(storyId, chapterNumber, trace);
    trace.update({ output: { success: true, chapterId: result.id } });
    return result;
  } catch (err) {
    trace.update({ output: { success: false, error: (err as Error).message } });
    throw err;
  } finally {
    // Non-blocking flush — doesn't add latency to the response
    await langfuse.flushAsync();
  }
}
```

## Adding Spans

Spans track sub-operations within a trace. Pass the parent trace (or span) when creating children:

```typescript
async function runPipeline(storyId: string, chapter: number, trace: LangfuseTraceClient) {
  // Span for the overall pipeline
  const pipelineSpan = trace.span({
    name: "pipeline.run",
    input: { storyId, chapter },
  });

  // Child span for image generation
  const imageSpan = pipelineSpan.span({
    name: "imagen.generate",
    input: { prompt: "Caribbean watercolor illustration..." },
    metadata: { provider: "fal-ai", model: "flux/schnell" },
  });

  const imageUrl = await generateImage(/* ... */);

  imageSpan.end({
    output: { imageUrl },
    level: "DEFAULT", // DEFAULT | DEBUG | WARNING | ERROR
  });

  pipelineSpan.end({ output: { chapterComplete: true } });
}
```

## Recording LLM Generations

`generation` is a special span type with LLM-specific fields. This is the most important primitive in Langfuse:

```typescript
async function runOgmaReview(
  draft: string,
  storyId: string,
  parentSpan: LangfuseSpanClient
): Promise<string> {
  const generation = parentSpan.generation({
    name: "ogma.review",
    model: "llama-3.1-8b-instant",   // actual model used
    modelParameters: {
      temperature: 0.3,
      maxTokens: 1024,
    },
    input: [
      { role: "system", content: ogmaSystemPrompt },
      { role: "user", content: draft },
    ],
    metadata: { provider: OGMA_PROVIDER, storyId },
  });

  const startTime = Date.now();

  try {
    const response = await groq.chat.completions.create({
      model: "llama-3.1-8b-instant",
      messages: [
        { role: "system", content: ogmaSystemPrompt },
        { role: "user", content: draft },
      ],
      temperature: 0.3,
      max_tokens: 1024,
    });

    const completion = response.choices[0].message.content!;
    const usage = response.usage!;

    // Record the actual completion and token usage
    generation.end({
      output: completion,
      usage: {
        input: usage.prompt_tokens,
        output: usage.completion_tokens,
        total: usage.total_tokens,
        unit: "TOKENS",
      },
      completionStartTime: new Date(startTime), // time to first token (if streaming)
    });

    return completion;
  } catch (err) {
    generation.end({ level: "ERROR", output: { error: (err as Error).message } });
    throw err;
  }
}
```

## Using the Prompt Registry

The prompt registry is underused but extremely valuable. It gives you version-controlled prompts with A/B testing and zero-redeploy iteration:

```typescript
// Fetch a prompt from the registry (cached locally, refreshed every 60s)
const promptTemplate = await langfuse.getPrompt("ogma-review-system", {
  cacheTtlSeconds: 60,
  fallback: DEFAULT_SYSTEM_PROMPT, // if fetch fails
});

// Compile with variables
const systemPrompt = promptTemplate.compile({
  folkloreTradition: "Caribbean / Trinidadian",
  targetAge: "8-12",
});

// Record which prompt version was used on the generation
const generation = span.generation({
  name: "ogma.review",
  promptName: promptTemplate.name,
  promptVersion: promptTemplate.version,
  // ...
});
```

Now when you update the prompt in the Langfuse UI and bump the version, all new requests pick it up within 60 seconds — no code deploy needed.

## Adding Scores

Scores are evaluation signals. The most common pattern is LLM-as-a-judge:

```typescript
// After generation, score it with a separate LLM call
async function scoreChapterQuality(
  traceId: string,
  chapter: string
): Promise<void> {
  const judgeResponse = await runLLMJudge(chapter); // returns 0.0–1.0

  await langfuse.score({
    traceId,
    name: "quality",
    value: judgeResponse.score,
    comment: judgeResponse.reasoning,
    source: "LLM_JUDGE",
  });

  // Also score cultural authenticity
  await langfuse.score({
    traceId,
    name: "cultural_authenticity",
    value: judgeResponse.authenticityScore,
    source: "LLM_JUDGE",
  });
}
```

Scores appear in the Generations view, let you sort/filter by quality, and feed into dataset evaluation runs.

## OTEL Integration (Alternative Approach)

If you already have OTEL instrumentation, you can export to Langfuse's OTLP endpoint instead of using the SDK directly. This is what SandSync does for non-LLM spans:

```typescript
// In telemetry.ts — export to Langfuse OTLP
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-http";

const langfuseExporter = new OTLPTraceExporter({
  url: `${process.env.LANGFUSE_BASE_URL}/api/public/otel/v1/traces`,
  headers: {
    Authorization: `Basic ${Buffer.from(
      `${process.env.LANGFUSE_PUBLIC_KEY}:${process.env.LANGFUSE_SECRET_KEY}`
    ).toString("base64")}`,
  },
});
```

OTEL spans land in Langfuse as regular spans. LLM calls need `gen_ai.*` attributes to be recognised as generations.

## Flush Strategy

A critical gotcha: **Langfuse events are buffered and must be flushed** before your process exits.

```typescript
// In serverless / short-lived processes: flush after each request
await langfuse.flushAsync();

// In long-running servers: flush on shutdown
process.on("SIGTERM", async () => {
  await langfuse.shutdownAsync();
  process.exit(0);
});

// In Bun:
process.on("beforeExit", async () => {
  await langfuse.shutdownAsync();
});
```

If you skip this, events buffered in the last batch window (default 5s) will be lost.

## Summary

- Initialise once, reuse everywhere — `langfuse.trace()` → `trace.span()` → `span.generation()`
- Record `usage` on every generation — this is how cost tracking works
- Use the prompt registry for any prompt you'll iterate on
- Add scores post-generation for quality tracking
- Always flush before process exit
