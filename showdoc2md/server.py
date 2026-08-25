from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .client import ShowDocClient
from .exporter import ShowDocExporter


class Handler(BaseHTTPRequestHandler):
    server_version = "ShowDoc2MD/0.1"

    def _send(self, status: int, obj: dict) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send(200, {"ok": True})
        else:
            self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/convert":
            self._send(404, {"ok": False, "error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            url = str(payload.get("url") or "")
            password = str(payload.get("password") or "")
            output = str(payload.get("output_dir") or "output")
            download_assets = bool(payload.get("download_assets", True))
            verify_ssl = bool(payload.get("verify_ssl", True))
            client = ShowDocClient(url, password, verify_ssl=verify_ssl)
            result = ShowDocExporter(client).export(output, download_assets=download_assets)
            status = 200 if result.complete else 502
            self._send(status, {"ok": result.complete, "complete": result.complete, "result": result.to_dict()})
        except Exception as exc:
            self._send(400, {"ok": False, "error": str(exc)})

    def log_message(self, fmt: str, *args) -> None:
        print("[showdoc2md] " + (fmt % args))


def run_server(host: str, port: int) -> None:
    try:
        httpd = ThreadingHTTPServer((host, port), Handler)
    except OSError as exc:
        raise RuntimeError(
            f"无法监听 http://{host}:{port}；端口可能已被占用或被系统保留。请改用 --port 指定其他端口。原始错误: {exc}"
        ) from exc
    print(f"ShowDoc2MD HTTP server: http://{host}:{port}")
    print(f"Health: http://{host}:{port}/health")
    httpd.serve_forever()
