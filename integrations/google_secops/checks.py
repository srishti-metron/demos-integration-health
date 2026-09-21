"""Google SecOps–specific health checks (lives with the integration)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tests.health.assertions import expect_status, print_param_drift
from tests.health.logforge_client import MockEnv

HERE = Path(__file__).resolve().parent
MANIFEST = json.loads((HERE / "manifest.json").read_text())


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


def run_checks(env: MockEnv) -> None:
    token = env.credentials.get("bearer_token")
    if not token:
        raise RuntimeError("No bearer_token — set demo_env.json or mint from plugin creds.")

    project = env.meta.get("project")
    location = env.meta.get("location")
    instance = env.meta.get("instance")
    if not all([project, location, instance]):
        raise RuntimeError("Need project/location/instance on mock env meta.")

    health = MANIFEST["health"]
    expected_params = health["expectedParams"]
    simulate_drift = (
        os.environ.get("DEMO_SIMULATE_DRIFT", os.environ.get("SIMULATE_DRIFT", "false")).lower()
        == "true"
    )

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=7)
    start_s = start.isoformat().replace("+00:00", "Z")
    end_s = end.isoformat().replace("+00:00", "Z")

    if simulate_drift:
        print("DEMO_SIMULATE_DRIFT=true → wrong params (marketing demo only)")
        query = {
            "timeRange.start": start_s,
            "timeRange.end": end_s,
            "maxNumAlertsToReturn": "10",
        }
    else:
        query = {
            "timeRange.start_time": start_s,
            "timeRange.end_time": end_s,
            "maxNumAlertsToReturn": "10",
        }

    path = health["endpoint"].format(
        project=project, location=location, instance=instance
    )
    url = f"{env.base_url.rstrip('/')}{path}?{urllib.parse.urlencode(query)}"
    print(f"Request params sent: {list(query.keys())}")
    status, body = http_get(url, token)
    print(f"HTTP {status}: {json.dumps(body)[:300]}")

    if status != 200:
        if simulate_drift:
            print_param_drift(
                title=f"{MANIFEST['name']} weekly health check",
                expected_params=expected_params,
                sent_params=list(query.keys()),
                status=status,
                body=body,
            )
        expect_status(status, 200, context=f"{MANIFEST['name']} alerts", body=body)
