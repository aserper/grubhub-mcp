"""Offline diagnostic tests; never use the persisted session or live API."""
from types import SimpleNamespace
import json
import unittest
from unittest.mock import AsyncMock, patch

import httpx

from src.grubhub_mcp.tools import auth as auth_tools


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def register(function):
            self.tools[function.__name__] = function
            return function
        return register


class AuthDiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = SimpleNamespace(
            session=SimpleNamespace(is_authenticated=True, diner_udid="diner-123",
                                    auth_token="secret-token", csrf_token="secret-csrf",
                                    login_generation=None),
            get=AsyncMock(return_value={"private_profile": "do-not-return"}),
            put=AsyncMock(),
        )
        mcp = FakeMCP()
        auth_tools.register(mcp)
        self.tools = mcp.tools
        patcher = patch.object(auth_tools, "get_client", return_value=self.client)
        patcher.start()
        self.addCleanup(patcher.stop)

    async def test_default_distinguishes_stored_state_without_remote_verification(self):
        result = json.loads(await self.tools["get_session_info"]())
        self.assertTrue(result["is_authenticated"])
        self.assertEqual(result["diner_udid"], "diner-123")
        self.assertTrue(result["has_token"])
        self.assertTrue(result["stored_is_authenticated"])
        self.assertIsNone(result["verified_is_authenticated"])
        self.assertEqual(result["verification_status"], "not_checked")
        self.client.get.assert_not_awaited()
        self.assertNotIn("secret-token", json.dumps(result))

    async def test_verify_probes_authenticated_profile_without_returning_profile(self):
        result = json.loads(await self.tools["get_session_info"](verify=True))
        self.client.get.assert_awaited_once_with("/diners/diner-123/details", auth_required=True)
        self.assertTrue(result["verified_is_authenticated"])
        self.assertEqual(result["verification_status"], "authenticated")
        self.assertFalse(result["relogin_required"])
        self.assertNotIn("do-not-return", json.dumps(result))

    async def test_verify_401_reports_relogin_without_changing_stored_flag(self):
        request = httpx.Request("GET", "https://example.test/profile")
        self.client.get.side_effect = httpx.HTTPStatusError(
            "secret-token", request=request, response=httpx.Response(401, request=request))
        result = json.loads(await self.tools["get_session_info"](verify=True))
        self.assertTrue(result["stored_is_authenticated"])
        self.assertTrue(result["is_authenticated"])
        self.assertFalse(result["verified_is_authenticated"])
        self.assertEqual(result["verification_status"], "relogin_required")
        self.assertTrue(result["relogin_required"])
        self.assertIn("log in", result["error"].lower())
        self.assertNotIn("secret-token", json.dumps(result))
        self.assertTrue(self.client.session.is_authenticated)

    async def test_probe_failures_leave_health_unknown_without_leaking_errors(self):
        request = httpx.Request("GET", "https://example.test/profile")
        errors: list[Exception] = [httpx.HTTPStatusError("secret-token", request=request,
                                      response=httpx.Response(status, request=request))
                  for status in (403, 429, 500)]
        errors += [httpx.ConnectError("secret-token", request=request),
                   httpx.ReadTimeout("secret-token", request=request),
                   ValueError("secret-token")]
        for error in errors:
            with self.subTest(error=type(error).__name__, status=getattr(getattr(error, "response", None), "status_code", None)):
                self.client.get.side_effect = error
                result = json.loads(await self.tools["get_session_info"](verify=True))
                self.assertIsNone(result["verified_is_authenticated"])
                self.assertIsNone(result["relogin_required"])
                self.assertEqual(result["verification_status"], "failed")
                self.assertNotIn("expired", result["error"].lower())
                self.assertNotIn("secret-token", json.dumps(result))

    async def test_verify_incomplete_or_anonymous_state_never_probes_profile(self):
        for field, value in (("is_authenticated", False), ("diner_udid", None), ("auth_token", None)):
            with self.subTest(field=field):
                previous = getattr(self.client.session, field)
                setattr(self.client.session, field, value)
                try:
                    result = json.loads(await self.tools["get_session_info"](verify=True))
                    self.assertEqual(result["verification_status"], "relogin_required")
                    self.assertIsNone(result["verified_is_authenticated"])
                    self.assertTrue(result["relogin_required"])
                    self.client.get.assert_not_awaited()
                finally:
                    setattr(self.client.session, field, previous)

    async def test_real_otp_verify_401_has_safe_helpful_error(self):
        request = httpx.Request("PUT", "https://example.test/auth/confirmation_code")
        self.client.put.side_effect = httpx.HTTPStatusError(
            "secret-token secret-csrf 123456", request=request,
            response=httpx.Response(401, request=request))
        raw = await self.tools["verify_login_otp"]("private@example.test", "123456")
        self.assertEqual(json.loads(raw), {
            "error": "OTP expired or invalid — request a new code with send_login_otp"
        })
        self.client.put.assert_awaited_once_with(
            "/auth/confirmation_code",
            data={"brand": "GRUBHUB", "client_id": auth_tools.auth_module.API_KEY,
                  "email": "private@example.test", "csrf_token": "secret-csrf",
                  "confirmation_code": "123456"}, auth_required=True)
        for secret in ("secret-token", "secret-csrf", "123456", "private@example.test"):
            self.assertNotIn(secret, raw)
        self.client.get.assert_not_awaited()

    async def test_real_otp_verify_non401_errors_are_not_reported_as_invalid_otp(self):
        request = httpx.Request("PUT", "https://example.test/auth/confirmation_code")
        errors: list[Exception] = [httpx.HTTPStatusError("failure", request=request,
                                      response=httpx.Response(status, request=request))
                  for status in (400, 403, 429, 500)]
        errors.append(httpx.ConnectError("network failure", request=request))
        for error in errors:
            with self.subTest(error=type(error).__name__):
                self.client.put.side_effect = error
                with self.assertRaises(type(error)) as raised:
                    await self.tools["verify_login_otp"]("private@example.test", "123456")
                self.assertIs(raised.exception, error)

    async def test_real_otp_verify_missing_session_preserves_prerequisite_error(self):
        self.client.session.auth_token = None
        with self.assertRaisesRegex(ValueError, "call send_login_otp first"):
            await self.tools["verify_login_otp"]("private@example.test", "123456")
        self.client.put.assert_not_awaited()

