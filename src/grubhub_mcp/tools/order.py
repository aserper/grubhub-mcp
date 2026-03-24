"""Order management MCP tools."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..client import get_client


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def place_order(
        cart_id: str,
        payment_method_id: str | None = None,
        tip_amount: float | None = None,
    ) -> str:
        """Place an order from a cart. Requires authentication.

        Args:
            cart_id: The cart ID to submit as an order
            payment_method_id: ID of the payment method to use (uses default if not specified)
            tip_amount: Optional tip amount in dollars
        """
        client = get_client()
        if not client.session.is_authenticated:
            return json.dumps({"error": "Must be logged in to place an order"})

        payload: dict[str, Any] = {}
        if payment_method_id:
            payload["payment_method_id"] = payment_method_id
        if tip_amount is not None:
            payload["tip_amount"] = int(tip_amount * 100)

        data = await client.post(f"/carts/{cart_id}/submit", data=payload)
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def get_order(order_id: str) -> str:
        """Get details for a specific order.

        Args:
            order_id: The order ID
        """
        client = get_client()
        data = await client.get(f"/orders/{order_id}")
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def get_order_history(page_size: int = 10, page_num: int = 0) -> str:
        """Get past order history. Requires authentication.

        Args:
            page_size: Number of orders per page (default 10)
            page_num: Page number (default 0)
        """
        client = get_client()
        if not client.session.is_authenticated:
            return json.dumps({"error": "Must be logged in to view order history"})

        params = {
            "pageSize": page_size,
            "pageNum": page_num,
        }
        data = await client.get(
            f"/diners/{client.session.diner_udid}/orders",
            params=params,
        )
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def track_order(order_id: str) -> str:
        """Get real-time tracking info for an active order.

        Args:
            order_id: The order ID to track
        """
        client = get_client()
        data = await client.get(f"/orders/{order_id}/tracking")
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def reorder(order_id: str) -> str:
        """Create a new cart from a previous order for easy reordering.

        Args:
            order_id: The order ID to reorder
        """
        client = get_client()
        if not client.session.is_authenticated:
            return json.dumps({"error": "Must be logged in to reorder"})

        data = await client.post(f"/orders/{order_id}/reorder")
        return json.dumps(data, indent=2)

    @mcp.tool()
    async def post_delivery_tip(order_id: str, tip_amount: float) -> str:
        """Add or update the tip after delivery.

        Args:
            order_id: The order ID
            tip_amount: Tip amount in dollars
        """
        client = get_client()
        data = await client.post(
            f"/orders/{order_id}/tip",
            data={"tip_amount": int(tip_amount * 100)},
        )
        return json.dumps(data, indent=2)
