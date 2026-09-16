#!/usr/bin/env python3
"""Weekly Google SecOps health check against a LogForge mock.

Env:
  SECOPS_BASE_URL          e.g. https://google-secops-<sub>.staging.logforge.net
  SECOPS_CREDENTIALS_JSON  full JSON from LogForge (credentials + project/location/instance)
  SIMULATE_DRIFT           if "true", send wrong query param (demo red run)
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

REQUIRED_CRED_KEYS = (
    "type",
    "project_id",
    "private_key_id",
    "private_key",
    "client_email",
    "client_id",
)


def env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"Missing required env: {name}", file=sys.stderr)
        sys.exit(2)
    return value


def http_json(method: str, url: str, body: dict | None = None, token: str | None = None):
    data = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
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


def parse_cred_blob(raw: str) -> dict:
    try:
        blob = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"SECOPS_CREDENTIALS_JSON is not valid JSON: {e}", file=sys.stderr)
        sys.exit(2)
    if not isinstance(blob, dict):
        print("SECOPS_CREDENTIALS_JSON must be a JSON object", file=sys.stderr)
        sys.exit(2)
    return blob


def unwrap_credentials(blob: dict) -> dict:
    """Accept flat SA JSON, {credentials: {...}}, or credentials as a JSON string."""
    creds = blob.get("credentials", blob)
    if isinstance(creds, str):
        try:
            creds = json.loads(creds)
        except json.JSONDecodeError as e:
            print(f"credentials field is a string but not valid JSON: {e}", file=sys.stderr)
            sys.exit(2)
    # unwrap accidental double nesting
    while (
        isinstance(creds, dict)
        and "type" not in creds
        and isinstance(creds.get("credentials"), (dict, str))
    ):
        inner = creds["credentials"]
        if isinstance(inner, str):
            inner = json.loads(inner)
        creds = inner
    if not isinstance(creds, dict):
        print(f"credentials must be an object, got {type(creds).__name__}", file=sys.stderr)
        sys.exit(2)
    missing = [k for k in REQUIRED_CRED_KEYS if k not in creds]
    if missing:
        safe_keys = sorted(k for k in creds.keys() if k != "private_key")
        print(
            "Service-account credentials missing keys: "
            f"{missing}. Found keys: {safe_keys}. "
            "Secret must look like "
            '{"credentials":{"type":"service_account",...},"project":"...","location":"...","instance":"..."}',
            file=sys.stderr,
        )
        sys.exit(2)
    return creds


def main() -> int:
    base = env("SECOPS_BASE_URL").rstrip("/")
    cred_blob = parse_cred_blob(env("SECOPS_CREDENTIALS_JSON"))
    simulate_drift = os.environ.get("SIMULATE_DRIFT", "false").lower() == "true"

    credentials = unwrap_credentials(cred_blob)
    project = cred_blob.get("project")
    location = cred_blob.get("location")
    instance = cred_blob.get("instance")
    if not all([project, location, instance]):
        print(
            "SECOPS_CREDENTIALS_JSON must include top-level project, location, instance. "
            f"Found top-level keys: {sorted(cred_blob.keys())}",
            file=sys.stderr,
        )
        return 2

    print(f"Using base URL: {base}")
    print(f"Using project={project} location={location} instance={instance}")

    print("1) Request assertion from mock auth…")
    status, auth_body = http_json(
        "POST",
        f"{base}/o/oauth2/auth",
        {
            "type": credentials["type"],
            "project_id": credentials["project_id"],
            "private_key_id": credentials["private_key_id"],
            "private_key": credentials["private_key"],
            "client_email": credentials["client_email"],
            "client_id": credentials["client_id"],
        },
    )
    if status != 200 or "assertion" not in auth_body:
        print(f"Auth failed ({status}): {auth_body}", file=sys.stderr)
        if status == 0:
            print(
                "HINT: GitHub runners cannot reach *.localhost. "
                "Use a staging LogForge mock URL for Actions.",
                file=sys.stderr,
            )
        return 1

    print("2) Exchange assertion for access token…")
    status, token_body = http_json(
        "POST",
        f"{base}/token",
        {
            "assertion": auth_body["assertion"],
            "grant_type": auth_body.get(
                "grant_type", "urn:ietf:params:oauth:grant-type:jwt-bearer"
            ),
        },
    )
    if status != 200 or "access_token" not in token_body:
        print(f"Token failed ({status}): {token_body}", file=sys.stderr)
        return 1
    token = token_body["access_token"]

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=7)

    if simulate_drift:
        print(
            "SIMULATE_DRIFT=true → WRONG params "
            "timeRange.start / timeRange.end (expected: timeRange.start_time)"
        )
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

    print("3) Fetch alerts…")
    status, alerts_body = http_json("GET", url, token=token)
    print(f"HTTP {status}: {json.dumps(alerts_body)[:500]}")

    if status != 200:
        print(
            "FAIL: expected HTTP 200 from LogForge mock. "
            "Weekly check caught contract drift.",
            file=sys.stderr,
        )
        return 1

    print("PASS: Google SecOps weekly health check succeeded against LogForge.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
