#!/usr/bin/env python3
"""
Batch ingest synthetic traces into a Langfuse instance.

Reads NDJSON trace data and posts to Langfuse API in configurable batches.

Usage: python3 seed_langfuse.py input.ndjson [options]
"""

import json
import sys
import argparse
import os
import base64
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


def build_auth_header(public_key: str, secret_key: str) -> str:
    """Build HTTP Basic auth header from public and secret keys."""
    credentials = f"{public_key}:{secret_key}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


def post_batch(
    host: str,
    batch: list,
    auth_header: str,
    verbose: bool = False,
) -> bool:
    """
    Post a batch of traces to Langfuse API.
    Returns True if successful, False otherwise.
    """
    url = f"{host}/api/public/ingestion"
    
    # Langfuse batch ingestion expects a list of trace objects
    payload = json.dumps(batch).encode()
    
    request = Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": auth_header,
        },
        method="POST",
    )

    retry_count = 0
    max_retries = 3

    while retry_count < max_retries:
        try:
            response = urlopen(request, timeout=30)
            status = response.status
            response_text = response.read().decode()
            
            if verbose:
                print(f"POST {url} → {status}", file=sys.stderr)

            if status in (200, 201, 202):
                return True
            else:
                print(f"Unexpected status {status}: {response_text}", file=sys.stderr)
                return False

        except HTTPError as e:
            status = e.code
            error_body = e.read().decode()

            if status == 429:
                # Rate limited — retry with backoff
                retry_count += 1
                if retry_count >= max_retries:
                    print(f"Rate limited (429) — max retries exceeded", file=sys.stderr)
                    return False
                wait_time = 2 ** retry_count  # exponential backoff
                if verbose:
                    print(f"Rate limited (429) — retrying in {wait_time}s (attempt {retry_count}/{max_retries})",
                          file=sys.stderr)
                time.sleep(wait_time)

            elif status in (400, 401, 403, 404):
                # Client error — don't retry
                print(f"Client error {status}: {error_body}", file=sys.stderr)
                return False

            elif status in (500, 502, 503, 504):
                # Server error — retry
                retry_count += 1
                if retry_count >= max_retries:
                    print(f"Server error {status} — max retries exceeded", file=sys.stderr)
                    return False
                wait_time = 2 ** retry_count
                if verbose:
                    print(f"Server error {status} — retrying in {wait_time}s (attempt {retry_count}/{max_retries})",
                          file=sys.stderr)
                time.sleep(wait_time)

            else:
                print(f"HTTP error {status}: {error_body}", file=sys.stderr)
                return False

        except (URLError, Exception) as e:
            retry_count += 1
            if retry_count >= max_retries:
                print(f"Connection error (max retries exceeded): {e}", file=sys.stderr)
                return False
            wait_time = 2 ** retry_count
            if verbose:
                print(f"Connection error — retrying in {wait_time}s (attempt {retry_count}/{max_retries}): {e}",
                      file=sys.stderr)
            time.sleep(wait_time)

    return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Batch ingest synthetic traces into Langfuse",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 seed_langfuse.py traces.ndjson --verbose
  python3 seed_langfuse.py traces.ndjson --host http://localhost:3100 --dry-run
  python3 seed_langfuse.py traces.ndjson --public-key pk --secret-key sk --batch-size 50

Environment variables:
  LANGFUSE_BASE_URL    Langfuse host (default: http://localhost:3100)
  LANGFUSE_PUBLIC_KEY  Public key
  LANGFUSE_SECRET_KEY  Secret key
        """
    )

    parser.add_argument(
        "input",
        help="Input NDJSON file with trace data",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=os.getenv("LANGFUSE_BASE_URL", "http://localhost:3100"),
        help="Langfuse host (default: $LANGFUSE_BASE_URL or http://localhost:3100)",
    )
    parser.add_argument(
        "--public-key",
        type=str,
        default=os.getenv("LANGFUSE_PUBLIC_KEY", ""),
        help="Public key (default: $LANGFUSE_PUBLIC_KEY)",
    )
    parser.add_argument(
        "--secret-key",
        type=str,
        default=os.getenv("LANGFUSE_SECRET_KEY", ""),
        help="Secret key (default: $LANGFUSE_SECRET_KEY)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=20,
        help="Traces per API call (default: 20)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate input without sending",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print progress",
    )

    args = parser.parse_args()

    # Validate credentials
    if not args.dry_run:
        if not args.public_key or not args.secret_key:
            print(
                "Error: --public-key and --secret-key required (or set LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY)",
                file=sys.stderr,
            )
            sys.exit(1)

    # Read input and validate format
    try:
        input_file = open(args.input, "r")
    except FileNotFoundError:
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    traces = []
    line_num = 0

    try:
        for line in input_file:
            line_num += 1
            line = line.strip()
            if not line:
                continue

            try:
                trace_data = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"Error parsing line {line_num}: {e}", file=sys.stderr)
                sys.exit(1)

            # Validate basic structure
            if not isinstance(trace_data, dict):
                print(f"Error line {line_num}: expected object, got {type(trace_data).__name__}", 
                      file=sys.stderr)
                sys.exit(1)

            if "trace" not in trace_data:
                print(f"Error line {line_num}: missing 'trace' key", file=sys.stderr)
                sys.exit(1)

            traces.append(trace_data)

        if args.verbose:
            print(f"Loaded {len(traces)} traces from {args.input}", file=sys.stderr)

        # Print sample trace structure
        if traces:
            print(f"\nSample trace structure:", file=sys.stderr)
            print(json.dumps(traces[0], indent=2)[:500], file=sys.stderr)
            print("...\n", file=sys.stderr)

        # If dry-run, exit here
        if args.dry_run:
            print(f"✓ Validation passed: {len(traces)} traces ready to ingest", file=sys.stderr)
            sys.exit(0)

    finally:
        input_file.close()

    # Build auth header
    auth_header = build_auth_header(args.public_key, args.secret_key)

    # Batch and send traces
    ingested = 0
    failed = 0

    for i in range(0, len(traces), args.batch_size):
        batch = traces[i : i + args.batch_size]
        batch_num = (i // args.batch_size) + 1
        total_batches = (len(traces) + args.batch_size - 1) // args.batch_size

        if args.verbose:
            print(f"Posting batch {batch_num}/{total_batches} ({len(batch)} traces)...", file=sys.stderr)

        success = post_batch(args.host, batch, auth_header, verbose=args.verbose)

        if success:
            ingested += len(batch)
            progress = (ingested / len(traces)) * 100
            print(f"Ingested {ingested}/{len(traces)} traces ({progress:.0f}%)", file=sys.stderr)
        else:
            failed += len(batch)
            print(f"Failed to ingest batch {batch_num}", file=sys.stderr)

    if failed > 0:
        print(f"\n⚠ Partially complete: {ingested} succeeded, {failed} failed", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"\n✓ Success: ingested {ingested} traces", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
