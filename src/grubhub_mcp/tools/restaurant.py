"""Restaurant and menu MCP tools."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..client import get_client
from .. import auth as auth_module


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def get_restaurant(
        restaurant_id: str,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> str:
        """Get restaurant details including hours, ratings, and delivery info.

        Args:
            restaurant_id: The Grubhub restaurant ID
            latitude: Optional latitude for delivery estimates
            longitude: Optional longitude for delivery estimates
        """
        client = get_client()
        if not client.session.auth_token:
            await auth_module.create_anonymous_session(client)

        params: dict[str, Any] = {
            "hideChoiceCategories": "true",
            "orderType": "standard",
            "platform": "web",
            "enhancedFees": "true",
        }
        if latitude and longitude:
            params["location"] = f"POINT({longitude} {latitude})"

        data = await client.get(
            f"/restaurants/{restaurant_id}", params=params
        )
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def get_menu(
        restaurant_id: str,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> str:
        """Get the full menu for a restaurant including categories, items, and prices.

        Args:
            restaurant_id: The Grubhub restaurant ID
            latitude: Optional latitude for availability
            longitude: Optional longitude for availability
        """
        client = get_client()
        if not client.session.auth_token:
            await auth_module.create_anonymous_session(client)

        params: dict[str, Any] = {
            "hideUnavailableMenuItems": "true",
            "orderType": "standard",
            "platform": "web",
        }
        if latitude and longitude:
            params["location"] = f"POINT({longitude} {latitude})"

        data = await client.get(
            f"/restaurants/{restaurant_id}/menu", params=params
        )
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def get_menu_item(restaurant_id: str, item_id: str) -> str:
        """Get details for a specific menu item including options, add-ons, and pricing.

        Args:
            restaurant_id: The Grubhub restaurant ID
            item_id: The menu item ID
        """
        client = get_client()
        if not client.session.auth_token:
            await auth_module.create_anonymous_session(client)

        data = await client.get(
            f"/restaurants/{restaurant_id}/menu_items/{item_id}",
            params={"platform": "web"},
        )
        return json.dumps(data, indent=2)
