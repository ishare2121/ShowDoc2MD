from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse
import re


@dataclass(frozen=True)
class ShowDocURL:
    original: str
    server_base: str
    item_id: str
    page_id: str | None = None


def parse_showdoc_url(url: str) -> ShowDocURL:
    raw = (url or "").strip()
    if not raw:
        raise ValueError("ShowDoc URL 不能为空")

    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"不是有效的 URL: {raw}")

    server_base = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
    item_id: str | None = None
    page_id: str | None = None

    # 1) 新版托管短链接: https://www.showdoc.com.cn/{item_id}/{page_id}
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 1 and parts[0].isdigit():
        item_id = parts[0]
        if len(parts) >= 2 and parts[1].isdigit():
            page_id = parts[1]

    # 2) SPA hash: /web/#/{item_id}/{page_id}
    frag = parsed.fragment or ""
    if frag:
        clean_frag = frag.lstrip("/")
        m = re.search(r"(?:^|/)(\d+)(?:/(\d+))?(?:$|[/?])", clean_frag)
        if m and not item_id:
            item_id = m.group(1)
            page_id = page_id or m.group(2)

        # 3) /web/#/item/password/{item_id}?page_id={page_id}
        m = re.search(r"item/password/(\d+)", clean_frag)
        if m:
            item_id = m.group(1)
            query_text = clean_frag.split("?", 1)[1] if "?" in clean_frag else ""
            q = parse_qs(query_text)
            if q.get("page_id"):
                page_id = q["page_id"][0]

    # 4) query fallback
    q = parse_qs(parsed.query)
    if not item_id and q.get("item_id"):
        item_id = q["item_id"][0]
    if not page_id and q.get("page_id"):
        page_id = q["page_id"][0]

    if not item_id:
        raise ValueError(f"无法从 URL 解析 ShowDoc item_id: {raw}")

    return ShowDocURL(raw, server_base, item_id, page_id)
