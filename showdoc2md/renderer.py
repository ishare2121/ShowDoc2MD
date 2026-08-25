from __future__ import annotations

import json
from typing import Any


def _esc(v: Any) -> str:
    if v is None:
        return ""
    return str(v).replace("|", "\\|").replace("\n", "<br>")


def _table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> str:
    if not rows:
        return ""
    head = "| " + " | ".join(label for _, label in columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    lines = [head, sep]
    for row in rows:
        lines.append("| " + " | ".join(_esc(row.get(key, "")) for key, _ in columns) + " |")
    return "\n".join(lines)


def _as_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]
    return []


def render_runapi_json(obj: dict[str, Any]) -> str:
    info = obj.get("info") if isinstance(obj.get("info"), dict) else {}
    request = obj.get("request") if isinstance(obj.get("request"), dict) else {}
    method = str(info.get("method") or "GET").upper()
    url = str(info.get("url") or "")
    title = str(info.get("title") or "")
    desc = str(info.get("description") or info.get("remark") or "")

    lines: list[str] = []
    if title:
        lines += [f"### {title}", ""]
    lines += ["#### 接口", "", f"`{method} {url}`", ""]
    if desc:
        lines += [desc, ""]

    sections: list[tuple[str, Any, list[tuple[str, str]]]] = [
        ("请求头", request.get("headers"), [("name", "名称"), ("value", "值"), ("remark", "说明")]),
        ("Query 参数", request.get("query"), [("name", "参数"), ("type", "类型"), ("required", "必填"), ("value", "示例/默认值"), ("remark", "说明")]),
        ("Cookie", request.get("cookies"), [("name", "名称"), ("value", "值"), ("remark", "说明")]),
    ]
    for heading, value, cols in sections:
        rows = _as_rows(value)
        if rows:
            lines += [f"#### {heading}", "", _table(rows, cols), ""]

    params = request.get("params") if isinstance(request.get("params"), dict) else {}
    mode = params.get("mode")
    if mode:
        lines += ["#### 请求体", "", f"模式：`{mode}`", ""]
    json_body = params.get("json")
    if isinstance(json_body, str) and json_body.strip():
        lines += ["```json", json_body.strip(), "```", ""]
    for key, label in (("formdata", "Form Data"), ("urlencoded", "x-www-form-urlencoded"), ("jsonDesc", "JSON 字段说明")):
        rows = _as_rows(params.get(key))
        if rows:
            cols = [("name", "参数"), ("type", "类型"), ("required", "必填"), ("value", "示例/默认值"), ("remark", "说明")]
            lines += [f"##### {label}", "", _table(rows, cols), ""]

    response = obj.get("response")
    if response:
        lines += ["#### 响应", ""]
        if isinstance(response, str):
            lines += ["```json", response, "```", ""]
        else:
            lines += ["```json", json.dumps(response, ensure_ascii=False, indent=2), "```", ""]

    return "\n".join(lines).strip() + "\n"


def render_page_content(page: dict[str, Any]) -> str:
    raw = page.get("page_content")
    if raw is None:
        return ""
    if not isinstance(raw, str):
        return json.dumps(raw, ensure_ascii=False, indent=2) + "\n"

    text = raw.strip()
    if not text:
        return ""

    # RunAPI/API pages store JSON in page_content. Preserve Markdown pages verbatim.
    if text.startswith("{") or text.startswith("["):
        try:
            obj = json.loads(text)
            if isinstance(obj, dict) and isinstance(obj.get("info"), dict):
                return render_runapi_json(obj)
        except json.JSONDecodeError:
            pass
    return raw.rstrip() + "\n"
