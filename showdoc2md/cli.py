from __future__ import annotations

import argparse
import json
import os
import sys

from .client import ShowDocClient
from .exporter import ShowDocExporter
from .mcp_server import run_mcp
from .server import run_server


def _configure_console_encoding() -> None:
    """Keep Chinese output readable on Windows consoles and AgentDock pipes."""
    if os.name != "nt":
        return
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _password(args: argparse.Namespace) -> str:
    value = args.password if getattr(args, "password", None) is not None else os.getenv("SHOWDOC_PASSWORD", "")
    if value == "":
        raise SystemExit("缺少文档密码：请使用 --password 或环境变量 SHOWDOC_PASSWORD")
    return value


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="showdoc2md", description="Export ShowDoc to Markdown")
    sub = p.add_subparsers(dest="cmd", required=True)

    exp = sub.add_parser("export", help="导出完整 Markdown")
    exp.add_argument("url")
    exp.add_argument("--password", "-p", default=None)
    exp.add_argument("--output", "-o", default="output")
    exp.add_argument("--no-assets", action="store_true", help="不下载图片资源")
    exp.add_argument("--insecure", action="store_true", help="关闭 TLS 证书验证")
    exp.add_argument("--json", action="store_true", help="以 JSON 输出结果")

    probe = sub.add_parser("probe", help="只测试鉴权和目录读取")
    probe.add_argument("url")
    probe.add_argument("--password", "-p", default=None)
    probe.add_argument("--insecure", action="store_true")

    srv = sub.add_parser("serve", help="启动旧版本地 HTTP 转换服务")
    srv.add_argument("--host", default="127.0.0.1")
    srv.add_argument("--port", type=int, default=18765)

    mcp_cmd = sub.add_parser("mcp", help="启动 MCP Server（推荐 AI 接入方式）")
    mcp_cmd.add_argument("--transport", choices=["streamable-http", "stdio"], default="streamable-http")
    mcp_cmd.add_argument("--host", default="127.0.0.1")
    mcp_cmd.add_argument("--port", type=int, default=18765)
    mcp_cmd.add_argument("--path", default="/mcp")
    mcp_cmd.add_argument(
        "--allowed-host",
        action="append",
        default=None,
        help="远程访问时允许的 Host/IP，可重复指定；会自动同时允许任意端口",
    )
    mcp_cmd.add_argument(
        "--allowed-origin",
        action="append",
        default=None,
        help="浏览器 MCP 客户端允许的 Origin，可重复指定",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    _configure_console_encoding()
    args = build_parser().parse_args(argv)
    if args.cmd == "serve":
        run_server(args.host, args.port)
        return 0
    if args.cmd == "mcp":
        run_mcp(
            transport=args.transport,
            host=args.host,
            port=args.port,
            path=args.path,
            allowed_hosts=args.allowed_host,
            allowed_origins=args.allowed_origin,
        )
        return 0

    client = ShowDocClient(args.url, _password(args), verify_ssl=not args.insecure)
    if args.cmd == "probe":
        item = client.fetch_item_info()
        print(json.dumps({
            "ok": True,
            "item_id": client.item_id,
            "item_name": item.get("item_name"),
            "item_type": item.get("item_type"),
            "has_menu": isinstance(item.get("menu"), dict),
        }, ensure_ascii=False, indent=2))
        return 0

    result = ShowDocExporter(client).export(args.output, download_assets=not args.no_assets)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"导出完成：{result.item_name}")
        print(f"页面：{result.pages}")
        print(f"完整 Markdown：{result.combined_md}")
        print(f"清单：{result.manifest_json}")
        if result.failed_pages:
            print(f"失败页面：{len(result.failed_pages)}", file=sys.stderr)
        if result.failed_assets:
            print(f"失败资源：{len(result.failed_assets)}", file=sys.stderr)
    if not result.complete:
        print("导出不完整：存在失败页面或资源，进程返回非零状态。", file=sys.stderr)
        return 2
    return 0
