"""LogForge control-plane helpers: login → create mock → fetch details → purge."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class MockEnv:
    plugin_id: int | None
    base_url: str
    credentials: dict[str, Any]
    meta: dict[str, Any]


def _http_json(method: str, url: str, body: dict | None = None, token: str | None = None):
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
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode() or "{}"
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode() if e.fp else ""
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return e.code, payload


class LogForgeClient:
    def __init__(self, host: str, email: str, password: str):
        self.host = host.rstrip("/")
        self.email = email
        self.password = password
        self._token: str | None = None

    def login(self) -> str:
        status, body = _http_json(
            "POST",
            f"{self.host}/lf-api/auth/login",
            {"email": self.email, "password": self.password},
        )
        if status != 200 or not body.get("token"):
            raise RuntimeError(f"LogForge login failed ({status}): {body}")
        self._token = body["token"]
        return self._token

    @property
    def token(self) -> str:
        if not self._token:
            self.login()
        return self._token  # type: ignore[return-value]

    def create_mock(self, org_id: int, platform_id: int) -> dict:
        status, body = _http_json(
            "POST",
            f"{self.host}/lf-api/plugin/create",
            {"orgId": org_id, "platformId": platform_id, "labType": "MockLab"},
            token=self.token,
        )
        if status not in (200, 201):
            raise RuntimeError(f"Create mock failed ({status}): {body}")
        return body

    def get_plugin(self, plugin_id: int) -> dict:
        status, body = _http_json(
            "GET",
            f"{self.host}/lf-api/plugin/{plugin_id}",
            token=self.token,
        )
        if status != 200:
            raise RuntimeError(f"Get plugin failed ({status}): {body}")
        return body

    def purge_mock(self, plugin_id: int) -> None:
        status, body = _http_json(
            "POST",
            f"{self.host}/lf-api/plugin/delete/{plugin_id}",
            token=self.token,
        )
        if status not in (200, 201, 204):
            raise RuntimeError(f"Purge mock failed ({status}): {body}")


def from_env_or_demo_config(demo_config_path: str) -> MockEnv:
    """Prefer committed demo_config.json for marketing demos; else create via API."""
    if os.path.exists(demo_config_path):
        cfg = json.loads(open(demo_config_path).read())
        return MockEnv(
            plugin_id=None,
            base_url=cfg["base_url"],
            credentials={"bearer_token": cfg["bearer_token"]},
            meta={
                "project": cfg.get("project"),
                "location": cfg.get("location"),
                "instance": cfg.get("instance"),
                "source": "demo_config.json",
            },
        )

    host = os.environ["LOGFORGE_HOST"]
    email = os.environ["LOGFORGE_EMAIL"]
    password = os.environ["LOGFORGE_PASSWORD"]
    org_id = int(os.environ["LOGFORGE_ORG_ID"])
    platform_id = int(os.environ["LOGFORGE_PLATFORM_ID"])

    client = LogForgeClient(host, email, password)
    created = client.create_mock(org_id, platform_id)
    plugin_id = created.get("id") or created.get("pluginId")
    if not plugin_id:
        raise RuntimeError(f"Create response missing plugin id: {created}")
    details = client.get_plugin(int(plugin_id))
    base_url = details.get("fullURL") or details.get("serverUrl") or details.get("url")
    cred = details.get("cred") or details.get("credentials") or {}
    if isinstance(cred, str):
        cred = json.loads(cred)
    return MockEnv(
        plugin_id=int(plugin_id),
        base_url=str(base_url),
        credentials=cred if isinstance(cred, dict) else {"raw": cred},
        meta={"source": "logforge_api", "raw": details},
    )
