"""Create → test → purge harness (vendor-agnostic)."""

from __future__ import annotations

import os
import sys
import traceback
from collections.abc import Callable
from pathlib import Path

from tests.health.logforge_client import MockEnv, LogForgeClient, from_env_or_demo_config

ROOT = Path(__file__).resolve().parents[2]


def run_connector(
    name: str,
    checks: Callable[[MockEnv], None],
    *,
    demo_env_path: Path | None = None,
) -> int:
    """
    Lifecycle:
      1) provision mock (integration demo_env.json OR LogForge create API)
      2) run connector checks (provided by integrations/<name>/)
      3) purge mock if we created one
    """
    print(f"=== {name}: provision ===")
    env: MockEnv | None = None
    client: LogForgeClient | None = None
    exit_code = 0
    demo_path = demo_env_path or (ROOT / "integrations" / name / "demo_env.json")

    try:
        env = from_env_or_demo_config(str(demo_path))
        print(f"Mock source: {env.meta.get('source')}")
        print(f"Base URL: {env.base_url}")

        print(f"=== {name}: checks ===")
        checks(env)
        print(f"=== {name}: PASS ===")
    except Exception as e:
        exit_code = 1
        print(f"=== {name}: FAIL ===", file=sys.stderr)
        print(str(e), file=sys.stderr)
        traceback.print_exc()
    finally:
        if env and env.plugin_id is not None:
            print(f"=== {name}: purge plugin {env.plugin_id} ===")
            try:
                if client is None:
                    client = LogForgeClient(
                        os.environ["LOGFORGE_HOST"],
                        os.environ["LOGFORGE_EMAIL"],
                        os.environ["LOGFORGE_PASSWORD"],
                    )
                client.purge_mock(env.plugin_id)
                print("Purge OK")
            except Exception as purge_err:
                print(f"Purge failed: {purge_err}", file=sys.stderr)
                exit_code = 1
        elif env and env.meta.get("source") == "demo_env.json":
            print("=== skip purge (using shared demo_env mock) ===")

    return exit_code
