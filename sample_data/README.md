# Sample Data

This directory contains sample datasets for the course exercises.

## Files

- `sandsync-traces-redacted.ndjson` — Real SandSync traces, redacted for public use
- `synthetic-500.ndjson` — Generated synthetic dataset (500 traces)

## Usage

### Load into Langfuse (Python)

```python
from langfuse import Langfuse

client = Langfuse(
    public_key="YOUR_PUBLIC_KEY",
    secret_key="YOUR_SECRET_KEY",
)

# Load NDJSON file
with open("sample_data/synthetic-500.ndjson") as f:
    for line in f:
        trace = json.loads(line)
        client.trace(**trace)

client.flush()
```

### Load into Local Langfuse

```bash
# Set environment to local instance
export LANGFUSE_HOST=http://localhost:3100

python -c "
import json
from langfuse import Langfuse

client = Langfuse(
    public_key='test_pk',
    secret_key='test_sk',
)

with open('sample_data/synthetic-500.ndjson') as f:
    for line in f:
        trace = json.loads(line)
        client.trace(**trace)

client.flush()
print('✓ Data loaded')
"
```

## Format

Each line is a valid JSON object compatible with the Langfuse SDK trace ingest format:

```json
{
  "id": "trace-123",
  "name": "user.signup",
  "user_id": "user-456",
  "session_id": "session-789",
  "timestamp": "2026-03-10T12:00:00Z",
  "input": {"email": "user@example.com"},
  "output": {"user_id": "user-456"},
  "metadata": {"source": "web"},
  "tags": ["signup", "auth"]
}
```

## Data Privacy

Real production traces have been redacted using `scripts/redact_traces.py`:

- Email addresses → `user@example.com` (keep count)
- IP addresses → `10.0.x.x` pattern
- API keys → `sk_****` (first/last 4 chars only)
- Bearer tokens → removed
- Model responses with PII → scanned and flagged for manual review

## Synthetic Generation

Synthetic traces are generated using `scripts/generate_traces.py` with:

- Realistic latency distributions (log-normal, not uniform)
- Configurable error rates
- Multi-service cascade simulation
- Token count simulation for LLM spans
- Seeds from real trace schema

---

_For more information, see Module 09: Synthetic Datasets._
