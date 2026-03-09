#!/usr/bin/env python3
"""
Synthetic Langfuse-compatible trace dataset generator.

Generates statistically realistic trace data for course exercises.
Usage: python3 generate_traces.py [options]
"""

import json
import random
import uuid
import datetime
import argparse
import math
import sys

# Constants for cost calculation (haiku-class pricing)
COST_PER_1M_INPUT_TOKENS = 0.25 / 1_000_000
COST_PER_1M_OUTPUT_TOKENS = 1.25 / 1_000_000

# Realistic error messages
ERROR_MESSAGES = [
    "Request timeout after 30s",
    "Rate limit exceeded: 100 req/min",
    "Context length exceeded (4K max)",
    "Model overloaded, retrying...",
    "Invalid API key",
    "Service unavailable",
    "Hallucination detected in response",
    "Token count mismatch",
    "Cascade fallback exhausted",
    "Connection refused",
]

# Service operations
SERVICE_OPS = {
    "api": ["process_request", "validate_input", "call_external_api", "format_response"],
    "ogma": ["route_to_provider", "construct_prompt", "call_ollama", "fallback_to_groq", "fallback_to_claude"],
    "anansi": ["fetch_context", "enrich_data", "generate_summary"],
    "firefly": ["build_ui", "render_component", "optimize_assets"],
}

# Models for LLM generation spans
MODELS = [
    "ollama/llama2:13b",
    "groq/mixtral-8x7b",
    "anthropic/claude-3-haiku",
    "openai/gpt-3.5-turbo",
]


def log_normal_distribution(median: float, p95: float) -> float:
    """
    Generate a value from log-normal distribution.
    Given median and p95 percentile, compute mean and stddev,
    then sample from log-normal.
    """
    # log-normal: p = exp(normal(mu, sigma))
    # median = exp(mu) => mu = ln(median)
    # p95 ≈ exp(mu + 1.645*sigma)
    mu = math.log(median)
    # Solve: p95 = exp(mu + 1.645*sigma)
    # ln(p95) = mu + 1.645*sigma
    # sigma = (ln(p95) - mu) / 1.645
    sigma = (math.log(p95) - mu) / 1.645
    x = random.gauss(mu, sigma)
    return math.exp(x)


def generate_trace(
    trace_id: str,
    user_id: str,
    session_id: str,
    services: list,
    error_rate: float,
    timestamp: datetime.datetime,
) -> dict:
    """Generate a single trace with nested spans and generations."""
    has_error = random.random() < error_rate

    # Root span (trace level)
    trace_obj = {
        "id": trace_id,
        "name": f"request_{random.choice(['process', 'analyze', 'generate', 'handle'])}",
        "userId": user_id,
        "sessionId": session_id,
        "timestamp": timestamp.isoformat(),
        "input": json.dumps({"query": f"query_{random.randint(1, 1000)}", "context": "user_context"}),
        "output": None if has_error else json.dumps({"result": "success", "data": [1, 2, 3]}),
        "metadata": {
            "environment": "production",
            "version": "1.0.0",
        },
        "tags": ["course_synthetic", "exercise_data"],
    }

    if has_error:
        trace_obj["metadata"]["error"] = random.choice(ERROR_MESSAGES)

    # Nested spans (2-5 per trace)
    num_spans = random.randint(2, 5)
    spans = []
    parent_time = timestamp

    for i in range(num_spans):
        span_duration = log_normal_distribution(200, 800)  # milliseconds, p50=200, p95=800
        span_start = parent_time + datetime.timedelta(milliseconds=sum(s["duration"] for s in spans))
        span_end = span_start + datetime.timedelta(milliseconds=span_duration)

        service = random.choice(services)
        operation = random.choice(SERVICE_OPS[service])

        span = {
            "id": str(uuid.uuid4()),
            "traceId": trace_id,
            "parentSpanId": None if i == 0 else spans[i - 1]["id"],
            "name": f"{service}/{operation}",
            "startTime": span_start.isoformat(),
            "endTime": span_end.isoformat(),
            "duration": span_duration,
            "attributes": {
                "service": service,
                "operation": operation,
                "span.kind": "internal",
            },
            "events": [],
            "status": {"code": "ERROR" if (has_error and i == num_spans - 1) else "OK"},
        }

        if has_error and i == num_spans - 1:
            span["events"].append({
                "name": "exception",
                "timestamp": span_end.isoformat(),
                "attributes": {"exception.message": random.choice(ERROR_MESSAGES)},
            })

        spans.append(span)

    # LLM generation spans (1-3 per trace)
    num_gens = random.randint(1, 3)
    generations = []

    for i in range(num_gens):
        gen_id = str(uuid.uuid4())
        model = random.choice(MODELS)
        
        # Token counts with log-normal distribution
        input_tokens = int(log_normal_distribution(200, 1500))
        output_tokens = int(log_normal_distribution(50, 300))
        
        # Cost calculation
        input_cost = input_tokens * COST_PER_1M_INPUT_TOKENS
        output_cost = output_tokens * COST_PER_1M_OUTPUT_TOKENS
        total_cost = input_cost + output_cost

        gen_duration = log_normal_distribution(500, 2000)  # slightly longer for LLM calls
        gen_start = spans[-1]["endTime"] if spans else timestamp.isoformat()

        # Parse gen_start if it's a string
        if isinstance(gen_start, str):
            gen_start_dt = datetime.datetime.fromisoformat(gen_start)
        else:
            gen_start_dt = gen_start

        gen_end = (gen_start_dt + datetime.timedelta(milliseconds=gen_duration)).isoformat()

        generation = {
            "id": gen_id,
            "traceId": trace_id,
            "spanId": spans[-1]["id"] if spans else None,
            "name": f"generation_{i}",
            "startTime": gen_start,
            "endTime": gen_end,
            "model": model,
            "input": json.dumps({"prompt": f"prompt_{i}", "system": "You are a helpful assistant"}),
            "output": json.dumps({"text": f"generated_response_{i}"}),
            "usage": {
                "inputTokens": input_tokens,
                "outputTokens": output_tokens,
                "totalTokens": input_tokens + output_tokens,
            },
            "totalCost": total_cost,
        }

        generations.append(generation)

    return {
        "trace": trace_obj,
        "spans": spans,
        "generations": generations,
    }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate synthetic Langfuse-compatible traces",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 generate_traces.py --count 100 --output traces.ndjson
  python3 generate_traces.py --count 10 --seed 42 --output /tmp/test.ndjson
  python3 generate_traces.py --count 500 --services api,ogma,anansi --error-rate 0.1
        """
    )

    parser.add_argument(
        "--count",
        type=int,
        default=100,
        help="Number of traces to generate (default: 100)",
    )
    parser.add_argument(
        "--services",
        type=str,
        default="api,ogma,anansi,firefly",
        help="Comma-separated service names (default: api,ogma,anansi,firefly)",
    )
    parser.add_argument(
        "--error-rate",
        type=float,
        default=0.05,
        help="Fraction of traces with errors (default: 0.05)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output NDJSON file (default: stdout)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility",
    )
    parser.add_argument(
        "--schema",
        type=str,
        default=None,
        help="JSON config file overriding defaults (not implemented)",
    )

    args = parser.parse_args()

    # Validate args
    if args.error_rate < 0 or args.error_rate > 1:
        print("Error: --error-rate must be between 0 and 1", file=sys.stderr)
        sys.exit(1)

    if args.count <= 0:
        print("Error: --count must be > 0", file=sys.stderr)
        sys.exit(1)

    services = [s.strip() for s in args.services.split(",")]

    # Set random seed if provided
    if args.seed is not None:
        random.seed(args.seed)

    # Generate traces
    output_file = open(args.output, "w") if args.output else sys.stdout

    try:
        for i in range(args.count):
            trace_id = str(uuid.uuid4())
            user_id = f"user_{random.randint(1, 100)}"
            session_id = str(uuid.uuid4())
            timestamp = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
                seconds=random.randint(0, 86400)
            )

            trace_data = generate_trace(
                trace_id=trace_id,
                user_id=user_id,
                session_id=session_id,
                services=services,
                error_rate=args.error_rate,
                timestamp=timestamp,
            )

            # Write NDJSON (one JSON object per line)
            output_file.write(json.dumps(trace_data) + "\n")

            if i % 50 == 0 and args.output:
                print(f"Generated {i}/{args.count} traces", file=sys.stderr)

        if args.output:
            print(f"Generated {args.count} traces → {args.output}", file=sys.stderr)

    finally:
        if args.output:
            output_file.close()


if __name__ == "__main__":
    main()
