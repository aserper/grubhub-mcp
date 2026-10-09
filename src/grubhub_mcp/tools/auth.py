"""Authentication MCP tools."""

from __future__ import annotations

import json
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

from ..client import get_client
from .. import auth as auth_module


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def login(email: str, password: str) -> str:
        """Log in to Grubhub with email and password. Returns session info on success."""
        client = get_client()
        data = await auth_module.login(client, email, password)
        return json.dumps(
            {
                "status": "authenticated",
                "diner_udid": client.session.diner_udid,
                "email": email,
            },
            indent=2,
        )

    @mcp.tool()
    async def logout() -> str:
        """Log out of the current Grubhub session."""
        client = get_client()
        await auth_module.logout(client)
        return json.dumps({"status": "logged_out"})

    @mcp.tool()
    async def get_session_info(verify: bool = False) -> str:
        """Report stored session state, not proof of a healthy login.

        Legacy is_authenticated is the stored flag. Set verify=True to probe
        the authenticated profile through the normal client (including refresh).
        The token value and profile data are never included in this diagnostic.
        """
        client = get_client()
        result = {
            "is_authenticated": client.session.is_authenticated,
            "diner_udid": client.session.diner_udid,
            "has_token": client.session.auth_token is not None,
            "stored_is_authenticated": client.session.is_authenticated,
            "verified_is_authenticated": None,
            "verification_status": "not_checked",
        }
        if verify and not (
            client.session.is_authenticated
            and client.session.diner_udid
            and client.session.auth_token
        ):
            result.update(
                verification_status="relogin_required",
                relogin_required=True,
                error="No complete authenticated session is stored. Please log in again.",
            )
            return json.dumps(result, indent=2)
        if verify:
            try:
                await client.get(
                    f"/diners/{client.session.diner_udid}/details", auth_required=True
                )
            except (httpx.HTTPError, ValueError) as exc:
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 401:
                    result.update(
                        verified_is_authenticated=False,
                        verification_status="relogin_required",
                        relogin_required=True,
                        error="Authentication was rejected; the session may have expired. Please log in again.",
                    )
                else:
                    result.update(
                        verification_status="failed",
                        relogin_required=None,
                        error="Unable to verify session health. Please retry; authentication status is unknown.",
                    )
            else:
                result.update(
                    verified_is_authenticated=True,
                    verification_status="authenticated",
                    relogin_required=False,
                )
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def send_login_otp(email: str) -> str:
        """Send a one-time passcode to the given email for login."""
        client = get_client()
        data = await auth_module.send_otp(client, email)
        return json.dumps({"status": "otp_sent", "email": email})

    @mcp.tool()
    async def verify_login_otp(email: str, code: str) -> str:
        """Verify a one-time passcode and complete login."""
        client = get_client()
        try:
            data = await auth_module.verify_otp(client, email, code)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                return json.dumps(
                    {"error": "OTP expired or invalid — request a new code with send_login_otp"}
                )
            raise
        return json.dumps(
            {
                "status": "authenticated",
                "diner_udid": client.session.diner_udid,
            },
            indent=2,
        )

    @mcp.tool()
    async def create_account(
        email: str, password: str, first_name: str, last_name: str
    ) -> str:
        """Create a new Grubhub account."""
        client = get_client()
        data = await auth_module.create_account(
            client, email, password, first_name, last_name
        )
        return json.dumps(
            {
                "status": "account_created",
                "diner_udid": client.session.diner_udid,
            },
            indent=2,
        )

    @mcp.tool()
    async def send_password_reset(email: str) -> str:
        """Send a password reset OTP to the given email."""
        client = get_client()
        await auth_module.send_password_reset_otp(client, email)
        return json.dumps({"status": "reset_otp_sent", "email": email})
