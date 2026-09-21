#!/usr/bin/env python3
"""Thin entrypoint — SecOps logic lives under integrations/google_secops/."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from integrations.google_secops.checks import run_checks
from tests.health.runner import run_connector


def main() -> int:
    return run_connector(
        "google_secops",
        run_checks,
        demo_env_path=ROOT / "integrations" / "google_secops" / "demo_env.json",
    )


if __name__ == "__main__":
    raise SystemExit(main())
