# Security

## Scope

ShowDoc2MD handles document URLs and passwords. Treat both as sensitive input.

- Prefer `SHOWDOC_PASSWORD` on the MCP server when one deployment serves documents that share a password.
- Do not commit `.env`, exported documents, logs, passwords, or private ShowDoc URLs.
- Keep the default MCP bind address (`127.0.0.1`) unless remote access is required.
- For LAN/remote Streamable HTTP, configure `--allowed-host` explicitly.
- For LAN/remote Streamable HTTP, set `SHOWDOC_MCP_TOKEN`; ShowDoc2MD requires Bearer authentication by default for non-loopback listeners.
- Use `--allow-unauthenticated-remote` only on a trusted private network/VPN when you deliberately do not want a token.
- Do not expose an unauthenticated MCP endpoint directly to the public Internet. For public deployments, also use TLS plus a private network/VPN, authenticated reverse proxy, or an MCP OAuth deployment.

## Reporting a vulnerability

Please open a GitHub Security Advisory when available. Avoid posting passwords, private document URLs, exported document contents, or other secrets in public issues.
