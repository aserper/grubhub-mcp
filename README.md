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

Sessions are stored in `~/.grubhub-mcp/session.json` (override the directory with
`GRUBHUB_SESSION_DIR`). Access tokens are refreshed on use, including before
expiry when Grubhub supplies expiry metadata and once after an authenticated
request returns 401. Rotated tokens are saved for the next server invocation.
Refresh responses that omit account metadata do not erase your login identity.
Concurrent refreshes are serialized within the client, and on POSIX systems
across server processes sharing the session directory. Session writes are atomic
and use private file permissions. Grubhub's lifetime fields are in minutes;
the observed access/refresh lifetimes are one hour / 30 days, but server policy
may change.
There is no background keep-alive: a revoked or expired refresh token still
requires a new login. Do not share your session file; it contains credentials.

## Address Validation

`add_address` geocodes the supplied address through ``/geocode`` before saving
and refuses empty, ambiguous, or incomplete results instead of storing a bad
address. An optional ``phone`` is accepted when Grubhub requires one for the
address; no phone number is inferred.

## Session Diagnostics

`get_session_info` reports stored session state, which is not proof of a healthy
login. Pass ``verify=true`` to probe the authenticated profile through the normal
client (including token refresh). The result then reports
``verification_status`` as ``authenticated``, ``relogin_required``, or ``failed``,
with ``verified_is_authenticated`` and, when a re-login is needed,
``relogin_required``. The token value and profile data are never returned.

## Order History Pagination

`get_order_history` uses server-side pagination through `search_listing`.
`page_num` is **1-based** (default `1`), and `page_size` is the requested page
size (default `20`). Both must be positive. Iterate from `1` through
`pagination.total_pages` to retrieve the available history from
`search_listing`. This does not guarantee lifetime history: the endpoint's
available total may differ from the profile's lifetime count, without proving
deletion or a retention policy.

The response still includes full order objects, including partner orders, and the
existing pagination fields. Additional API metadata is exposed when supplied:

- `stats`: the API's statistics, passed through unchanged (including any reported
  date-range fields). No lifetime count or retention limit is inferred.
- `pagination.page_size`: the requested size, preserving its legacy meaning.
  `requested_page_size` always repeats the requested size. `server_page_size`
  exposes `pager.page_size` when present, otherwise `stats.page_size` when
  reported. It is never inferred from the number of orders returned.
- `pagination.returned`: the number of order objects on this page, not a page-size
  limit or total history count.
- `pagination.total_results`: the API's reported available count, taken from the
  pager when supplied, otherwise from `stats.total_results`. Missing counts are
  not guessed, and zero counts remain zero. The unchanged `stats` allow inspection
  if the two reported counts differ.

A request for `page_size=100` returning 48 orders with `total_results=48` can
simply be a short final page; it does **not** establish server clamping or a cap.
For an optional lifetime-completeness comparison, fetch `get_profile` separately
and compare its lifetime order count with the endpoint's available total. History
pages do not make a mandatory profile request.

A live account check observed roughly a year of available history, with fewer
orders than its lifetime profile count. That is an observation, not a permanent
12-month retention guarantee. A difference between available and lifetime history
does not prove that older orders were deleted. Dates inferred from a single page
describe that page only; without API range metadata, inspect all available pages
before describing the available history's date range.

**Migration from v1.1.6:** callers using the old 0-based `page_num` must add one
to their page index. The response provides `total_pages` and `current_page`
instead of the legacy `total_orders` value, which only counted a recent subset.

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

## Development

Run the regression suite with:

```
uv run python -m unittest discover -s tests -v
```

CI runs tests on pushes and pull requests, and the release job runs them before
publishing. The package currently requires MCP 1.x (`mcp<2`).

## Disclaimer

This project is for educational and personal use. It is not affiliated with or endorsed by Grubhub. Use responsibly and in accordance with Grubhub's terms of service.

## License

MIT
