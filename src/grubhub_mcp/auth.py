"""Grubhub authentication flows."""

from __future__ import annotations

from typing import Any

from .client import API_KEY, GrubhubClient


async def create_anonymous_session(client: GrubhubClient) -> dict[str, Any]:
    """Create an anonymous session for unauthenticated browsing."""
    payload = {
        "brand": "GRUBHUB",
        "client_id": API_KEY,
        "scope": "anonymous",
    }
    data = await client.post("/auth/anon", data=payload, auth_required=False)
    client.session.set_anonymous(data)
    return data


async def login(client: GrubhubClient, email: str, password: str) -> dict[str, Any]:
    """Authenticate with email and password."""
    payload = {
        "brand": "GRUBHUB",
        "client_id": API_KEY,
        "email": email,
        "password": password,
    }
    data = await client.post("/auth/login", data=payload, auth_required=False)
    client.session.set_authenticated(data)
    return data


async def logout(client: GrubhubClient) -> dict[str, Any]:
    """Log out and clear session."""
    try:
        data = await client.post("/auth/logout", auth_required=True)
    except Exception:
        data = {}
    client.session.clear()
    return data


async def get_session(client: GrubhubClient) -> dict[str, Any]:
    """Get current authenticated session info."""
    return await client.get("/session", auth_required=True)


async def send_otp(client: GrubhubClient, email: str) -> dict[str, Any]:
    """Send a one-time passcode for authentication."""
    payload = {
        "brand": "GRUBHUB",
        "client_id": API_KEY,
        "email": email,
    }
    return await client.post("/auth/confirmation_code", data=payload, auth_required=False)


async def verify_otp(client: GrubhubClient, email: str, code: str) -> dict[str, Any]:
    """Verify OTP and authenticate."""
    payload = {
        "brand": "GRUBHUB",
        "client_id": API_KEY,
        "email": email,
        "confirmation_code": code,
    }
    data = await client.put("/auth/confirmation_code", data=payload, auth_required=False)
    client.session.set_authenticated(data)
    return data


async def create_account(
    client: GrubhubClient,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
) -> dict[str, Any]:
    """Create a new Grubhub account."""
    payload = {
        "brand": "GRUBHUB",
        "client_id": API_KEY,
        "email": email,
        "password": password,
        "first_name": first_name,
        "last_name": last_name,
    }
    data = await client.post("/credentials", data=payload, auth_required=False)
    client.session.set_authenticated(data)
    return data


async def get_account_details(client: GrubhubClient) -> dict[str, Any]:
    """Get account details for the current user."""
    if not client.session.diner_udid:
        return {"error": "Not authenticated"}
    return await client.get(f"/credentials/{client.session.diner_udid}")


async def send_password_reset_otp(client: GrubhubClient, email: str) -> dict[str, Any]:
    """Send OTP for password reset."""
    payload = {
        "brand": "GRUBHUB",
        "client_id": API_KEY,
        "email": email,
    }
    return await client.post(
        "/forgot_password/confirmation_code", data=payload, auth_required=False
    )
