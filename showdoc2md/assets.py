from __future__ import annotations

import hashlib
import mimetypes
import os
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from .client import ShowDocClient, ShowDocNetworkError

_MD_IMG_RE = re.compile(r"(!\[[^\]]*\]\()([^\s)]+)([^)]*\))")
_HTML_IMG_RE = re.compile(r"(<img\b[^>]*?\bsrc=[\"'])([^\"']+)([\"'][^>]*>)", re.I)


class AssetDownloader:
    def __init__(self, client: ShowDocClient, project_root: Path) -> None:
        self.client = client
        self.project_root = project_root
        self.assets_dir = project_root / "assets"
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        self.cache: dict[str, Path] = {}
        self.failures: list[str] = []

    def _absolute(self, url: str) -> str | None:
        u = url.strip().strip("<>")
        if not u or u.startswith("data:") or u.startswith("#"):
            return None
        if u.startswith("//"):
            return "https:" + u
        return urljoin(self.client.server_base + "/", u)

    def _guess_suffix(self, url: str, content_type: str | None) -> str:
        suffix = Path(urlparse(url).path).suffix
        if suffix and len(suffix) <= 8:
            return suffix
        if content_type:
            mime = content_type.split(";", 1)[0].strip()
            guess = mimetypes.guess_extension(mime)
            if guess:
                return guess
        return ".bin"

    def fetch(self, url: str) -> Path | None:
        absolute = self._absolute(url)
        if not absolute:
            return None
        if absolute in self.cache:
            return self.cache[absolute]
        try:
            data, content_type = self.client.download(absolute)
        except ShowDocNetworkError:
            self.failures.append(absolute)
            return None
        digest = hashlib.sha1(absolute.encode("utf-8")).hexdigest()[:16]
        suffix = self._guess_suffix(absolute, content_type)
        path = self.assets_dir / f"{digest}{suffix}"
        path.write_bytes(data)
        self.cache[absolute] = path
        return path

    def rewrite(self, markdown: str, from_dir: Path) -> str:
        def rel(asset: Path) -> str:
            return Path(os.path.relpath(asset, from_dir)).as_posix()

        def md_sub(m: re.Match[str]) -> str:
            asset = self.fetch(m.group(2))
            if not asset:
                return m.group(0)
            return f"{m.group(1)}{rel(asset)}{m.group(3)}"

        def html_sub(m: re.Match[str]) -> str:
            asset = self.fetch(m.group(2))
            if not asset:
                return m.group(0)
            return f"{m.group(1)}{rel(asset)}{m.group(3)}"

        markdown = _MD_IMG_RE.sub(md_sub, markdown)
        markdown = _HTML_IMG_RE.sub(html_sub, markdown)
        return markdown
