import os
import tempfile
import unittest
from unittest.mock import patch

from mcp import Client

from showdoc2md.mcp_server import mcp
from showdoc2md.url import parse_showdoc_url


FAKE_ITEM = {
    "item_id": "123",
    "item_name": "Demo API",
    "item_type": "1",
    "menu": {
        "pages": [{"page_id": "1", "page_title": "Overview"}],
        "catalogs": [
            {
                "cat_name": "Orders",
                "pages": [{"page_id": "2", "page_title": "Create order"}],
                "catalogs": [],
            }
        ],
    },
}

FAKE_PAGES = {
    "1": {"page_id": "1", "page_title": "Overview", "page_content": "# Welcome\n\nDemo documentation."},
    "2": {"page_id": "2", "page_title": "Create order", "page_content": "POST /orders\n"},
}


class FakeShowDocClient:
    def __init__(self, url, password, *, verify_ssl=True, **_kwargs):
        self.url_info = parse_showdoc_url(url)
        self.server_base = self.url_info.server_base
        self.item_id = self.url_info.item_id
        self.initial_page_id = self.url_info.page_id
        self.password = password
        self.verify_ssl = verify_ssl

    def fetch_item_info(self):
        return FAKE_ITEM

    def fetch_page_info(self, page_id):
        return FAKE_PAGES[str(page_id)]

    def download(self, _url):
        raise AssertionError("assets should be disabled in this test")


class MCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_tools_are_discoverable(self):
        async with Client(mcp) as client:
            listed = await client.list_tools()
        names = {tool.name for tool in listed.tools}
        self.assertEqual(
            names,
            {
                "showdoc_probe",
                "showdoc_list_pages",
                "showdoc_read_page",
                "showdoc_read_full",
                "showdoc_export",
            },
        )

    async def test_read_full_uses_server_side_password_without_echoing_it(self):
        with patch("showdoc2md.mcp_server.ShowDocClient", FakeShowDocClient), patch.dict(
            os.environ, {"SHOWDOC_PASSWORD": "demo-password"}, clear=False
        ):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "showdoc_read_full",
                    {"url": "https://docs.example.test/123/1"},
                )

        self.assertFalse(result.is_error)
        data = result.structured_content
        self.assertTrue(data["complete"])
        self.assertEqual(data["page_count_discovered"], 2)
        self.assertEqual(data["page_count_read"], 2)
        self.assertIn("Create order", data["markdown"])
        self.assertNotIn("demo-password", str(data))

    async def test_read_page_defaults_to_page_id_in_url(self):
        with patch("showdoc2md.mcp_server.ShowDocClient", FakeShowDocClient):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "showdoc_read_page",
                    {
                        "url": "https://docs.example.test/123/2",
                        "password": "demo-password",
                    },
                )

        self.assertFalse(result.is_error)
        self.assertEqual(result.structured_content["page_id"], "2")
        self.assertEqual(result.structured_content["title"], "Create order")

    async def test_export_tool_returns_complete_result(self):
        with tempfile.TemporaryDirectory() as td, patch(
            "showdoc2md.mcp_server.ShowDocClient", FakeShowDocClient
        ):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "showdoc_export",
                    {
                        "url": "https://docs.example.test/123/1",
                        "password": "demo-password",
                        "output_dir": td,
                        "download_assets": False,
                    },
                )

        self.assertFalse(result.is_error)
        self.assertTrue(result.structured_content["complete"])
        self.assertEqual(result.structured_content["pages"], 2)


if __name__ == "__main__":
    unittest.main()
