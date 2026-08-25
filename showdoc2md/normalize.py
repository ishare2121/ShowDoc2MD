from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass
class PageRef:
    page_id: str
    title: str
    path: list[str] = field(default_factory=list)
    order: int = 0


def _page_id(page: dict[str, Any]) -> str:
    return str(page.get("page_id") or page.get("id") or "")


def _page_title(page: dict[str, Any]) -> str:
    return str(page.get("page_title") or page.get("title") or _page_id(page) or "未命名页面")


def collect_pages(item_info: dict[str, Any]) -> list[PageRef]:
    """Normalize both current (`data.menu`) and older menu response shapes."""
    menu = item_info.get("menu")
    if not isinstance(menu, dict):
        # Older/community variants sometimes put pages/catalogs at top level.
        menu = {
            "pages": item_info.get("pages", []),
            "catalogs": item_info.get("catalogs", []),
        }

    out: list[PageRef] = []
    seen: set[str] = set()
    counter = 0

    def add_pages(pages: Iterable[dict[str, Any]], path: list[str]) -> None:
        nonlocal counter
        for p in pages or []:
            if not isinstance(p, dict):
                continue
            pid = _page_id(p)
            if not pid or pid in seen:
                continue
            seen.add(pid)
            counter += 1
            out.append(PageRef(pid, _page_title(p), list(path), counter))

    def walk_catalogs(catalogs: Iterable[dict[str, Any]], path: list[str]) -> None:
        for cat in catalogs or []:
            if not isinstance(cat, dict):
                continue
            name = str(cat.get("cat_name") or cat.get("name") or "未命名目录")
            next_path = path + [name]
            add_pages(cat.get("pages", []), next_path)
            walk_catalogs(cat.get("catalogs", []) or cat.get("children", []), next_path)

    add_pages(menu.get("pages", []), [])
    walk_catalogs(menu.get("catalogs", []), [])
    return out
