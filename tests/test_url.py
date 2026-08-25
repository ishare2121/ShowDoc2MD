import unittest
from showdoc2md.url import parse_showdoc_url


class URLTests(unittest.TestCase):
    def test_hosted_short_url(self):
        x = parse_showdoc_url("https://www.showdoc.com.cn/100200/987654")
        self.assertEqual(x.item_id, "100200")
        self.assertEqual(x.page_id, "987654")
        self.assertEqual(x.server_base, "https://www.showdoc.com.cn")

    def test_spa_url(self):
        x = parse_showdoc_url("https://example.com/web/#/90/4091")
        self.assertEqual(x.item_id, "90")
        self.assertEqual(x.page_id, "4091")

    def test_password_hash_url(self):
        x = parse_showdoc_url("https://example.com/web/#/item/password/88?page_id=4091")
        self.assertEqual(x.item_id, "88")
        self.assertEqual(x.page_id, "4091")


if __name__ == "__main__":
    unittest.main()
