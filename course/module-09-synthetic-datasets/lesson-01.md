# Why Synthetic Data?

> **Estimated reading time:** 7 minutes

## The Problem with Learning from Real Traces

Real production traces are the best learning material — they have realistic noise, interesting failure patterns, and real cost distributions. But they have two problems:

**They contain sensitive data.** Prompts and completions often include user content, internal knowledge, or PII. You can't share a real trace from a healthcare chatbot with a class of students. Even after redaction, residual risk makes sharing awkward.

**You can't control them.** If you want to demonstrate tail-based sampling on traces with exactly 5% error rate and a specific latency distribution, real data won't cooperate. Production systems have the patterns they have.

Synthetic data solves both problems. Generate it from a schema, control every variable, share freely.

## Where Synthetic Data Is Used

**Course exercises.** This course's Module 09 exercise asks you to load 500 traces into your own Langfuse instance and run an evaluation. That's only possible because we can hand you a pre-generated dataset that works on any Langfuse setup.

**Testing observability pipelines.** Before connecting your production app to a new Langfuse instance, you want to verify the ingestion works, the dashboards render, and alerts fire correctly. Synthetic data lets you do a full end-to-end test without real traffic.

**Load testing.** If you're evaluating Langfuse self-hosting at 10k traces/day, you need a way to generate that volume on demand to see how ClickHouse and Postgres perform under load.

**Evaluation baseline.** When building LLM-as-a-judge pipelines, you need a corpus of traces with known-good and known-bad outputs to calibrate your judge. Synthetic data with injected quality variations lets you do this without waiting for production data.

## What Makes Synthetic Data "Realistic"?

The difference between good and bad synthetic data is in the distributions.

**Bad synthetic data:** `latency = random.uniform(100, 3000)` — flat distribution, nothing like production.

**Good synthetic data:** `latency = int(random.lognormvariate(mu, sigma))` — log-normal distribution matching real p50/p95/p99 values.

Latency, token counts, error rates, and cost all follow characteristic distributions in real systems. If your synthetic data doesn't match those distributions, the exercises built on it will give students false intuitions.

For this course's dataset, we calibrated distributions against real SandSync production traces:
- Span latencies: log-normal (p50=200ms, p95=800ms, p99=2000ms)
- Input tokens: log-normal (p50=600, p95=1800, p99=2800)
- Output tokens: log-normal (p50=200, p95=600, p99=900)
- Error rate: 5% of traces, weighted toward timeout and rate-limit errors

## The Tool We Built

`scripts/generate_traces.py` is the generator for this course. It's also a lesson in itself — the implementation demonstrates exactly the statistical techniques described above.

Run it:

```bash
# Generate 100 traces to stdout
python3 scripts/generate_traces.py --count 100

# Generate 500 traces with a fixed seed (reproducible)
python3 scripts/generate_traces.py --count 500 --seed 2026 --output sample_data/synthetic-500.ndjson

# Control error rate and services
python3 scripts/generate_traces.py --count 100 --error-rate 0.20 --services api,ogma,anansi
```

Output format is NDJSON — one JSON object per line, each a Langfuse-compatible batch ingest payload.

## The Three-Script Pipeline

Module 09 introduces three tools that form a complete synthetic data workflow:

```
generate_traces.py  →  redact_traces.py  →  seed_langfuse.py
     (create)              (sanitise)            (ingest)
```

**generate_traces.py** — Creates synthetic traces from a statistical schema. Used when you need data from scratch.

**redact_traces.py** — Strips PII and secrets from real Langfuse exports. Used when you have real traces you want to sanitise for sharing.

**seed_langfuse.py** — Batch-ingests NDJSON trace files into any Langfuse instance. Used after either of the above.

You can use them independently or chain them. In the next two lessons we'll walk through each one in depth.

## Summary

- Synthetic data solves two real problems: sensitive data in real traces, and lack of control over distributions
- Good synthetic data matches real statistical distributions — log-normal for latency and tokens, not uniform
- The three-script pipeline (`generate → redact → seed`) covers the full workflow from creation to ingestion
- The 500-trace sample dataset (`sample_data/synthetic-500.ndjson`) is already generated and ready to use
