#!/usr/bin/env python3
"""Google SecOps connector health checks.

Client path: provision (demo_config or create API) → alerts check → purge if created.

Demo-only: DEMO_SIMULATE_DRIFT=true sends wrong query params to show contract drift on camera.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.health.assertions import expect_status, print_drift_diff
from tests.health.logforge_client import MockEnv
from tests.health.runner import run_connector


def http_get(url: str, token: str):
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "logforge-demo/1.0",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode() if e.fp else ""
        try:
            body = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            body = {"raw": raw}
        return e.code, body


def checks(env: MockEnv) -> None:
    token = env.credentials.get("bearer_token")
    if not token:
        raise RuntimeError(
            "No bearer_token in env.credentials. "
            "demo_config.json path provides one; API path should mint a token from plugin creds."
        )

    project = env.meta.get("project")
    location = env.meta.get("location")
    instance = env.meta.get("instance")
    if not all([project, location, instance]):
        raise RuntimeError("Need project/location/instance in mock meta (demo_config or plugin details).")

    simulate_drift = os.environ.get("DEMO_SIMULATE_DRIFT", os.environ.get("SIMULATE_DRIFT", "false")).lower() == "true"
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=7)
    expected_params = ["timeRange.start_time", "timeRange.end_time", "maxNumAlertsToReturn"]

    if simulate_drift:
        print("DEMO_SIMULATE_DRIFT=true → sending wrong params (marketing demo only)")
        query = {
            "timeRange.start": start.isoformat().replace("+00:00", "Z"),
            "timeRange.end": end.isoformat().replace("+00:00", "Z"),
            "maxNumAlertsToReturn": "10",
        }
    else:
        query = {
            "timeRange.start_time": start.isoformat().replace("+00:00", "Z"),
            "timeRange.end_time": end.isoformat().replace("+00:00", "Z"),
            "maxNumAlertsToReturn": "10",
        }

    path = (
        f"/v1alpha/projects/{project}/locations/{location}/instances/{instance}"
        f"/legacy:legacySearchRulesAlerts"
    )
    url = f"{env.base_url.rstrip('/')}{path}?{urllib.parse.urlencode(query)}"
    print(f"Request params sent: {list(query.keys())}")
    status, body = http_get(url, token)
    print(f"HTTP {status}: {json.dumps(body)[:300]}")

    if status != 200:
        if simulate_drift:
            print_drift_diff(
                expected_params=expected_params,
                sent_params=list(query.keys()),
                status=status,
                body=body,
            )
        expect_status(status, 200, context="Google SecOps alerts", body=body)


def main() -> int:
    return run_connector("google-secops", checks)


if __name__ == "__main__":
    raise SystemExit(main())
