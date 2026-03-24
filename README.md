# Grubhub MCP Server

An MCP (Model Context Protocol) server that provides programmatic access to Grubhub's food delivery platform. Search restaurants, browse menus, manage your cart, place orders, and track deliveries — all through MCP tools.

## Features

- **Search & Discovery** — Find restaurants by location, cuisine, or keyword with autocomplete
- **Restaurant & Menus** — View restaurant details, full menus, item options and pricing
- **Cart Management** — Create carts, add/remove items, apply promo codes, set tips
- **Order Flow** — Place orders, track deliveries in real-time, reorder past meals
- **Account Management** — Manage profile, saved addresses, favorites, and passwords
- **Payments** — View saved payment methods, check gift card balances

### All 36 Tools

| Category | Tools |
|----------|-------|
| **Auth** | `login`, `logout`, `get_session_info`, `send_login_otp`, `verify_login_otp`, `create_account`, `send_password_reset` |
| **Search** | `search_restaurants`, `autocomplete_search` |
| **Restaurant** | `get_restaurant`, `get_menu`, `get_menu_item` |
| **Cart** | `create_cart`, `get_cart`, `add_to_cart`, `update_cart_item`, `remove_from_cart`, `apply_promo_code`, `set_tip` |
| **Order** | `place_order`, `get_order`, `get_order_history`, `track_order`, `reorder`, `post_delivery_tip` |
| **Account** | `get_profile`, `update_profile`, `get_addresses`, `add_address`, `get_favorites`, `add_favorite`, `remove_favorite`, `change_password` |
| **Payments** | `get_payment_methods`, `get_gift_card_balance`, `apply_gift_card` |

## Installation

### Claude Code Plugin (Recommended)

```bash
claude plugin marketplace add aserper/grubhub-mcp
claude plugin install grubhub-mcp@grubhub-marketplace
```

### uvx (No Installation Required)

Add to your Claude Code MCP settings (`~/.claude/settings.json`):

```json
{
  "mcpServers": {
    "grubhub": {
      "command": "uvx",
      "args": ["--from", "grubhub-mcp", "grubhub"]
    }
  }
}
```

### Manual / From Source

Requires Python 3.11+.

```bash
git clone https://github.com/aserper/grubhub-mcp.git
cd grubhub-mcp
uv venv && source .venv/bin/activate
uv pip install -e .
```

Then add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "grubhub": {
      "command": "/path/to/grubhub-mcp/.venv/bin/grubhub"
    }
  }
}
```

## Usage with Other MCP Clients

Run the server over stdio:

```bash
# With uvx (no install needed)
uvx --from grubhub-mcp grubhub

# Or from a local install
grubhub

# Or as a Python module
python -m grubhub_mcp
```

## Authentication

**No login required** for browsing — search restaurants, view menus, and check prices without an account. The server automatically creates an anonymous session.

**Login required** for ordering, account management, and order history:

```
Use the login tool with my email and password
```

Supports email/password login and OTP (one-time passcode) authentication.

## How It Works

The API endpoints were reverse-engineered from the Grubhub Android app (v2026.11.1) by decompiling the APK with jadx and analyzing the Retrofit service interfaces, OkHttp interceptors, and data models.

Key technical details:
- **Base API**: `https://api-gtm.grubhub.com`
- **Auth**: Bearer token via email/password or anonymous sessions
- **Transport**: REST/JSON for most endpoints, Protobuf for some BFF services
- **Headers**: Mimics the Android app's request headers including `x-gh-browser-id`

## Project Structure

```
src/grubhub_mcp/
├── __init__.py
├── __main__.py        # python -m entry point
├── server.py          # MCP server setup and tool registration
├── client.py          # HTTP client with auth and header management
├── auth.py            # Authentication flows (login, anonymous, OTP, refresh)
└── tools/
    ├── auth.py        # Auth tools (login, logout, OTP, account creation)
    ├── search.py      # Restaurant search and autocomplete
    ├── restaurant.py  # Restaurant details, menus, menu items
    ├── cart.py        # Cart CRUD, promo codes, tips
    ├── order.py       # Place orders, track, reorder, order history
    ├── account.py     # Profile, addresses, favorites, password
    └── payments.py    # Payment methods, gift cards
```

## Disclaimer

This project is for educational and personal use. It is not affiliated with or endorsed by Grubhub. Use responsibly and in accordance with Grubhub's terms of service.

## License

MIT
