# ShowDoc2MD

[![CI](https://github.com/ishare2121/ShowDoc2MD/actions/workflows/ci.yml/badge.svg)](https://github.com/ishare2121/ShowDoc2MD/actions/workflows/ci.yml)

将 **已知访问密码的 ShowDoc 项目**读取并转换为 Markdown，供 AI / Agent / RAG 使用。

支持三种使用方式：

- **MCP Server（推荐）**：Cursor、Codex、Claude、AgentDock 等 AI 客户端自动发现工具并调用。
- **CLI**：手工或脚本批量导出 Markdown。
- **Legacy HTTP API**：保留 `/convert` 兼容接口。

> ShowDoc2MD 只用于读取你已经合法获得访问权限和密码的文档。它不会猜测、破解或暴力尝试密码。

## 为什么做这个项目

受密码保护的 ShowDoc 页面通常要求浏览器先完成验证码/密码交互，这对 AI Agent 自动阅读文档非常不方便。

ShowDoc 的只读接口允许请求携带 `_item_pwd=<已知文档密码>`。ShowDoc2MD 通过这一正常读取参数访问项目目录和页面，因此不需要 AI 去模拟网页验证码流程。

当前主要读取：

- `/api/item/info`
- `/api/page/info`

## 安装

要求：**Python 3.10+**。

### Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows_install.ps1
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

## MCP：推荐的 AI 接入方式

ShowDoc2MD 使用官方 Python MCP SDK，支持：

- `stdio`：适合同一台机器上的 AI 客户端。
- `Streamable HTTP`：适合部署在一台固定机器上，其他 AI 客户端通过网络连接。

### 暴露给 AI 的工具

| Tool | 用途 |
|---|---|
| `showdoc_probe` | 验证 ShowDoc 地址和密码是否可读取 |
| `showdoc_list_pages` | 获取整个项目目录，不读取所有正文 |
| `showdoc_read_page` | 读取一个页面并返回 Markdown |
| `showdoc_read_full` | 读取整个项目并合并为 Markdown |
| `showdoc_export` | 在 MCP 服务器机器上导出 Markdown 文件和资源 |

AI 客户端连接后会通过 MCP schema 自动得到这些工具的参数和说明，不需要另外告诉模型 HTTP JSON 格式。

### 方式一：同机 stdio

先安装 ShowDoc2MD，然后在 MCP 客户端中配置一个 stdio server。通用配置示意：

```json
{
  "mcpServers": {
    "showdoc2md": {
      "command": "showdoc2md",
      "args": ["mcp", "--transport", "stdio"],
      "env": {
        "SHOWDOC_PASSWORD": "your-document-password"
      }
    }
  }
}
```

如果不同 ShowDoc 项目使用不同密码，可以不设置 `SHOWDOC_PASSWORD`，由 AI 在每次工具调用时传 `password`。

### 方式二：固定机器部署 Streamable HTTP

仅本机访问：

```powershell
$env:SHOWDOC_PASSWORD='your-document-password'
.\showdoc2md.cmd mcp
```

默认 MCP 地址：

```text
http://127.0.0.1:18765/mcp
```

Linux / macOS：

```bash
export SHOWDOC_PASSWORD='your-document-password'
showdoc2md mcp
```

AI 客户端只需要配置 MCP URL：

```text
http://127.0.0.1:18765/mcp
```

### 局域网 / 远程机器

MCP SDK 默认启用 DNS-rebinding 防护。监听非本机地址时，ShowDoc2MD 要求你明确写出 AI 实际访问的服务器 Host/IP：

```powershell
.\showdoc2md.cmd mcp `
  --host 0.0.0.0 `
  --port 18765 `
  --allowed-host 192.168.1.20
```

然后 AI 客户端连接：

```text
http://192.168.1.20:18765/mcp
```

如果通过域名访问：

```bash
showdoc2md mcp \
  --host 0.0.0.0 \
  --port 18765 \
  --allowed-host mcp.example.com
```

`--allowed-host mcp.example.com` 会同时允许 `mcp.example.com:*`。

浏览器型 MCP 客户端如果会发送 `Origin`，可以额外添加：

```text
--allowed-origin https://app.example.com
```

> **安全提示**：不要把无认证的 MCP 服务直接暴露到公网。公网部署建议放在 VPN/Tailscale、反向代理认证或符合 MCP 规范的 OAuth 2.1 资源服务器之后。

### Docker

仓库附带 `Dockerfile` 和 `docker-compose.example.yml`。本机部署示例：

```bash
export SHOWDOC_PASSWORD='your-document-password'
docker compose -f docker-compose.example.yml up -d --build
```

默认只把端口映射到宿主机 `127.0.0.1:18765`。如果要从其他机器访问，请同时修改端口映射，并把容器启动参数中的 `--allowed-host` 改成 AI 实际访问的服务器 IP/域名。

## AI 应该怎样使用

通常不需要写特殊提示词，MCP Server 自带 instructions。推荐调用顺序：

1. 不确定权限时：`showdoc_probe`
2. 先看结构：`showdoc_list_pages`
3. 只需要少量内容：`showdoc_read_page`
4. 需要全项目分析：`showdoc_read_full`
5. 需要落盘文件：`showdoc_export`

例如你可以直接对 AI 说：

```text
阅读这个 ShowDoc 并总结它的 API 认证方式：
https://www.showdoc.com.cn/100200/300400
```

如果密码已经配置在 MCP 服务器的 `SHOWDOC_PASSWORD` 环境变量中，AI 不需要再拿到密码。

## CLI

### 检查是否可访问

```powershell
$env:SHOWDOC_PASSWORD='your-document-password'
.\showdoc2md.cmd probe 'https://www.showdoc.com.cn/100200/300400'
```

### 完整导出

```powershell
.\showdoc2md.cmd export 'https://www.showdoc.com.cn/100200/300400' --output .\output
```

也可以直接传密码：

```bash
showdoc2md export 'https://www.showdoc.com.cn/100200/300400' \
  --password 'your-document-password' \
  --output ./output
```

推荐环境变量方式，避免密码进入 shell history。

## 导出结构

```text
output/
└── ProjectName_itemId/
    ├── 完整文档.md
    ├── manifest.json
    ├── assets/
    └── pages/
        ├── 0001_Overview.md
        └── API/
            └── 0002_CreateOrder.md
```

- 普通 ShowDoc Markdown 页面尽量原样保存。
- RunAPI/API JSON 页面转换为可读 Markdown。
- 页面内图片默认下载到 `assets/` 并重写链接。
- `完整文档.md` 按目录顺序合并页面。
- `manifest.json` 记录页面、失败项和 `complete` 状态。

### 完整性保护

ShowDoc2MD 不会把“部分成功”伪装成完整成功：

- 项目目录返回 0 页时直接报错。
- 任一页面或要求下载的资源失败时，`complete=false`。
- CLI 在导出不完整时返回非 0 退出码。
- MCP / HTTP 结果会显式返回完整性状态。

## Legacy HTTP API

如果已有旧系统使用 `/convert`，可以继续运行：

```powershell
.\showdoc2md.cmd serve --host 127.0.0.1 --port 18765
```

接口：

```text
GET  /health
POST /convert
```

新 AI 集成建议直接使用 MCP，而不是这个接口。

## 开发与测试

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

测试使用虚构 URL、虚构项目和 Fake Client，不包含维护者自己的 ShowDoc 地址、文档密码或导出内容。

## 当前边界

- 当前优先覆盖“项目访问密码”型 ShowDoc。
- 如果某个 ShowDoc 实例强制账号登录（例如 `force_login`），仅项目密码可能不足。
- 页面内图片已支持下载；ShowDoc 独立附件列表尚未作为单独附件功能完整覆盖。

## License

MIT License。详见 [LICENSE](LICENSE)。
