"""Grubhub HTTP client with authentication and header management."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api-gtm.grubhub.com"
AUTH_BASE_URL = "https://api-gtm.grubhub.com"
API_KEY = "ghandroid_Ujtwar5s9e3RYiSNV31X41y2hsK6Kh1Uv7JDrkpS"

# File-based session persistence so auth survives across stdio invocations
_SESSION_DIR = Path(os.environ.get("GRUBHUB_SESSION_DIR", Path.home() / ".grubhub-mcp"))
_SESSION_FILE = _SESSION_DIR / "session.json"


class GrubhubSession:
    """Manages authentication state for a Grubhub session."""

    def __init__(self) -> None:
        self.auth_token: str | None = None
        self.refresh_token: str | None = None
        self.diner_udid: str | None = None
        self.browser_id: str = str(uuid4())
        self.is_authenticated: bool = False
        self.session_handle: dict[str, Any] | None = None
        self.csrf_token: str | None = None
        self._load()

    def _load(self) -> None:
        """Load persisted session from disk if available."""
        try:
            if _SESSION_FILE.exists():
                data = json.loads(_SESSION_FILE.read_text())
                self.auth_token = data.get("auth_token")
                self.refresh_token = data.get("refresh_token")
                self.diner_udid = data.get("diner_udid")
                self.browser_id = data.get("browser_id", self.browser_id)
                self.is_authenticated = data.get("is_authenticated", False)
                self.session_handle = data.get("session_handle")
                self.csrf_token = data.get("csrf_token")
        except Exception:
            logger.debug("Failed to load persisted session", exc_info=True)

    def _save(self) -> None:
        """Persist session state to disk."""
        try:
            _SESSION_DIR.mkdir(parents=True, exist_ok=True)
            _SESSION_FILE.write_text(json.dumps({
                "auth_token": self.auth_token,
                "refresh_token": self.refresh_token,
                "diner_udid": self.diner_udid,
                "browser_id": self.browser_id,
                "is_authenticated": self.is_authenticated,
                "session_handle": self.session_handle,
                "csrf_token": self.csrf_token,
            }))
            _SESSION_FILE.chmod(0o600)
        except Exception:
            logger.debug("Failed to persist session", exc_info=True)

    def set_authenticated(self, session_data: dict[str, Any]) -> None:
        self.auth_token = session_data.get("session_handle", {}).get("access_token")
        if not self.auth_token:
            self.auth_token = session_data.get("auth_token")
        self.refresh_token = session_data.get("session_handle", {}).get("refresh_token")
        credential = session_data.get("credential", {})
        self.diner_udid = credential.get("ud_id") or credential.get("udid")
        self.session_handle = session_data.get("session_handle")
        self.is_authenticated = True
        self._save()

    def set_anonymous(self, session_data: dict[str, Any]) -> None:
        self.auth_token = session_data.get("session_handle", {}).get("access_token")
        if not self.auth_token:
            self.auth_token = session_data.get("auth_token")
        self.refresh_token = session_data.get("session_handle", {}).get("refresh_token")
        self.session_handle = session_data.get("session_handle")
        self.is_authenticated = False
        self._save()

    def clear(self) -> None:
        self.auth_token = None
        self.refresh_token = None
        self.diner_udid = None
        self.is_authenticated = False
        self.session_handle = None
        self.csrf_token = None
        try:
            if _SESSION_FILE.exists():
                _SESSION_FILE.unlink()
        except Exception:
            pass


class GrubhubClient:
    """HTTP client for Grubhub API with automatic auth handling."""

    def __init__(self) -> None:
        self.session = GrubhubSession()
        self._http = httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=30.0,
            follow_redirects=True,
        )

    def _headers(self, auth_required: bool = True) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "x-gh-browser-id": self.session.browser_id,
            "Vary": "Accept-Encoding",
        }
        if self.session.auth_token and auth_required:
            headers["Authorization"] = f"Bearer {self.session.auth_token}"
        return headers

    async def _handle_response(self, resp: httpx.Response) -> dict[str, Any]:
        if resp.status_code == 401 and self.session.refresh_token:
            refreshed = await self._refresh_token()
            if refreshed:
                # Retry not possible here — caller should retry
                pass
        resp.raise_for_status()
        if resp.status_code == 204 or not resp.content:
            return {}
        return resp.json()

    async def _refresh_token(self) -> bool:
        try:
            payload: dict[str, Any] = {}
            if self.session.is_authenticated:
                payload = {
                    "brand": "GRUBHUB",
                    "client_id": API_KEY,
                    "refresh_token": self.session.refresh_token,
                }
            else:
                payload = {
                    "brand": "GRUBHUB",
                    "client_id": API_KEY,
                    "refresh_token": self.session.refresh_token,
                }
            resp = await self._http.post(
                "/auth/refresh",
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if resp.is_success:
                data = resp.json()
                if self.session.is_authenticated:
                    self.session.set_authenticated(data)
                else:
                    self.session.set_anonymous(data)
                return True
        except Exception:
            logger.exception("Token refresh failed")
        return False

    async def get(
        self, path: str, params: Any = None, auth_required: bool = True
    ) -> dict[str, Any]:
        resp = await self._http.get(
            path, headers=self._headers(auth_required), params=params
        )
        if resp.status_code == 401 and self.session.refresh_token:
            if await self._refresh_token():
                resp = await self._http.get(
                    path, headers=self._headers(auth_required), params=params
                )
        resp.raise_for_status()
        if not resp.content:
            return {}
        return resp.json()

    async def post(
        self,
        path: str,
        data: dict[str, Any] | None = None,
        auth_required: bool = True,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        resp = await self._http.post(
            path, headers=self._headers(auth_required), json=data, params=params
        )
        if resp.status_code == 401 and self.session.refresh_token:
            if await self._refresh_token():
                resp = await self._http.post(
                    path, headers=self._headers(auth_required), json=data, params=params
                )
        resp.raise_for_status()
        if not resp.content:
            return {}
        return resp.json()

    async def put(
        self, path: str, data: dict[str, Any] | None = None, auth_required: bool = True
    ) -> dict[str, Any]:
        resp = await self._http.put(
            path, headers=self._headers(auth_required), json=data
        )
        if resp.status_code == 401 and self.session.refresh_token:
            if await self._refresh_token():
                resp = await self._http.put(
                    path, headers=self._headers(auth_required), json=data
                )
        resp.raise_for_status()
        if not resp.content:
            return {}
        return resp.json()

    async def delete(
        self, path: str, auth_required: bool = True
    ) -> dict[str, Any]:
        resp = await self._http.delete(
            path, headers=self._headers(auth_required)
        )
        if resp.status_code == 401 and self.session.refresh_token:
            if await self._refresh_token():
                resp = await self._http.delete(
                    path, headers=self._headers(auth_required)
                )
        resp.raise_for_status()
        if not resp.content:
            return {}
        return resp.json()

    async def close(self) -> None:
        await self._http.aclose()


# Singleton client instance shared across tools
_client: GrubhubClient | None = None


def get_client() -> GrubhubClient:
    global _client
    if _client is None:
        _client = GrubhubClient()
    return _client
