"""Shared assertion helpers (no vendor-specific data)."""

from __future__ import annotations

import json
import sys


def expect_status(status: int, expected: int, *, context: str, body=None) -> None:
    if status == expected:
        return
    print("", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"ASSERTION FAILED: {context}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"Expected : HTTP {expected}", file=sys.stderr)
    print(f"Got      : HTTP {status}", file=sys.stderr)
    if body is not None:
        print(f"Body     : {json.dumps(body)[:500]}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    raise AssertionError(f"{context}: expected HTTP {expected}, got {status}")


def print_param_drift(
    *,
    title: str,
    expected_params: list[str],
    sent_params: list[str],
    status: int,
    body,
) -> None:
    print("", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"ASSERTION FAILED: {title}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print("Scenario : API request-contract drift", file=sys.stderr)
    print(f"Expected : HTTP 200 with params {expected_params}", file=sys.stderr)
    print(f"Sent     : params {sent_params}", file=sys.stderr)
    print(f"Got      : HTTP {status}  {json.dumps(body)}", file=sys.stderr)
    print("", file=sys.stderr)
    print("Diff:", file=sys.stderr)
    for p in expected_params:
        if p not in sent_params:
            print(f"  - {p}", file=sys.stderr)
    for p in sent_params:
        if p not in expected_params:
            print(f"  + {p}", file=sys.stderr)
    print("", file=sys.stderr)
    print(
        "Caught by weekly LogForge mock check — connector still uses old field names.",
        file=sys.stderr,
    )
    print("=" * 60, file=sys.stderr)
