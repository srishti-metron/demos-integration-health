"""Create → test → purge harness for one connector."""

from __future__ import annotations

import os
import sys
import traceback
from collections.abc import Callable
from pathlib import Path

from tests.health.logforge_client import MockEnv, LogForgeClient, from_env_or_demo_config

ROOT = Path(__file__).resolve().parents[2]
DEMO_CONFIG = ROOT / "demo_config.json"


def run_connector(
    name: str,
    checks: Callable[[MockEnv], None],
) -> int:
    """
    Lifecycle:
      1) provision mock (demo_config.json OR LogForge create API)
      2) run connector checks
      3) purge mock if we created one
    """
    print(f"=== {name}: provision ===")
    env: MockEnv | None = None
    client: LogForgeClient | None = None
    exit_code = 0

    try:
        env = from_env_or_demo_config(str(DEMO_CONFIG))
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
        elif env and env.meta.get("source") == "demo_config.json":
            print("=== skip purge (using shared demo_config mock) ===")

    return exit_code
