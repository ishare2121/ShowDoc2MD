from __future__ import annotations

import html
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .url import ShowDocURL, parse_showdoc_url


class ShowDocError(RuntimeError):
    pass


class ShowDocAuthError(ShowDocError):
    pass


class ShowDocNetworkError(ShowDocError):
    pass


class ShowDocClient:
    """Read-only ShowDoc client.

    Important: we do NOT perform CAPTCHA/OCR login. ShowDoc's own backend accepts
    `_item_pwd` in read requests. Its source documents this parameter as the
    cross-origin way to remember/submit an already-known project password.
    """

    def __init__(
        self,
        url: str,
        password: str,
        *,
        timeout: int = 30,
        verify_ssl: bool = True,
        session: requests.Session | None = None,
    ) -> None:
        self.url_info: ShowDocURL = parse_showdoc_url(url)
        self.server_base = self.url_info.server_base
        self.item_id = self.url_info.item_id
        self.initial_page_id = self.url_info.page_id
        self.password = password or ""
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.session = session or requests.Session()

        retry = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=0.6,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "POST"}),
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
                "Origin": self.server_base,
                "Referer": self.url_info.original,
            }
        )

    def _post_api(self, route: str, data: dict[str, Any]) -> dict[str, Any]:
        endpoint = f"{self.server_base}/server/index.php?s={route}"
        try:
            r = self.session.post(
                endpoint,
                data=data,
                timeout=self.timeout,
                verify=self.verify_ssl,
            )
        except requests.RequestException as exc:
            raise ShowDocNetworkError(f"请求 ShowDoc 失败: {exc}") from exc

        if r.status_code != 200:
            raise ShowDocNetworkError(f"ShowDoc HTTP {r.status_code}: {endpoint}")

        try:
            obj = r.json()
        except ValueError as exc:
            preview = r.text[:300].replace("\n", " ")
            raise ShowDocNetworkError(f"ShowDoc 返回的不是 JSON: {preview}") from exc

        code = obj.get("error_code", 0)
        if code not in (0, "0", None):
            msg = obj.get("error_message") or obj.get("error_msg") or "未知错误"
            # Current and legacy ShowDoc permission/password errors vary by version.
            if str(code) in {"10103", "10201", "10202", "10203", "10204", "10205", "10303", "10307"}:
                raise ShowDocAuthError(f"ShowDoc 鉴权失败 ({code}): {msg}")
            raise ShowDocError(f"ShowDoc API 错误 ({code}): {msg}")
        return obj.get("data", {})

    def fetch_item_info(self) -> dict[str, Any]:
        return self._post_api(
            "/api/item/info",
            {
                "item_id": self.item_id,
                "_item_pwd": self.password,
                "show_md": 1,
            },
        )

    def fetch_page_info(self, page_id: str) -> dict[str, Any]:
        data = self._post_api(
            "/api/page/info",
            {
                "page_id": str(page_id),
                "with_path": 1,
                "_item_pwd": self.password,
            },
        )
        if "page_content" in data and isinstance(data["page_content"], str):
            data["page_content"] = html.unescape(data["page_content"])
        return data

    def download(self, url: str) -> tuple[bytes, str | None]:
        try:
            r = self.session.get(url, timeout=self.timeout, verify=self.verify_ssl)
            r.raise_for_status()
            return r.content, r.headers.get("Content-Type")
        except requests.RequestException as exc:
            raise ShowDocNetworkError(f"资源下载失败 {url}: {exc}") from exc
