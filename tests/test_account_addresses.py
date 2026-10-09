"""Address regression tests; all external calls are mocked."""
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from src.grubhub_mcp.tools import account


GEOCODE = {
    "street_address1": "90 Elmwood Rd",
    "address_locality": "Wellesley",
    "address_region": "MA",
    "postal_code": "02481",
    "latitude": "42.31146621",
    "longitude": "-71.30834198",
    "address_country": "US",
    "street_address2": None,
    "location_address": {
        "region_code": "US",
        "address_lines": ["90 Elmwood Rd"],
        "locality": "Wellesley",
        "administrative_area": "MA",
        "postal_code": "02481",
        "coordinates": {"latitude": 42.31146621, "longitude": -71.30834198},
    },
    "time_zone": {"id": "America/New_York"},
}


class ToolRegistry:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def register(func):
            self.tools[func.__name__] = func
            return func
        return register


class AddressTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = SimpleNamespace(
            session=SimpleNamespace(is_authenticated=True, diner_udid="diner-123"),
            get=AsyncMock(return_value=[deepcopy(GEOCODE)]),
            post=AsyncMock(return_value={"id": "address-123"}),
        )
        registry = ToolRegistry()
        account.register(registry)
        self.add_address = registry.tools["add_address"]
        patcher = patch.object(account, "get_client", return_value=self.client)
        patcher.start()
        self.addCleanup(patcher.stop)

    async def add(self, **kwargs):
        return json.loads(await self.add_address(
            "90 elmwood road", "Wellesley", "MA", "02428", **kwargs
        ))

    async def test_unauthenticated_or_missing_diner_id_makes_no_requests(self):
        for field, value in (("is_authenticated", False), ("diner_udid", None)):
            with self.subTest(field=field):
                previous = getattr(self.client.session, field)
                setattr(self.client.session, field, value)
                result = await self.add()
                self.assertIn("logged in", result["error"])
                self.client.get.assert_not_awaited()
                self.client.post.assert_not_awaited()
                setattr(self.client.session, field, previous)

    async def test_geocoder_exception_does_not_post(self):
        self.client.get.side_effect = RuntimeError("Geocoder unavailable")
        with self.assertRaisesRegex(RuntimeError, "Geocoder unavailable"):
            await self.add()
        self.client.post.assert_not_awaited()

    async def test_original_positional_arguments_remain_supported(self):
        result = json.loads(await self.add_address(
            "90 elmwood road", "Wellesley", "MA", "02428", "Apt 4B", "Ring bell", "Home"
        ))
        self.assertEqual(result, {"id": "address-123"})
        payload = self.client.post.await_args.kwargs["data"]
        self.assertEqual(payload["label"], "Home")
        self.assertEqual(payload["special_instructions"], "Ring bell")
        self.assertEqual(payload["street_address2"], "Apt 4B")

    async def test_invalid_canonical_address_metadata_does_not_post(self):
        for field, value in (
            ("street_address1", ""), ("address_country", None),
            ("address_locality", " "), ("postal_code", 2481),
            ("location_address", None), ("location_address", []),
            ("location_address", {}),
            ("address_lines", None), ("address_lines", "90 Elmwood Rd"),
            ("address_lines", []), ("address_lines", [None]),
            ("time_zone", None), ("time_zone", {}),
            ("time_zone", {"id": ""}),
        ):
            with self.subTest(field=field, value=value):
                canonical = deepcopy(GEOCODE)
                if field == "address_lines":
                    canonical["location_address"][field] = value
                else:
                    canonical[field] = value
                self.client.get.return_value = [canonical]
                result = await self.add()
                self.assertIn("incomplete", result["error"].lower())
                self.client.post.assert_not_awaited()

    async def test_malformed_geocoder_response_does_not_post(self):
        for response in ({"unexpected": "object"}, "unexpected", [None], ["unexpected"]):
            with self.subTest(response=response):
                self.client.get.return_value = response
                result = await self.add()
                self.assertIn("invalid", result["error"].lower())
                self.client.post.assert_not_awaited()

    async def test_missing_canonical_address_metadata_does_not_post(self):
        for field in (
            "street_address1", "address_country", "address_locality",
            "address_region", "postal_code", "location_address", "address_lines", "time_zone",
        ):
            with self.subTest(field=field):
                canonical = deepcopy(GEOCODE)
                if field == "address_lines":
                    del canonical["location_address"][field]
                else:
                    del canonical[field]
                self.client.get.return_value = [canonical]
                result = await self.add()
                self.assertIn("incomplete", result["error"].lower())
                self.client.post.assert_not_awaited()

    async def test_apartment_survives_geocoding_in_flat_and_nested_lines(self):
        await self.add(apt_suite="Apt 4B")
        self.client.get.assert_awaited_once_with(
            "/geocode", params={"address": "90 elmwood road, Apt 4B, Wellesley, MA 02428"}
        )
        payload = self.client.post.await_args.kwargs["data"]
        self.assertEqual(payload["street_address2"], "Apt 4B")
        self.assertEqual(payload["address_lines"], ["90 Elmwood Rd", "Apt 4B"])
        self.assertEqual(payload["address"]["address_lines"], payload["address_lines"])
        self.assertEqual(self.client.get.return_value, [GEOCODE])

    async def test_supplied_phone_is_sent_without_inventing_one(self):
        await self.add(phone="617-555-0100")
        self.assertEqual(self.client.post.await_args.kwargs["data"]["phone"], "617-555-0100")
        self.client.post.reset_mock()
        await self.add()
        self.assertNotIn("phone", self.client.post.await_args.kwargs["data"])

    async def test_missing_or_invalid_coordinates_do_not_post(self):
        for field, value in (
            ("latitude", None), ("longitude", None),
            ("latitude", ""), ("longitude", "invalid"),
            ("latitude", "nan"), ("longitude", "inf"),
            ("latitude", "91"), ("longitude", "-181"),
            ("latitude", True),
        ):
            with self.subTest(field=field, value=value):
                canonical = deepcopy(GEOCODE)
                if value is None:
                    del canonical[field]
                else:
                    canonical[field] = value
                self.client.get.return_value = [canonical]
                result = await self.add()
                self.assertIn("coordinates", result["error"].lower())
                self.client.post.assert_not_awaited()

    async def test_ambiguous_geocoder_results_do_not_post(self):
        self.client.get.return_value = [deepcopy(GEOCODE), deepcopy(GEOCODE)]
        result = await self.add()
        self.assertIn("ambiguous", result["error"].lower())
        self.client.post.assert_not_awaited()

    async def test_no_geocoder_result_does_not_post(self):
        self.client.get.return_value = []
        result = await self.add()
        self.assertIn("no results", result["error"].lower())
        self.client.post.assert_not_awaited()

    async def test_geocodes_before_posting_canonical_payload(self):
        result = await self.add(label="Home", delivery_instructions="Ring bell")
        self.assertEqual(result, {"id": "address-123"})
        self.client.get.assert_awaited_once_with(
            "/geocode", params={"address": "90 elmwood road, Wellesley, MA 02428"}
        )
        self.client.post.assert_awaited_once_with(
            "/diners/diner-123/addresses", data={
                **{key: GEOCODE[key] for key in (
                    "street_address1", "address_country", "address_locality",
                    "address_region", "postal_code", "latitude", "longitude",
                )},
                "region_code": "US",
                "address_lines": ["90 Elmwood Rd"],
                "address": {
                    "region_code": "US", "address_lines": ["90 Elmwood Rd"],
                    "locality": "Wellesley", "administrative_area": "MA",
                    "postal_code": "02481", "coordinates": GEOCODE["location_address"]["coordinates"],
                },
                "label": "Home", "special_instructions": "Ring bell",
                "fulfillment_type": "DELIVERY", "time_zone": GEOCODE["time_zone"],
            },
        )
