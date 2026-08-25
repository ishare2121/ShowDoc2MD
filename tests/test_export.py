import json
import tempfile
import unittest
from pathlib import Path

from showdoc2md.client import ShowDocError
from showdoc2md.exporter import ShowDocExporter
from showdoc2md.normalize import collect_pages
from showdoc2md.renderer import render_page_content
from showdoc2md.url import parse_showdoc_url


ITEM = {
    "item_id": "123",
    "item_name": "测试项目",
    "menu": {
        "pages": [{"page_id": "1", "page_title": "首页"}],
        "catalogs": [
            {
                "cat_name": "订单",
                "pages": [{"page_id": "2", "page_title": "创建订单"}],
                "catalogs": [
                    {"cat_name": "查询", "pages": [{"page_id": "3", "page_title": "订单详情"}], "catalogs": []}
                ],
            }
        ],
    },
}

PAGES = {
    "1": {"page_id": "1", "page_title": "首页", "page_content": "欢迎使用。\n"},
    "2": {
        "page_id": "2",
        "page_title": "创建订单",
        "page_content": json.dumps({
            "info": {"type": "api", "title": "创建订单", "method": "post", "url": "https://api.test/order"},
            "request": {"query": [{"name": "merchant_id", "type": "string", "required": "1", "remark": "商户号"}]},
            "response": {"code": 0}
        }, ensure_ascii=False),
    },
    "3": {"page_id": "3", "page_title": "订单详情", "page_content": "## 示例\n\n内容。"},
}


class FakeClient:
    def __init__(self):
        self.item_id = "123"
        self.url_info = parse_showdoc_url("https://www.showdoc.com.cn/123/1")
        self.server_base = self.url_info.server_base
    def fetch_item_info(self):
        return ITEM
    def fetch_page_info(self, page_id):
        return PAGES[str(page_id)]


class ExportTests(unittest.TestCase):
    def test_collect_pages(self):
        refs = collect_pages(ITEM)
        self.assertEqual([x.page_id for x in refs], ["1", "2", "3"])
        self.assertEqual(refs[2].path, ["订单", "查询"])

    def test_runapi_render(self):
        md = render_page_content(PAGES["2"])
        self.assertIn("POST https://api.test/order", md)
        self.assertIn("merchant_id", md)

    def test_export_tree_and_combined(self):
        with tempfile.TemporaryDirectory() as td:
            result = ShowDocExporter(FakeClient()).export(td, download_assets=False)
            self.assertEqual(result.pages, 3)
            self.assertTrue(result.complete)
            self.assertTrue(result.combined_md.exists())
            text = result.combined_md.read_text(encoding="utf-8")
            self.assertIn("订单 / 创建订单", text)
            self.assertIn("订单 / 查询 / 订单详情", text)
            self.assertTrue((result.root_dir / "pages" / "订单" / "查询").exists())


class CompletenessTests(unittest.TestCase):
    def test_empty_menu_raises(self):
        class EmptyClient(FakeClient):
            def fetch_item_info(self):
                return {"item_name": "empty", "menu": {"pages": [], "catalogs": []}}

        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ShowDocError):
                ShowDocExporter(EmptyClient()).export(td, download_assets=False)

    def test_failed_page_marks_incomplete(self):
        class PartialClient(FakeClient):
            def fetch_page_info(self, page_id):
                if str(page_id) == "2":
                    raise RuntimeError("simulated page read failure")
                return super().fetch_page_info(page_id)

        with tempfile.TemporaryDirectory() as td:
            result = ShowDocExporter(PartialClient()).export(td, download_assets=False)
            self.assertEqual(result.pages, 2)
            self.assertFalse(result.complete)
            self.assertEqual(len(result.failed_pages), 1)
            manifest = json.loads(result.manifest_json.read_text(encoding="utf-8"))
            self.assertFalse(manifest["complete"])
            self.assertEqual(manifest["page_count_discovered"], 3)
            self.assertEqual(manifest["page_count_exported"], 2)


if __name__ == "__main__":
    unittest.main()
