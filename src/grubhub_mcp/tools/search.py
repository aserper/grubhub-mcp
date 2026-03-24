"""Restaurant search and discovery MCP tools."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..client import get_client
from .. import auth as auth_module


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def search_restaurants(
        latitude: float,
        longitude: float,
        query: str = "",
        page_size: int = 20,
        page_num: int = 0,
        sort_type: str = "RELEVANCE",
        delivery_or_pickup: str = "DELIVERY",
    ) -> str:
        """Search for restaurants near a location.

        Args:
            latitude: Latitude of the delivery address
            longitude: Longitude of the delivery address
            query: Optional search query (cuisine, restaurant name, dish)
            page_size: Number of results per page (default 20)
            page_num: Page number for pagination (default 0)
            sort_type: Sort order - RELEVANCE, DISTANCE, RATING, PRICE_LOW_TO_HIGH, ESTIMATED_DELIVERY_TIME
            delivery_or_pickup: DELIVERY or PICKUP
        """
        client = get_client()
        if not client.session.auth_token:
            await auth_module.create_anonymous_session(client)

        params: dict[str, Any] = {
            "orderMethod": delivery_or_pickup,
            "locationMode": "DELIVERY",
            "facetSet": "umamiV6",
            "pageSize": page_size,
            "pageNum": page_num,
            "hideHat498": "true",
            "searchMetrics": "true",
            "location": f"POINT({longitude} {latitude})",
            "preciseLocation": "true",
            "sortSetId": "umami",
            "countOmittingTimes": "true",
        }
        if query:
            params["queryText"] = query
        if sort_type:
            params["sorts"] = json.dumps({"sortType": sort_type})

        data = await client.get("/search_listing", params=params)
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def autocomplete_search(
        query: str,
        latitude: float,
        longitude: float,
    ) -> str:
        """Get autocomplete suggestions for a search query.

        Args:
            query: The partial search text
            latitude: Latitude for location context
            longitude: Longitude for location context
        """
        client = get_client()
        if not client.session.auth_token:
            await auth_module.create_anonymous_session(client)

        params = {
            "queryText": query,
            "location": f"POINT({longitude} {latitude})",
        }
        data = await client.get("/search_listing/autocomplete", params=params)
        return json.dumps(data, indent=2)
