from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .assets import AssetDownloader
from .client import ShowDocClient, ShowDocError
from .normalize import PageRef, collect_pages
from .renderer import render_page_content


_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_name(name: str, fallback: str = "untitled", max_len: int = 100) -> str:
    name = _INVALID.sub("_", (name or "").strip())
    name = re.sub(r"\s+", " ", name).strip(" .")
    return (name or fallback)[:max_len]


@dataclass
class ExportResult:
    item_id: str
    item_name: str
    pages: int
    root_dir: Path
    combined_md: Path
    manifest_json: Path
    failed_pages: list[dict[str, str]]
    failed_assets: list[str]

    @property
    def complete(self) -> bool:
        """True only when every discovered page and requested asset was exported."""
        return not self.failed_pages and not self.failed_assets

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "item_name": self.item_name,
            "pages": self.pages,
            "complete": self.complete,
            "root_dir": str(self.root_dir),
            "combined_md": str(self.combined_md),
            "manifest_json": str(self.manifest_json),
            "failed_pages": self.failed_pages,
            "failed_assets": self.failed_assets,
        }


class ShowDocExporter:
    def __init__(self, client: ShowDocClient) -> None:
        self.client = client

    def _page_path(self, root: Path, ref: PageRef) -> Path:
        parent = root / "pages"
        for seg in ref.path:
            parent /= safe_name(seg)
        parent.mkdir(parents=True, exist_ok=True)
        return parent / f"{ref.order:04d}_{safe_name(ref.title, ref.page_id)}.md"

    def export(self, output_dir: str | Path = "output", *, download_assets: bool = True) -> ExportResult:
        item = self.client.fetch_item_info()
        item_name = str(item.get("item_name") or f"showdoc_{self.client.item_id}")
        root = Path(output_dir).expanduser().resolve() / f"{safe_name(item_name)}_{self.client.item_id}"
        root.mkdir(parents=True, exist_ok=True)
        refs = collect_pages(item)
        if not refs:
            raise ShowDocError("ShowDoc 项目目录未返回任何页面，无法保证完整导出；已停止而不是生成空文档。")
        assets = AssetDownloader(self.client, root) if download_assets else None

        combined_parts = [
            f"# {item_name}",
            "",
            f"> Source: {self.client.url_info.original}",
            f"> ShowDoc item_id: `{self.client.item_id}`",
            f"> Exported: {datetime.now(timezone.utc).isoformat()}",
            "",
            "## 目录",
            "",
        ]
        for ref in refs:
            label = " / ".join(ref.path + [ref.title])
            combined_parts.append(f"- {label}")
        combined_parts.append("")

        manifest_pages: list[dict[str, Any]] = []
        failed_pages: list[dict[str, str]] = []

        for ref in refs:
            try:
                page = self.client.fetch_page_info(ref.page_id)
                title = str(page.get("page_title") or ref.title)
                raw_md = render_page_content(page)
                page_file = self._page_path(root, PageRef(ref.page_id, title, ref.path, ref.order))
                page_md = assets.rewrite(raw_md, page_file.parent) if assets else raw_md

                heading = " / ".join(ref.path + [title])
                page_file.write_text(
                    f"# {title}\n\n> ShowDoc page_id: `{ref.page_id}`\n\n{page_md}",
                    encoding="utf-8",
                )

                combined_md = assets.rewrite(raw_md, root) if assets else raw_md
                combined_parts += ["---", "", f"## {heading}", "", combined_md.rstrip(), ""]
                manifest_pages.append(
                    {
                        "page_id": ref.page_id,
                        "title": title,
                        "path": ref.path,
                        "file": str(page_file.relative_to(root)),
                    }
                )
            except Exception as exc:
                failed_pages.append({"page_id": ref.page_id, "title": ref.title, "error": str(exc)})

        combined = root / "完整文档.md"
        combined.write_text("\n".join(combined_parts).rstrip() + "\n", encoding="utf-8")

        manifest = root / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "item_id": self.client.item_id,
                    "item_name": item_name,
                    "source_url": self.client.url_info.original,
                    "page_count_discovered": len(refs),
                    "page_count_exported": len(manifest_pages),
                    "complete": len(manifest_pages) == len(refs) and not failed_pages and not (assets.failures if assets else []),
                    "pages": manifest_pages,
                    "failed_pages": failed_pages,
                    "failed_assets": assets.failures if assets else [],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return ExportResult(
            item_id=self.client.item_id,
            item_name=item_name,
            pages=len(manifest_pages),
            root_dir=root,
            combined_md=combined,
            manifest_json=manifest,
            failed_pages=failed_pages,
            failed_assets=assets.failures if assets else [],
        )
