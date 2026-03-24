"""Grubhub MCP Server — search restaurants, browse menus, manage cart, place orders."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .tools import auth, search, restaurant, cart, order, account, payments

mcp = FastMCP(
    "grubhub",
    instructions=(
        "Grubhub MCP server. Use these tools to search for restaurants, "
        "browse menus, manage a shopping cart, place food delivery/pickup "
        "orders, and manage your Grubhub account. "
        "Start by searching for restaurants near a location. "
        "Login is required for placing orders, viewing order history, "
        "and account management. Search and menu browsing work without login."
    ),
)

# Register all tool modules
auth.register(mcp)
search.register(mcp)
restaurant.register(mcp)
cart.register(mcp)
order.register(mcp)
account.register(mcp)
payments.register(mcp)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
