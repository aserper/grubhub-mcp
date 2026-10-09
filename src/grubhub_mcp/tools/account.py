"""Account management MCP tools."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..client import get_client
from .. import auth as auth_module


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def get_profile() -> str:
        """Get the current user's profile information. Requires authentication."""
        client = get_client()
        if not client.session.is_authenticated or not client.session.diner_udid:
            return json.dumps({"error": "Must be logged in to view profile"})

        data = await client.get(
            f"/diners/{client.session.diner_udid}/details",
            params={
                "with_addresses": True,
                "with_favorites": True,
                "with_diner_identity": True,
                "with_phone_numbers": True,
            },
        )
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def update_profile(
        first_name: str | None = None,
        last_name: str | None = None,
        phone: str | None = None,
    ) -> str:
        """Update user profile information. Requires authentication.

        Args:
            first_name: New first name
            last_name: New last name
            phone: New phone number
        """
        client = get_client()
        if not client.session.is_authenticated or not client.session.diner_udid:
            return json.dumps({"error": "Must be logged in to update profile"})

        payload: dict[str, Any] = {}
        if first_name is not None:
            payload["first_name"] = first_name
        if last_name is not None:
            payload["last_name"] = last_name
        if phone is not None:
            payload["phone"] = phone

        data = await client.put(
            f"/credentials/{client.session.diner_udid}/profile",
            data=payload,
        )
        return json.dumps(data if data else {"status": "updated"}, indent=2)

    @mcp.tool()
    async def get_addresses() -> str:
        """Get saved delivery addresses. Requires authentication."""
        client = get_client()
        if not client.session.is_authenticated or not client.session.diner_udid:
            return json.dumps({"error": "Must be logged in to view addresses"})

        data = await client.get(
            f"/diners/{client.session.diner_udid}/addresses"
        )
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def add_address(
        street_address: str,
        city: str,
        state: str,
        zip_code: str,
        apt_suite: str = "",
        delivery_instructions: str = "",
        label: str = "",
        phone: str | None = None,
    ) -> str:
        """Geocode and add a new delivery address. Requires authentication.

        Refuses empty, ambiguous, or incomplete geocoder results without saving the
        address.
        Supply phone when required by Grubhub; no phone number is inferred.

        Args:
            street_address: Street address line
            city: City name
            state: State abbreviation (e.g. NY, CA)
            zip_code: ZIP code
            apt_suite: Apartment/suite number
            delivery_instructions: Special delivery instructions
            label: Label for the address (e.g. Home, Work)
            phone: Delivery contact phone number, omitted if not supplied
        """
        client = get_client()
        if not client.session.is_authenticated or not client.session.diner_udid:
            return json.dumps({"error": "Must be logged in to add addresses"})

        full_address = ", ".join(
            part for part in (street_address, apt_suite, city, f"{state} {zip_code}")
            if part
        )
        results = await client.get("/geocode", params={"address": full_address})
        if not isinstance(results, list):
            return json.dumps({"error": "Geocoder returned an invalid response"})
        if not results:
            return json.dumps({"error": "Geocoder returned no results; address was not added"})
        if len(results) != 1:
            return json.dumps({"error": "Geocoder results are ambiguous; refine the address"})
        canonical = results[0]
        if not isinstance(canonical, dict):
            return json.dumps({"error": "Geocoder returned an invalid address"})
        text_fields = (
            "street_address1", "address_country", "address_locality",
            "address_region", "postal_code",
        )
        location_address = canonical.get("location_address")
        lines = location_address.get("address_lines") if isinstance(location_address, dict) else None
        time_zone = canonical.get("time_zone")
        if (
            any(not isinstance(canonical.get(field), str) or not canonical[field].strip()
                for field in text_fields)
            or not isinstance(lines, list) or not lines
            or any(not isinstance(line, str) or not line.strip() for line in lines)
            or not isinstance(time_zone, dict)
            or not isinstance(time_zone.get("id"), str) or not time_zone["id"].strip()
        ):
            return json.dumps({"error": "Geocoder returned incomplete address metadata"})
        try:
            latitude = float(canonical["latitude"])
            longitude = float(canonical["longitude"])
            if (
                isinstance(canonical["latitude"], bool)
                or isinstance(canonical["longitude"], bool)
                or not -90 <= latitude <= 90
                or not -180 <= longitude <= 180
            ):
                raise ValueError("Invalid coordinate range")
        except (KeyError, TypeError, ValueError, OverflowError):
            return json.dumps({"error": "Geocoder returned missing or invalid coordinates"})
        payload: dict[str, Any] = {
            key: canonical[key] for key in (
                "street_address1", "address_country", "address_locality",
                "address_region", "postal_code", "latitude", "longitude",
            )
        }
        address_lines = list(lines)
        if apt_suite:
            payload["street_address2"] = apt_suite
            if apt_suite not in address_lines:
                address_lines.append(apt_suite)
        payload.update({
            "region_code": canonical["address_country"],
            "address_lines": address_lines,
            "address": {
                "region_code": canonical["address_country"],
                "address_lines": list(address_lines),
                "locality": canonical["address_locality"],
                "administrative_area": canonical["address_region"],
                "postal_code": canonical["postal_code"],
                "coordinates": {
                    "latitude": latitude,
                    "longitude": longitude,
                },
            },
            "label": label,
            "special_instructions": delivery_instructions,
            "fulfillment_type": "DELIVERY",
            "time_zone": canonical["time_zone"],
        })

        if phone is not None:
            payload["phone"] = phone
        data = await client.post(
            f"/diners/{client.session.diner_udid}/addresses",
            data=payload,
        )
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def get_favorites() -> str:
        """Get favorite/saved restaurants. Requires authentication."""
        client = get_client()
        if not client.session.is_authenticated or not client.session.diner_udid:
            return json.dumps({"error": "Must be logged in to view favorites"})

        data = await client.get(
            f"/diners/{client.session.diner_udid}/favorites/restaurants"
        )
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def add_favorite(restaurant_id: str) -> str:
        """Add a restaurant to favorites. Requires authentication.

        Args:
            restaurant_id: The restaurant ID to favorite
        """
        client = get_client()
        if not client.session.is_authenticated or not client.session.diner_udid:
            return json.dumps({"error": "Must be logged in"})

        data = await client.post(
            f"/diners/{client.session.diner_udid}/favorites/restaurants",
            data={"restaurant_id": int(restaurant_id)},
        )
        return json.dumps(data if data else {"status": "added"}, indent=2)

    @mcp.tool()
    async def remove_favorite(restaurant_id: str) -> str:
        """Remove a restaurant from favorites. Requires authentication.

        Args:
            restaurant_id: The restaurant ID to unfavorite
        """
        client = get_client()
        if not client.session.is_authenticated or not client.session.diner_udid:
            return json.dumps({"error": "Must be logged in"})

        data = await client.delete(
            f"/diners/{client.session.diner_udid}/favorites/{restaurant_id}"
        )
        return json.dumps(data if data else {"status": "removed"}, indent=2)

    @mcp.tool()
    async def change_password(
        current_password: str, new_password: str
    ) -> str:
        """Change account password. Requires authentication.

        Args:
            current_password: Current password
            new_password: New password
        """
        client = get_client()
        if not client.session.is_authenticated or not client.session.diner_udid:
            return json.dumps({"error": "Must be logged in"})

        data = await client.put(
            f"/credentials/{client.session.diner_udid}/change_password",
            data={
                "current_password": current_password,
                "new_password": new_password,
            },
        )
        return json.dumps(data if data else {"status": "password_changed"}, indent=2)
