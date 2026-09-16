#!/usr/bin/env python3
"""Weekly Google SecOps health check against a LogForge mock.

Preferred env (no fragile JSON paste):
  SECOPS_BASE_URL
  SECOPS_PROJECT / SECOPS_LOCATION / SECOPS_INSTANCE
  SECOPS_SA_TYPE, SECOPS_SA_PROJECT_ID, SECOPS_SA_PRIVATE_KEY_ID,
  SECOPS_SA_PRIVATE_KEY (multiline PEM OK), SECOPS_SA_CLIENT_EMAIL, SECOPS_SA_CLIENT_ID

Legacy (optional):
  SECOPS_CREDENTIALS_B64 or SECOPS_CREDENTIALS_JSON

  SIMULATE_DRIFT=true → demo red run (wrong query params)
"""

from __future__ import annotations

import base64
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


def env(name: str, required: bool = True) -> str:
    value = os.environ.get(name, "").strip()
    if required and not value:
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


def credentials_from_flat_env() -> tuple[dict, str, str, str] | None:
    if not os.environ.get("SECOPS_SA_PRIVATE_KEY", "").strip():
        return None
    creds = {
        "type": os.environ.get("SECOPS_SA_TYPE", "").strip() or "service_account",
        "project_id": env("SECOPS_SA_PROJECT_ID"),
        "private_key_id": env("SECOPS_SA_PRIVATE_KEY_ID"),
        "private_key": os.environ["SECOPS_SA_PRIVATE_KEY"].replace("\\n", "\n"),
        "client_email": env("SECOPS_SA_CLIENT_EMAIL"),
        "client_id": env("SECOPS_SA_CLIENT_ID"),
    }
    return (
        creds,
        env("SECOPS_PROJECT"),
        env("SECOPS_LOCATION"),
        env("SECOPS_INSTANCE"),
    )


def load_cred_raw() -> str:
    b64 = os.environ.get("SECOPS_CREDENTIALS_B64", "").strip()
    if b64:
        b64 += "=" * (-len(b64) % 4)
        try:
            return base64.b64decode(b64).decode("utf-8")
        except Exception as e:
            print(f"SECOPS_CREDENTIALS_B64 is not valid base64: {e}", file=sys.stderr)
            sys.exit(2)
    return env("SECOPS_CREDENTIALS_JSON")


def parse_cred_blob(raw: str) -> dict:
    try:
        blob = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Credentials JSON is not valid: {e}", file=sys.stderr)
        sys.exit(2)
    if not isinstance(blob, dict):
        print("Credentials must be a JSON object", file=sys.stderr)
        sys.exit(2)
    return blob


def unwrap_credentials(blob: dict) -> dict:
    creds = blob.get("credentials", blob)
    if isinstance(creds, str):
        try:
            creds = json.loads(creds)
        except json.JSONDecodeError as e:
            print(f"credentials field is a string but not valid JSON: {e}", file=sys.stderr)
            sys.exit(2)
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
            f"Service-account credentials missing keys: {missing}. Found: {safe_keys}",
            file=sys.stderr,
        )
        sys.exit(2)
    return creds


def make_assertion(credentials: dict, base: str) -> str:
    """Sign SA JWT locally so we never POST private_key (staging WAF blocks that)."""
    import jwt  # PyJWT

    now = int(datetime.now(timezone.utc).timestamp())
    token_uri = credentials.get("token_uri") or f"{base}/token"
    payload = {
        "iss": credentials["client_email"],
        "aud": token_uri,
        "iat": now,
        "exp": now + 3600,
    }
    return jwt.encode(payload, credentials["private_key"], algorithm="RS256")


def main() -> int:
    base = env("SECOPS_BASE_URL").rstrip("/")
    simulate_drift = os.environ.get("SIMULATE_DRIFT", "false").lower() == "true"

    flat = credentials_from_flat_env()
    if flat:
        credentials, project, location, instance = flat
    else:
        cred_blob = parse_cred_blob(load_cred_raw())
        credentials = unwrap_credentials(cred_blob)
        project = cred_blob.get("project")
        location = cred_blob.get("location")
        instance = cred_blob.get("instance")
        if not all([project, location, instance]):
            print(
                "Need project, location, instance (flat SECOPS_* envs or JSON blob).",
                file=sys.stderr,
            )
            return 2

    print(f"Using base URL: {base}")
    print(f"Using project={project} location={location} instance={instance}")

    print("1) Sign assertion locally…")
    try:
        assertion = make_assertion(credentials, base)
    except Exception as e:
        print(f"Failed to sign assertion: {e}", file=sys.stderr)
        return 1

    print("2) Exchange assertion for access token…")
    status, token_body = http_json(
        "POST",
        f"{base}/token",
        {
            "assertion": assertion,
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        },
    )
    if status != 200 or "access_token" not in token_body:
        print(f"Token failed ({status}): {token_body}", file=sys.stderr)
        if status == 0:
            print(
                "HINT: GitHub runners cannot reach *.localhost. Use staging.",
                file=sys.stderr,
            )
        return 1
    token = token_body["access_token"]

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
