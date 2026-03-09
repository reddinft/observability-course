#!/usr/bin/env python3
"""
PII and secret redaction pipeline for Langfuse traces.

Safely redacts API keys, emails, IPs, JWTs, and other sensitive patterns
from exported traces before sharing as course examples.

Usage: python3 redact_traces.py input.json [options]
"""

import json
import re
import sys
import argparse
from typing import Any, Dict, Tuple


# Redaction patterns and their replacement values
REDACTION_PATTERNS = {
    "api_key_bearer": {
        "pattern": r"Bearer\s+[A-Za-z0-9\-_\.]+",
        "replacement": "[REDACTED_KEY]",
    },
    "api_key_sk": {
        "pattern": r"sk-[A-Za-z0-9]{20,}",
        "replacement": "[REDACTED_KEY]",
    },
    "api_key_pk_lf": {
        "pattern": r"pk-lf-[A-Za-z0-9\-_]+",
        "replacement": "[REDACTED_KEY]",
    },
    "api_key_sk_lf": {
        "pattern": r"sk-lf-[A-Za-z0-9\-_]+",
        "replacement": "[REDACTED_KEY]",
    },
    "api_key_gsk": {
        "pattern": r"gsk_[A-Za-z0-9]{20,}",
        "replacement": "[REDACTED_KEY]",
    },
    "api_key_fal": {
        "pattern": r"fal[-_][A-Za-z0-9\-_]{20,}",
        "replacement": "[REDACTED_KEY]",
    },
    "jwt": {
        "pattern": r"eyJ[A-Za-z0-9_\-\.]+",
        "replacement": "[REDACTED_JWT]",
    },
    "email": {
        "pattern": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "replacement": "user@example.com",
    },
    "ipv4": {
        "pattern": r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b",
        "replacement": "10.0.x.x",
    },
    "credit_card": {
        "pattern": r"\b(?:\d[ -]*?){13,19}\b",
        "replacement": "[REDACTED_CC]",
    },
    "phone_au": {
        "pattern": r"(?:\+61|0)[2-9](?:\s?\d){8}",
        "replacement": "[REDACTED_PHONE]",
    },
    "phone_intl": {
        "pattern": r"\+\d{1,3}\s?\d{6,14}",
        "replacement": "[REDACTED_PHONE]",
    },
    "supabase_url": {
        "pattern": r"https://[a-z0-9]+\.supabase\.co",
        "replacement": "https://[PROJECT].supabase.co",
    },
    "fly_io_domain": {
        "pattern": r"https?://[a-z0-9\-]+\.fly\.dev",
        "replacement": "[APP].fly.dev",
    },
}


class TraceRedactor:
    """Redactor for Langfuse trace data."""

    def __init__(self, dry_run: bool = False):
        """Initialize redactor."""
        self.dry_run = dry_run
        self.redaction_stats: Dict[str, int] = {pattern: 0 for pattern in REDACTION_PATTERNS}
        self.fields_scanned = 0

    def redact_value(self, value: str) -> Tuple[str, list]:
        """
        Redact sensitive patterns from a string value.
        Returns (redacted_value, list_of_redactions).
        """
        redactions = []

        for pattern_name, pattern_info in REDACTION_PATTERNS.items():
            pattern = pattern_info["pattern"]
            replacement = pattern_info["replacement"]

            # Find all matches
            matches = list(re.finditer(pattern, value, re.IGNORECASE))
            if matches:
                self.redaction_stats[pattern_name] += len(matches)
                redactions.append((pattern_name, len(matches)))

                if not self.dry_run:
                    value = re.sub(pattern, replacement, value, flags=re.IGNORECASE)

        return value, redactions

    def deep_walk(self, obj: Any, path: str = "root") -> Any:
        """
        Deep walk through nested JSON structure and redact all string values.
        Returns redacted object.
        """
        if isinstance(obj, dict):
            result = {}
            for key, val in obj.items():
                new_path = f"{path}.{key}"
                result[key] = self.deep_walk(val, new_path)
            return result

        elif isinstance(obj, list):
            return [self.deep_walk(item, f"{path}[{i}]") for i, item in enumerate(obj)]

        elif isinstance(obj, str):
            self.fields_scanned += 1
            redacted, _ = self.redact_value(obj)
            return redacted

        else:
            # Numbers, booleans, None — return as-is
            return obj

    def redact_trace(self, trace_obj: dict) -> dict:
        """Redact a single trace object."""
        return self.deep_walk(trace_obj)

    def report(self) -> str:
        """Generate redaction summary report."""
        lines = []
        lines.append("=" * 60)
        lines.append("REDACTION REPORT")
        lines.append("=" * 60)
        lines.append(f"Fields scanned: {self.fields_scanned}")
        
        total_redacted = sum(self.redaction_stats.values())
        lines.append(f"Values redacted: {total_redacted}")
        
        if total_redacted > 0:
            lines.append("\nBreakdown by type:")
            for pattern_name in sorted(REDACTION_PATTERNS.keys()):
                count = self.redaction_stats[pattern_name]
                if count > 0:
                    lines.append(f"  {pattern_name}: {count}")
        
        lines.append("=" * 60)
        return "\n".join(lines)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Redact PII and secrets from Langfuse trace exports",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 redact_traces.py input.json --output output.json
  python3 redact_traces.py input.json --dry-run --report
  python3 redact_traces.py input.json --report
        """
    )

    parser.add_argument(
        "input",
        help="Input NDJSON file with trace data",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file (default: stdout)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be redacted without writing",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Print redaction summary to stderr",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="YAML config for custom redaction rules (not implemented)",
    )

    args = parser.parse_args()

    redactor = TraceRedactor(dry_run=args.dry_run)

    # Read input (NDJSON format)
    try:
        input_file = open(args.input, "r")
    except FileNotFoundError:
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    output_file = open(args.output, "w") if args.output else sys.stdout

    try:
        line_num = 0
        for line in input_file:
            line_num += 1
            line = line.strip()
            if not line:
                continue

            try:
                trace_data = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"Error parsing line {line_num}: {e}", file=sys.stderr)
                continue

            # Redact the trace
            redacted_trace = redactor.redact_trace(trace_data)

            # Write to output
            output_file.write(json.dumps(redacted_trace) + "\n")

        if args.report:
            print(redactor.report(), file=sys.stderr)

        if args.output:
            print(f"Redacted {line_num} traces → {args.output}", file=sys.stderr)

    finally:
        input_file.close()
        if args.output:
            output_file.close()


if __name__ == "__main__":
    main()
