# Sample Datasets for Observability Course

This directory contains synthetic and real Langfuse trace datasets for use in course exercises.

## Files

### `synthetic-500.ndjson`
- **Generated:** 2026-03-10
- **Format:** NDJSON (newline-delimited JSON)
- **Count:** 500 traces
- **Seed:** 2026 (reproducible)
- **Source:** `scripts/generate_traces.py --count 500 --seed 2026`

**Usage:**
```bash
# Load into local Langfuse instance
python3 scripts/seed_langfuse.py sample_data/synthetic-500.ndjson \
  --host http://localhost:3100 \
  --public-key pk-lf-... \
  --secret-key sk-lf-...

# Load into cloud Langfuse
python3 scripts/seed_langfuse.py sample_data/synthetic-500.ndjson \
  --host https://cloud.langfuse.com \
  --public-key pk-... \
  --secret-key sk-...
```

**Dataset characteristics:**
- **Services:** api, ogma, anansi, firefly (multi-service traces)
- **Spans per trace:** 2–5 (realistic nested structure)
- **Generations per trace:** 1–3 (LLM calls with token counts and cost)
- **Error rate:** 5% (realistic error simulation)
- **Latency distribution:** Log-normal (p50=200ms, p95=800ms, p99=2000ms)
- **Token counts:** Log-normal (input ~200–2000, output ~50–500)
- **Models:** ollama/llama2:13b, groq/mixtral-8x7b, anthropic/claude-3-haiku, openai/gpt-3.5-turbo

## Scripts

### `scripts/generate_traces.py`
Generates synthetic OTEL/Langfuse traces with realistic distributions.

```bash
python3 scripts/generate_traces.py [options]
  --count N              Traces to generate (default: 100)
  --services STR         Comma-separated services (default: api,ogma,anansi,firefly)
  --error-rate F         Fraction with errors (default: 0.05)
  --output FILE          Output NDJSON file (default: stdout)
  --seed INT             Random seed for reproducibility
```

### `scripts/redact_traces.py`
Redacts PII, API keys, and secrets from exported traces before sharing.

```bash
python3 scripts/redact_traces.py input.ndjson [options]
  --output FILE          Output file (default: stdout)
  --dry-run              Show what would be redacted
  --report               Print redaction summary
```

Patterns redacted:
- API keys: Bearer tokens, sk-*, pk-lf-*, gsk_*, fal-key
- Emails → user@example.com
- IPv4 addresses → 10.0.x.x
- JWTs (eyJ...) → [REDACTED_JWT]
- Credit cards → [REDACTED_CC]
- Phone numbers (AU + intl) → [REDACTED_PHONE]
- Supabase URLs → [PROJECT].supabase.co
- Fly.io domains → [APP].fly.dev

### `scripts/seed_langfuse.py`
Batch ingests synthetic traces into a Langfuse instance.

```bash
python3 scripts/seed_langfuse.py input.ndjson [options]
  --host URL             Langfuse host (default: http://localhost:3100)
  --public-key STR       Public key (env: $LANGFUSE_PUBLIC_KEY)
  --secret-key STR       Secret key (env: $LANGFUSE_SECRET_KEY)
  --batch-size N         Traces per API call (default: 20)
  --dry-run              Validate without sending
  --verbose              Print progress
```

## Real Traces

`sandsync-traces-redacted.ndjson` (to be added after SandSync production data is exported).

## Contributing

When adding new sample datasets:
1. Run redaction pipeline for PII safety
2. Commit to git with descriptive message
3. Update this README with dataset characteristics
