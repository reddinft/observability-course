# Redaction & Ingestion: The Full Pipeline

> **Estimated reading time:** 9 minutes

## Overview

This lesson covers the other two scripts in the pipeline: `redact_traces.py` for sanitising real traces before sharing, and `seed_langfuse.py` for loading any NDJSON dataset into Langfuse. We'll also run the full end-to-end pipeline and load the 500-trace dataset into your own Langfuse instance.

## redact_traces.py — Sanitising Real Exports

When you want to use real production traces as examples — in courses, documentation, or bug reports — you need to strip sensitive data first.

### Usage

```bash
# Dry run: see what would be redacted without writing
python3 scripts/redact_traces.py real-export.json --dry-run --report

# Redact and write to file
python3 scripts/redact_traces.py real-export.json --output sanitised.ndjson

# With custom redaction config
python3 scripts/redact_traces.py real-export.json --config redact-config.yaml --report
```

### What Gets Redacted

The script deep-walks the JSON structure and applies regex patterns to every string value:

```python
REDACTION_PATTERNS = {
    # API keys — most important
    "api_key_sk":       (r'sk-[a-zA-Z0-9]{20,}', '[REDACTED_KEY]'),
    "api_key_pk_lf":    (r'pk-lf-[a-zA-Z0-9-]{20,}', '[REDACTED_KEY]'),
    "api_key_sk_lf":    (r'sk-lf-[a-zA-Z0-9-]{20,}', '[REDACTED_KEY]'),
    "api_key_groq":     (r'gsk_[a-zA-Z0-9]{40,}', '[REDACTED_KEY]'),
    "api_key_bearer":   (r'Bearer\s+[a-zA-Z0-9\-._~+/]{20,}', 'Bearer [REDACTED_KEY]'),

    # PII
    "email":            (r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
                         'user@example.com'),
    "ipv4":             (r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', '10.0.x.x'),
    "jwt":              (r'eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+',
                         '[REDACTED_JWT]'),

    # Infrastructure
    "supabase_url":     (r'https://[a-z0-9]+\.supabase\.co', 'https://[PROJECT].supabase.co'),
    "fly_hostname":     (r'[a-z0-9-]+\.fly\.dev', '[APP].fly.dev'),
}
```

The deep-walk ensures nested objects and arrays are all processed — it's not just top-level fields:

```python
def redact_value(value: Any, stats: dict) -> tuple[Any, dict]:
    """Recursively redact sensitive data from any JSON value."""
    if isinstance(value, str):
        for pattern_name, (pattern, replacement) in REDACTION_PATTERNS.items():
            if re.search(pattern, value):
                value = re.sub(pattern, replacement, value)
                stats[pattern_name] = stats.get(pattern_name, 0) + 1
        return value, stats
    elif isinstance(value, dict):
        return {k: redact_value(v, stats)[0] for k, v in value.items()}, stats
    elif isinstance(value, list):
        return [redact_value(item, stats)[0] for item in value], stats
    return value, stats
```

### The --report Flag

Run with `--report` to get a summary of what was redacted:

```
$ python3 scripts/redact_traces.py production-export.json --dry-run --report

Redaction Report
================
Total fields scanned: 4,821
Values redacted: 23

Breakdown:
  api_key_sk_lf:    8  (Langfuse secret keys in trace metadata)
  email:           11  (User email addresses in userId fields)
  supabase_url:     4  (Database URLs in span attributes)

Output: [DRY RUN - no file written]
```

This tells you exactly what was found before you commit to redacting.

### Custom Config

If you have application-specific patterns, define them in a YAML config:

```yaml
# redact-config.yaml
patterns:
  - name: internal_user_id
    pattern: 'usr_[a-f0-9]{16}'
    replacement: '[REDACTED_USER_ID]'
  - name: story_id
    pattern: 'story_[a-f0-9-]{36}'
    replacement: '[REDACTED_STORY_ID]'

blocklist_fields:
  - "metadata.internal_notes"
  - "input.system_prompt"
```

## seed_langfuse.py — Loading Traces

Once you have a clean NDJSON file (generated or redacted), `seed_langfuse.py` ingests it into any Langfuse instance.

### Setup

The script reads Langfuse credentials from environment variables (same ones the SDK uses):

```bash
export LANGFUSE_PUBLIC_KEY="pk-lf-..."
export LANGFUSE_SECRET_KEY="sk-lf-..."
export LANGFUSE_BASE_URL="http://localhost:3100"  # or https://cloud.langfuse.com
```

Or pass them as flags.

### Usage

```bash
# Validate without sending (dry run)
python3 scripts/seed_langfuse.py sample_data/synthetic-500.ndjson --dry-run --verbose

# Ingest into local Langfuse
python3 scripts/seed_langfuse.py sample_data/synthetic-500.ndjson --verbose

# Ingest into cloud with custom batch size
python3 scripts/seed_langfuse.py sample_data/synthetic-500.ndjson \
  --host https://cloud.langfuse.com \
  --public-key pk-lf-... \
  --secret-key sk-lf-... \
  --batch-size 50
```

### Batching and Retry Logic

The script sends traces in batches and handles errors gracefully:

```python
def ingest_batch(batch: list, config: dict) -> bool:
    """POST a batch to /api/public/ingestion with retry logic."""
    payload = json.dumps({"batch": batch}).encode()
    auth = base64.b64encode(
        f"{config['public_key']}:{config['secret_key']}".encode()
    ).decode()

    for attempt in range(3):
        try:
            req = urllib.request.Request(
                f"{config['host']}/api/public/ingestion",
                data=payload,
                headers={
                    "Authorization": f"Basic {auth}",
                    "Content-Type": "application/json",
                }
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status == 207  # Langfuse uses 207 Multi-Status

        except urllib.error.HTTPError as e:
            if e.code == 429:  # Rate limited
                wait = 2 ** attempt  # exponential backoff: 1s, 2s, 4s
                time.sleep(wait)
                continue
            elif e.code >= 500:  # Server error, retry
                time.sleep(1)
                continue
            else:
                print(f"Error {e.code}: {e.reason}", file=sys.stderr)
                return False

    return False  # All retries exhausted
```

## Exercise: Load the 500-Trace Dataset

**Prerequisites:** A running Langfuse instance (local self-hosted or cloud account).

```bash
# 1. Clone the repo
git clone https://github.com/reddinft/observability-course
cd observability-course

# 2. Set credentials
export LANGFUSE_PUBLIC_KEY="pk-lf-..."   # from your Langfuse settings
export LANGFUSE_SECRET_KEY="sk-lf-..."
export LANGFUSE_BASE_URL="http://localhost:3100"  # or cloud URL

# 3. Validate first
python3 scripts/seed_langfuse.py sample_data/synthetic-500.ndjson --dry-run --verbose
# Expected: "Validation passed. 500 traces ready to ingest."

# 4. Ingest
python3 scripts/seed_langfuse.py sample_data/synthetic-500.ndjson --verbose
# Expected: Ingested 500/500 traces (100%)

# 5. Open Langfuse and explore
open $LANGFUSE_BASE_URL
```

**What to explore in Langfuse after loading:**
- Filter Traces by `tags: ["story-generation"]` — all 500 traces
- Find the traces with `status: ERROR` — what error types appear?
- Open a cascade trace and examine the span waterfall — can you see the ollama→groq fallback?
- Go to Generations and check the token distribution — does it match the log-normal shape?
- Filter by `metadata.environment: staging` — what's different about staging traces?

## The Full Pipeline in One Shot

```bash
# Generate fresh → redact → ingest
python3 scripts/generate_traces.py --count 100 --seed 42 --output /tmp/raw.ndjson
python3 scripts/redact_traces.py /tmp/raw.ndjson --report --output /tmp/clean.ndjson
python3 scripts/seed_langfuse.py /tmp/clean.ndjson --verbose
```

## Summary

- `redact_traces.py` deep-walks JSON and applies regex patterns — always run `--dry-run --report` first
- `seed_langfuse.py` batches ingestion with exponential backoff on 429s — safe to run against any Langfuse instance
- The full pipeline: `generate → redact → seed` takes under 60 seconds for 500 traces
- The exercise: load `synthetic-500.ndjson` and explore the cascade traces, error distribution, and token shapes in Langfuse
