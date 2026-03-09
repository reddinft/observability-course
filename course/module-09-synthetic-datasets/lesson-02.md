# The generate_traces.py Tool

> **Estimated reading time:** 10 minutes

## Overview

`scripts/generate_traces.py` generates synthetic Langfuse-compatible trace datasets from a statistical schema. This lesson walks through its implementation — both as a practical tool and as a worked example of the statistical techniques that make synthetic data useful.

The full source is at `scripts/generate_traces.py` in this repo. We'll walk through the key sections.

## Usage

```bash
# Basic: 100 traces to stdout
python3 scripts/generate_traces.py --count 100

# Reproducible: fixed seed, file output
python3 scripts/generate_traces.py --count 500 --seed 2026 --output synthetic-500.ndjson

# Custom error rate and services
python3 scripts/generate_traces.py --count 200 --error-rate 0.15 --services api,ogma,anansi,firefly

# Help
python3 scripts/generate_traces.py --help
```

## The Statistical Core

The most important part of the generator is how it creates realistic values. Here's how latency is generated:

```python
def lognormal_ms(p50: float, p95: float) -> int:
    """
    Generate a log-normal latency value calibrated to real p50/p95.

    Log-normal is the right distribution for latencies because:
    - It's always positive (no negative latencies)
    - It has a long right tail (matches real p99 spikes)
    - It matches observed production latency distributions
    """
    # Convert p50/p95 to log-normal parameters
    mu = math.log(p50)
    # p95 = exp(mu + 1.645 * sigma) → solve for sigma
    sigma = (math.log(p95) - mu) / 1.645
    return max(1, int(random.lognormvariate(mu, sigma)))

# Usage
span_latency = lognormal_ms(p50=200, p95=800)  # milliseconds
```

Token counts use the same approach:

```python
input_tokens = lognormal_ms(p50=600, p95=1800)   # typical prompt size
output_tokens = lognormal_ms(p50=200, p95=600)    # typical completion size
```

This is the key insight: **calibrating the distribution to real p50/p95 values** is what makes synthetic data feel real. If you know your actual p50 and p95 from production, you can generate synthetic data that matches your system's characteristics.

## The Trace Structure

Each generated trace matches the Langfuse batch ingest format:

```python
def generate_trace(
    services: list[str],
    error_rate: float,
    rng: random.Random
) -> dict:
    trace_id = str(uuid.uuid4())
    is_error = rng.random() < error_rate
    start_time = datetime.datetime.utcnow() - datetime.timedelta(
        seconds=rng.randint(0, 86400)  # spread over last 24h
    )

    # Root trace
    trace = {
        "id": trace_id,
        "name": rng.choice(["story.generate_chapter", "story.create", "agent.run"]),
        "userId": f"user_{rng.randint(1000, 9999)}",
        "sessionId": f"session_{rng.randint(100, 999)}",
        "input": {"request": "generate story chapter"},
        "output": None if is_error else {"status": "success"},
        "metadata": {
            "environment": rng.choice(["production", "staging"]),
            "version": "2.0.0",
        },
        "tags": ["story-generation"],
        "timestamp": start_time.isoformat() + "Z",
    }
    return trace
```

## Multi-Service Cascade Simulation

The most realistic part of the generator is the cascade — simulating how SandSync's Ogma agent falls through providers:

```python
def generate_cascade_spans(trace_id: str, start: datetime, rng: random.Random) -> list:
    """Simulate the ollama → groq → anthropic cascade."""
    spans = []
    cascade = [
        ("ollama", 0.4),    # 40% chance Ollama is available
        ("groq", 0.85),     # if Ollama fails, 85% chance Groq works
        ("anthropic", 1.0), # Anthropic always works (final fallback)
    ]

    t = start
    for provider, success_prob in cascade:
        latency = lognormal_ms(p50=300, p95=900)
        succeeded = rng.random() < success_prob

        span = {
            "id": str(uuid.uuid4()),
            "traceId": trace_id,
            "name": f"ogma.{provider}",
            "startTime": t.isoformat() + "Z",
            "endTime": (t + datetime.timedelta(milliseconds=latency)).isoformat() + "Z",
            "attributes": {
                "provider": provider,
                "success": succeeded,
                "latency_ms": latency,
            },
            "status": "OK" if succeeded else "ERROR",
        }
        spans.append(span)

        if succeeded:
            break  # Stop cascade at first success
        t += datetime.timedelta(milliseconds=latency)

    return spans
```

This produces traces where you can see the exact cascade pattern in the waterfall — the same pattern we saw in real SandSync traces in Module 08.

## Error Injection

Errors are injected with realistic error types weighted by how commonly they occur:

```python
ERROR_TYPES = [
    ("Request timeout after 30s", 0.30),        # most common
    ("Rate limit exceeded: 100 req/min", 0.25),
    ("Context length exceeded (4K max)", 0.15),
    ("Model overloaded, retrying...", 0.12),
    ("Cascade fallback exhausted", 0.08),
    ("Service unavailable", 0.05),
    ("Invalid API key", 0.03),
    ("Connection refused", 0.02),
]

def pick_error(rng: random.Random) -> str:
    r = rng.random()
    cumulative = 0
    for msg, weight in ERROR_TYPES:
        cumulative += weight
        if r < cumulative:
            return msg
    return ERROR_TYPES[-1][0]
```

The weighting means timeout errors appear ~30% of the time among errors, which matches real-world LLM API patterns where cold starts and network timeouts dominate over quota errors.

## Deterministic Seeds

The `--seed` flag makes generation fully deterministic:

```bash
# These two commands produce identical output
python3 scripts/generate_traces.py --count 100 --seed 42 > traces-a.ndjson
python3 scripts/generate_traces.py --count 100 --seed 42 > traces-b.ndjson
diff traces-a.ndjson traces-b.ndjson  # no output
```

This matters for reproducibility in course exercises. The `sample_data/synthetic-500.ndjson` file was generated with `--seed 2026` — the exercises in this module reference specific traces by their deterministic IDs.

## The Pre-Generated Dataset

We've already generated a 500-trace dataset at `sample_data/synthetic-500.ndjson`. You can load it directly into Langfuse for the exercises — no need to generate your own unless you want to customise it.

Characteristics of the pre-generated dataset:
- 500 traces spanning a simulated 24-hour period
- Services: `api`, `ogma`, `anansi`, `firefly`
- Error rate: 5%
- Seed: 2026 (deterministic)
- ~2.1MB uncompressed

## Summary

- Log-normal distributions calibrated to real p50/p95 values are the key to realistic synthetic latency and token counts
- The cascade simulation generates multi-span traces that match real provider fallback patterns
- Error injection uses weighted sampling to match real-world error type distributions
- `--seed` makes generation deterministic — critical for reproducible exercises
- The pre-generated `synthetic-500.ndjson` is ready to use in the exercises below
