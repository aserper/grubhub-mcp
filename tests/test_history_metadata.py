"""Regression tests for endpoint-reported history, not lifetime completeness."""

import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.grubhub_mcp.tools import order as order_tools


class HistoryClient:
    def __init__(self, response):
        self.response = response
        self.session = SimpleNamespace(is_authenticated=True, diner_udid="diner-test")
        self.calls = []

    async def get(self, path, params=None):
        self.calls.append((path, params))
        return self.response


class ToolRegistry:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def register(func):
            self.tools[func.__name__] = func
            return func
        return register


class HistoryMetadataTests(unittest.IsolatedAsyncioTestCase):
    async def history(self, response, **kwargs):
        client = HistoryClient(response)
        registry = ToolRegistry()
        order_tools.register(registry)
        with patch.object(order_tools, "get_client", return_value=client):
            result = json.loads(await registry.tools["get_order_history"](**kwargs))
        self.assertEqual(len(client.calls), 1, "History must not fetch a profile implicitly")
        return result, client

    async def test_raw_history_retains_api_stats_without_interpreting_them(self):
        stats = {"total_results": 48, "date_range": {"oldest": "2025-10-08", "newest": "2026-10-07"}}
        client = HistoryClient({"results": [{"id": "order"}], "stats": stats})
        result = await order_tools._fetch_order_history_raw(client)
        self.assertEqual(result.get("stats"), stats)

    async def test_history_exposes_stats_and_available_total_not_lifetime(self):
        stats = {"total_results": 48, "oldest_order_date": "2025-10-08", "newest_order_date": "2026-10-07"}
        response = {"results": [{"id": "order"}], "stats": stats,
                    "pager": {"total_pages": 1, "current_page": 1}}
        result, _ = await self.history(response, page_size=100)
        self.assertEqual(result.get("stats"), stats)
        self.assertEqual(result["pagination"].get("total_results"), 48)
        self.assertNotIn("lifetime_total", result)

    async def test_requested_and_server_page_sizes_are_distinct(self):
        for server_size in (100, 20):
            with self.subTest(server_size=server_size):
                orders = [{"id": str(index)} for index in range(48 if server_size == 100 else 20)]
                result, client = await self.history({
                    "results": orders,
                    "stats": {"total_results": 48},
                    "pager": {"page_size": server_size, "total_pages": 1 if server_size == 100 else 3,
                              "current_page": 1},
                }, page_size=100)
                pagination = result["pagination"]
                self.assertEqual(pagination.get("requested_page_size"), 100)
                self.assertEqual(pagination.get("server_page_size"), server_size)
                self.assertEqual(pagination["page_size"], 100, "Keep the legacy requested-size field")
                self.assertEqual(pagination["returned"], len(orders))
                self.assertEqual(dict(client.calls[0][1])["pageSize"], 100)
                self.assertNotIn("server_cap", pagination)

    async def test_live_stats_page_size_is_reported_with_pager_precedence(self):
        stats = {"total_results": 48, "result_count": 1, "page_size": 1}
        for pager_size in (None, 20):
            with self.subTest(pager_size=pager_size):
                pager = {"total_pages": 48, "current_page": 1}
                if pager_size is not None:
                    pager["page_size"] = pager_size
                result, client = await self.history({
                    "results": [{"id": "order"}], "stats": stats, "pager": pager,
                }, page_size=100)
                self.assertEqual(result["pagination"], {
                    "page_size": 100, "requested_page_size": 100,
                    "server_page_size": 1 if pager_size is None else pager_size,
                    "page_num": 1, "returned": 1, "total_pages": 48,
                    "current_page": 1, "total_results": 48,
                })
                self.assertEqual(result["stats"], stats)
                self.assertEqual(dict(client.calls[0][1])["pageSize"], 100)

    async def test_pager_total_results_is_preserved_including_zero(self):
        for stats in (None, {"total_results": 48}):
            with self.subTest(stats=stats):
                result, _ = await self.history({
                    "results": [], "stats": stats,
                    "pager": {"total_results": 0, "total_pages": 0, "current_page": 1},
                })
                self.assertEqual(result["pagination"].get("total_results"), 0)
                self.assertEqual(result["stats"], stats)

    def test_history_docstring_limits_pagination_to_available_history(self):
        registry = ToolRegistry()
        order_tools.register(registry)
        doc = registry.tools["get_order_history"].__doc__
        self.assertIn("available history", doc)
        self.assertIn("not guarantee", doc)
        self.assertNotIn("full history is reachable", doc)

    async def test_missing_metadata_preserves_legacy_response_without_guessing(self):
        order = {"id": "order", "charges": {"lines": {"line_items": [{"id": "item"}]}}}
        result, _ = await self.history({"results": [order], "partner_results": [{"id": "partner"}]})
        self.assertEqual(result, {
            "orders": [order, {"id": "partner"}],
            "pagination": {"page_size": 20, "requested_page_size": 20, "page_num": 1, "returned": 2,
                           "total_pages": None, "current_page": None},
        })

    async def test_null_stats_are_preserved_without_inventing_counts(self):
        result, _ = await self.history({"stats": None, "pager": None, "results": None})
        self.assertIsNone(result["stats"])
        self.assertNotIn("total_results", result["pagination"])
        self.assertNotIn("server_page_size", result["pagination"])


if __name__ == "__main__":
    unittest.main()
