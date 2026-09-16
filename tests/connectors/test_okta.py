#!/usr/bin/env python3
"""Okta connector health — placeholder."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main() -> int:
    print("okta: placeholder (skip)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
