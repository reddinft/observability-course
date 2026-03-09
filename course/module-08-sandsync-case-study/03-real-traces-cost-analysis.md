# Real Traces & Cost Analysis

> **Estimated reading time:** 9 minutes

## Overview

This lesson walks through what SandSync's instrumentation revealed in production — the latency breakdown across the pipeline, a provider attribution surprise in Ogma, and a token cost pattern we didn't expect.

The traces shown here are from the Langfuse Cloud project at `cloud.langfuse.com/project/cmmjmaw050bb2ad07nzijbgjr`. They've been redacted to remove any user data. Students with course access can browse the public read-only version of this project.

## Reading the Waterfall

A typical story chapter generation trace looks like this:

```
story.generate_chapter          [████████████████████████████] 8.4s
├── pipeline.run                [███████████████████████████ ] 8.1s
│   ├── anansi.draft            [████████████████           ] 4.8s
│   │   └── generation (haiku)  [████████████████           ] 4.7s  847 tokens
│   ├── ogma.review             [      ████████             ] 2.4s
│   │   └── generation (groq)   [      ████████             ] 2.3s  312 tokens
│   └── fal.image_generate      [              ████████████ ] 3.1s
│       └── (fal.ai FLUX)       [              ████████████ ] 3.0s
└── supabase.chapter_upsert     [                          █] 0.3s
```

Three things jump out:

1. **Anansi (4.8s) dominates** — nearly 60% of total time. Claude Haiku at ~5s for an 800-token completion is expected but still the obvious optimisation target.

2. **Ogma and fal.ai run sequentially** — they could run in parallel. This is a code architecture problem, not an infrastructure one. Fixing this would bring total time from 8.4s to roughly 5.5s.

3. **Supabase write is negligible** — 300ms. We worried about this being slow; turns out it's fine.

## The Ogma Provider Surprise

Before adding `ogma.provider` to spans, Ogma's latency looked bimodal — sometimes 2s, sometimes 8s. After adding the attribute:

| Provider | p50 | p95 | p99 | % of calls |
|---|---|---|---|---|
| `groq/llama-3.1-8b-instant` | 1.8s | 3.2s | 4.1s | 83% |
| `anthropic/claude-haiku` | 6.8s | 9.4s | 12.1s | 17% |

Mystery solved. When Groq is available, Ogma is fast. When it falls back to Anthropic (which happens when `GROQ_API_KEY` isn't set in a particular environment), it's 4x slower. The 17% Anthropic calls were from our staging environment where we hadn't set the Groq key.

This is exactly the kind of insight that only traces give you. Metrics would show "Ogma p95 is sometimes 9s" — but wouldn't tell you it's only that slow in one environment with one provider.

## Token Cost Analysis

Langfuse's cost tracking requires accurate token counts. Here's what we found over 200 test story chapters:

**Anansi (Claude Haiku)**
- Average input tokens: 1,247 (system prompt + story context)
- Average output tokens: 683 (chapter draft)
- Cost per call: ~$0.0009 ($0.25/M input + $1.25/M output)
- Cost per story (5 chapters): ~$0.0045

**Ogma (Groq Llama 3.1 8B)**
- Average input tokens: 856 (system + Anansi's draft)
- Average output tokens: 312 (reviewed chapter)
- Cost per call: ~$0.00008 (Groq pricing: $0.05/M input + $0.08/M output)
- Cost per story (5 chapters): ~$0.0004

**Key finding:** Ogma on Groq costs **10x less** than Anansi on Haiku. Using Groq for the quality-review pass was the right call — it's fast, cheap, and the output quality is sufficient for the review task.

**The prompt bloat problem:** Anansi's 1,247 average input tokens includes a 450-token system prompt that we copied from an earlier prototype and never trimmed. It contains redundant formatting instructions and a character list that doesn't change between calls. Trimming this would save ~36% on Anansi's input cost with zero quality impact.

We found this by looking at Langfuse's token distribution chart and noticing the input/output ratio was unusually high (1.8:1 for a creative writing task — typically closer to 1:1).

## The fal.ai Latency Distribution

fal.ai FLUX image generation latency for `fal-ai/flux/schnell`:

```
p10:  1.2s  ▓
p25:  1.8s  ▓▓
p50:  2.6s  ▓▓▓
p75:  3.8s  ▓▓▓▓
p95:  6.4s  ▓▓▓▓▓▓▓
p99: 11.2s  ▓▓▓▓▓▓▓▓▓▓▓▓
```

The p99 of 11.2s is concerning for user experience, but looking at the actual traces that hit p99: they all have `image.size: square_hd` (a larger resolution we used in early testing). Standard `landscape_4_3` requests don't exceed 5s. The solution was already in place — we switched to landscape in the final version.

Without per-request span attributes (`image.size` on each span), this would have looked like "fal.ai is occasionally very slow" — actionable only by switching providers. With the attribute, it was "large resolution requests are slow" — fixable by config.

## What We'd Do Differently

**More aggressive parallelism.** The Ogma review and fal.ai image generation could both start immediately after Anansi finishes. Running them in parallel would cut 2–3s from the critical path. We didn't do this pre-hackathon because the code was simpler sequentially — but the traces make the cost very visible.

**Streaming for Anansi.** Claude Haiku supports streaming. Streaming Anansi's output to the UI while Ogma reviews the full draft would improve perceived performance significantly. This is a UI architecture change, not a backend one.

**Add cost scoring.** We log token counts but don't automatically score traces that exceed a cost threshold. Adding a score like `cost_within_budget: true/false` would make it easy to alert on unexpectedly expensive requests.

## The Observability Payoff

Before instrumentation: "SandSync is slow sometimes." (unhelpful)
After instrumentation:
- Anansi is the latency bottleneck (fix: parallelise or stream)
- Ogma cost can be cut 10x by using Groq (done)
- fal.ai p99 caused by resolution config (fixed)
- Anansi input tokens are 36% bloated by stale prompt (queued for trimming)
- Staging is using Anthropic for Ogma because GROQ_API_KEY isn't set (fixed)

Five concrete findings from two days of instrumented production traffic. That's the observability payoff.

## Summary

- Waterfall traces immediately revealed the sequential Ogma+fal.ai bottleneck
- Provider attribution on Ogma spans explained the bimodal latency distribution
- Token cost analysis found a 36% prompt bloat in Anansi that metrics alone wouldn't surface
- Per-span attributes (`image.size`) turned "fal.ai is slow" into "large resolution is slow"
- Observability doesn't fix bugs — it tells you which bugs to fix first
