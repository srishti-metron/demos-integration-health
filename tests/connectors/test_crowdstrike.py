#!/usr/bin/env python3
"""CrowdStrike connector health — placeholder."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.health.logforge_client import MockEnv
from tests.health.runner import run_connector


def checks(env: MockEnv) -> None:
    raise NotImplementedError("CrowdStrike checks not wired yet — placeholder only.")


def main() -> int:
    print("crowdstrike: placeholder (skip)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
