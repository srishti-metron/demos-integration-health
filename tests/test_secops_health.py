#!/usr/bin/env python3
"""Weekly Google SecOps health check against a LogForge mock.

Preferred for the demo video:
  demo_config.json  { base_url, bearer_token, project, location, instance }

Optional overrides via env (same keys / SIMULATE_DRIFT).
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

CONFIG_PATH = Path(__file__).resolve().parents[1] / "demo_config.json"


def http_json(method: str, url: str, body: dict | None = None, token: str | None = None):
    data = None if body is None else json.dumps(body).encode()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "logforge-demo/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode() or "{}"
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode() if e.fp else ""
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return e.code, payload
    except urllib.error.URLError as e:
        return 0, {"error": str(e.reason)}


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print(f"Missing {CONFIG_PATH.name}. Generate a bearer token into that file first.", file=sys.stderr)
        sys.exit(2)
    cfg = json.loads(CONFIG_PATH.read_text())
    # env overrides for filming tweaks
    for key, env_name in (
        ("base_url", "SECOPS_BASE_URL"),
        ("bearer_token", "SECOPS_BEARER_TOKEN"),
        ("project", "SECOPS_PROJECT"),
        ("location", "SECOPS_LOCATION"),
        ("instance", "SECOPS_INSTANCE"),
    ):
        if os.environ.get(env_name, "").strip():
            cfg[key] = os.environ[env_name].strip()
    needed = ("base_url", "bearer_token", "project", "location", "instance")
    missing = [k for k in needed if not cfg.get(k)]
    if missing:
        print(f"{CONFIG_PATH.name} missing fields: {missing}", file=sys.stderr)
        sys.exit(2)
    return cfg


def main() -> int:
    cfg = load_config()
    base = cfg["base_url"].rstrip("/")
    token = cfg["bearer_token"]
    project, location, instance = cfg["project"], cfg["location"], cfg["instance"]
    simulate_drift = os.environ.get("SIMULATE_DRIFT", "false").lower() == "true"

    print(f"Using base URL: {base}")
    print(f"Using project={project} location={location} instance={instance}")
    print("Using bearer token from demo_config.json")

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=7)

    if simulate_drift:
        print("SIMULATE_DRIFT=true → WRONG params timeRange.start / timeRange.end")
        query = {
            "timeRange.start": start.isoformat().replace("+00:00", "Z"),
            "timeRange.end": end.isoformat().replace("+00:00", "Z"),
            "maxNumAlertsToReturn": "10",
        }
    else:
        print("Correct params: timeRange.start_time / timeRange.end_time")
        query = {
            "timeRange.start_time": start.isoformat().replace("+00:00", "Z"),
            "timeRange.end_time": end.isoformat().replace("+00:00", "Z"),
            "maxNumAlertsToReturn": "10",
        }

    path = (
        f"/v1alpha/projects/{project}/locations/{location}/instances/{instance}"
        f"/legacy:legacySearchRulesAlerts"
    )
    url = f"{base}{path}?{urllib.parse.urlencode(query)}"

    expected_params = ["timeRange.start_time", "timeRange.end_time", "maxNumAlertsToReturn"]
    sent_params = list(query.keys())

    print("Fetch alerts…")
    print(f"Request params sent: {sent_params}")
    status, alerts_body = http_json("GET", url, token=token)
    print(f"HTTP {status}: {json.dumps(alerts_body)[:500]}")

    if status == 401:
        print(
            "Token rejected (expired?). Regenerate demo_config.json bearer_token.",
            file=sys.stderr,
        )
        return 1

    if status != 200:
        print("", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("ASSERTION FAILED: Google SecOps weekly health check", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print("Scenario : API request-contract drift", file=sys.stderr)
        print("Endpoint : legacySearchRulesAlerts", file=sys.stderr)
        print(f"Expected : HTTP 200 with params {expected_params}", file=sys.stderr)
        print(f"Sent     : params {sent_params}", file=sys.stderr)
        print(f"Got      : HTTP {status}  {json.dumps(alerts_body)}", file=sys.stderr)
        if simulate_drift:
            print("", file=sys.stderr)
            print("Diff:", file=sys.stderr)
            print("  - timeRange.start_time", file=sys.stderr)
            print("  - timeRange.end_time", file=sys.stderr)
            print("  + timeRange.start", file=sys.stderr)
            print("  + timeRange.end", file=sys.stderr)
            print("", file=sys.stderr)
            print(
                "Caught by weekly LogForge mock check — connector still uses old field names.",
                file=sys.stderr,
            )
        print("=" * 60, file=sys.stderr)
        return 1

    print("PASS: Google SecOps weekly health check succeeded against LogForge.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
