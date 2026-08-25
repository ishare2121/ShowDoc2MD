from __future__ import annotations

import hmac
import os
from pathlib import Path
from typing import Any

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from .client import ShowDocClient, ShowDocError
from .exporter import ShowDocExporter
from .normalize import collect_pages
from .renderer import render_page_content


MCP_INSTRUCTIONS = """ShowDoc2MD lets AI read ShowDoc projects when the user already knows the document password.
Use showdoc_probe first when access is uncertain. Use showdoc_list_pages to inspect structure, showdoc_read_page for focused reading, and showdoc_read_full only when the whole project is needed. Use showdoc_export when files must be written to disk.
Never guess or brute-force passwords. Do not expose passwords in tool output."""

mcp = MCPServer("ShowDoc2MD", instructions=MCP_INSTRUCTIONS)


class BearerTokenMiddleware:
    """Small ASGI wrapper for deployments that want a static bearer token.

    MCP itself remains the protocol spoken behind this wrapper. The token is
    intentionally configured only on the server and is never returned by a
    tool result or logged here.
    """

    def __init__(self, app: Any, token: str) -> None:
        self.app = app
        self.token = token.encode("utf-8")

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http" or scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return

        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        supplied = headers.get(b"authorization", b"")
        prefix = b"Bearer "
        valid = supplied.startswith(prefix) and hmac.compare_digest(supplied[len(prefix) :], self.token)
        if valid:
            await self.app(scope, receive, send)
            return

        body = b'{"error":"unauthorized"}'
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"www-authenticate", b"Bearer"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


def _resolve_password(password: str | None) -> str:
    value = password if password is not None else os.getenv("SHOWDOC_PASSWORD", "")
    if not value:
        raise ShowDocError("缺少 ShowDoc 文档密码。请传 password，或在 MCP 服务端配置 SHOWDOC_PASSWORD。")
    return value


def _client(url: str, password: str | None, verify_ssl: bool = True) -> ShowDocClient:
    return ShowDocClient(url, _resolve_password(password), verify_ssl=verify_ssl)


def _item_summary(client: ShowDocClient, item: dict[str, Any]) -> dict[str, Any]:
    refs = collect_pages(item)
    return {
        "ok": True,
        "item_id": client.item_id,
        "item_name": item.get("item_name"),
        "item_type": item.get("item_type"),
        "page_count": len(refs),
        "initial_page_id": client.initial_page_id,
    }


@mcp.tool()
def showdoc_probe(url: str, password: str | None = None, verify_ssl: bool = True) -> dict[str, Any]:
    """Check whether a ShowDoc URL can be read with an already-known document password.

    Args:
        url: A ShowDoc project/page URL.
        password: Known document password. If omitted, server-side SHOWDOC_PASSWORD is used.
        verify_ssl: Verify HTTPS certificates. Keep true unless testing a trusted self-hosted instance.
    """
    client = _client(url, password, verify_ssl)
    return _item_summary(client, client.fetch_item_info())


@mcp.tool()
def showdoc_list_pages(url: str, password: str | None = None, verify_ssl: bool = True) -> dict[str, Any]:
    """List every page in a ShowDoc project without downloading page bodies."""
    client = _client(url, password, verify_ssl)
    item = client.fetch_item_info()
    refs = collect_pages(item)
    return {
        **_item_summary(client, item),
        "pages": [
            {
                "page_id": ref.page_id,
                "title": ref.title,
                "path": ref.path,
                "order": ref.order,
            }
            for ref in refs
        ],
    }


@mcp.tool()
def showdoc_read_page(
    url: str,
    page_id: str | None = None,
    password: str | None = None,
    verify_ssl: bool = True,
) -> dict[str, Any]:
    """Read one ShowDoc page and return Markdown suitable for an AI context.

    If page_id is omitted, the page ID embedded in the supplied URL is used.
    """
    client = _client(url, password, verify_ssl)
    target = str(page_id or client.initial_page_id or "")
    if not target:
        raise ShowDocError("缺少 page_id，并且 URL 中也没有页面 ID。请先调用 showdoc_list_pages。")
    page = client.fetch_page_info(target)
    return {
        "ok": True,
        "item_id": client.item_id,
        "page_id": target,
        "title": page.get("page_title"),
        "markdown": render_page_content(page),
    }


@mcp.tool()
def showdoc_read_full(
    url: str,
    password: str | None = None,
    verify_ssl: bool = True,
) -> dict[str, Any]:
    """Read the whole ShowDoc project and return one combined Markdown string.

    Prefer showdoc_list_pages + showdoc_read_page for large projects when only a few pages are needed.
    This tool does not persist files and does not download image bytes.
    """
    client = _client(url, password, verify_ssl)
    item = client.fetch_item_info()
    refs = collect_pages(item)
    if not refs:
        raise ShowDocError("ShowDoc 项目目录未返回任何页面。")

    item_name = str(item.get("item_name") or f"showdoc_{client.item_id}")
    parts = [f"# {item_name}", "", "## 目录", ""]
    for ref in refs:
        parts.append(f"- {' / '.join(ref.path + [ref.title])}")
    parts.append("")

    pages: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for ref in refs:
        try:
            page = client.fetch_page_info(ref.page_id)
            title = str(page.get("page_title") or ref.title)
            markdown = render_page_content(page)
            parts.extend(["---", "", f"## {' / '.join(ref.path + [title])}", "", markdown.rstrip(), ""])
            pages.append({"page_id": ref.page_id, "title": title, "path": ref.path})
        except Exception as exc:
            failures.append({"page_id": ref.page_id, "title": ref.title, "error": str(exc)})

    complete = len(pages) == len(refs) and not failures
    return {
        "ok": complete,
        "complete": complete,
        "item_id": client.item_id,
        "item_name": item_name,
        "page_count_discovered": len(refs),
        "page_count_read": len(pages),
        "pages": pages,
        "failed_pages": failures,
        "markdown": "\n".join(parts).rstrip() + "\n",
    }


@mcp.tool()
def showdoc_export(
    url: str,
    output_dir: str = "output",
    password: str | None = None,
    download_assets: bool = True,
    verify_ssl: bool = True,
) -> dict[str, Any]:
    """Export a ShowDoc project to Markdown files on the MCP server machine.

    Returns paths on the MCP server machine. The result includes complete=false if any page or requested asset failed.
    """
    client = _client(url, password, verify_ssl)
    result = ShowDocExporter(client).export(Path(output_dir), download_assets=download_assets)
    return {"ok": result.complete, **result.to_dict()}


def _expand_allowed_hosts(values: list[str] | None) -> list[str] | None:
    if not values:
        return None
    expanded: list[str] = []
    for raw in values:
        value = raw.strip()
        if not value:
            continue
        if value not in expanded:
            expanded.append(value)
        if ":" not in value and f"{value}:*" not in expanded:
            expanded.append(f"{value}:*")
    return expanded or None


def run_mcp(
    *,
    transport: str = "streamable-http",
    host: str = "127.0.0.1",
    port: int = 18765,
    path: str = "/mcp",
    allowed_hosts: list[str] | None = None,
    allowed_origins: list[str] | None = None,
    api_token: str | None = None,
    allow_unauthenticated_remote: bool = False,
) -> None:
    """Run the MCP server over stdio or Streamable HTTP."""
    if transport == "stdio":
        mcp.run(transport="stdio")
        return
    if transport != "streamable-http":
        raise ValueError(f"不支持的 MCP transport: {transport}")
    if not path.startswith("/"):
        path = "/" + path

    local_hosts = {"127.0.0.1", "localhost", "::1"}
    expanded_hosts = _expand_allowed_hosts(allowed_hosts)
    if host not in local_hosts and not expanded_hosts:
        raise ValueError(
            "非本机监听需要显式指定 allowed host，以启用 MCP 的 DNS-rebinding 保护。"
            "请添加 --allowed-host <AI 实际访问的主机名或IP>。"
        )

    resolved_token = api_token if api_token is not None else os.getenv("SHOWDOC_MCP_TOKEN", "")
    if host not in local_hosts and not resolved_token and not allow_unauthenticated_remote:
        raise ValueError(
            "远程 MCP 默认要求 Bearer Token。请设置 SHOWDOC_MCP_TOKEN，"
            "或仅在受信任私网中显式使用 --allow-unauthenticated-remote。"
        )

    transport_security = None
    if expanded_hosts:
        transport_security = TransportSecuritySettings(
            allowed_hosts=expanded_hosts,
            allowed_origins=allowed_origins or [],
        )

    run_kwargs: dict[str, Any] = {
        "host": host,
        "port": port,
        "streamable_http_path": path,
        "stateless_http": True,
        "json_response": True,
    }
    if transport_security is not None:
        run_kwargs["transport_security"] = transport_security
    if not resolved_token:
        mcp.run(transport="streamable-http", **run_kwargs)
        return

    # MCPServer.run() owns uvicorn internally. For bearer auth we construct the
    # exact same Streamable HTTP ASGI app, wrap it, then let uvicorn serve it.
    import uvicorn

    app = mcp.streamable_http_app(
        streamable_http_path=path,
        stateless_http=True,
        json_response=True,
        transport_security=transport_security,
        host=host,
    )
    uvicorn.run(BearerTokenMiddleware(app, resolved_token), host=host, port=port)


if __name__ == "__main__":
    run_mcp()
