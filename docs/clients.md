# Client compatibility

Assessment date: October 23, 2026. “Example” means a registration recipe, not an end-to-end certification. This project exposes local stdio only, using the stable Python MCP 1.x SDK. Its automated ClientSession subprocess handshake was tested. A client requiring a newer protocol capability may need a future SDK upgrade.

| Client | Connection | Credential handling | Verification / status |
| --- | --- | --- | --- |
| Python MCP SDK ClientSession | Launch local executable, stdio | OS vault inside server; tests use no live token | Automated initialization, tools/list, invalid-input tools/call pass |
| Codex local client | `[mcp_servers.chilipad]` command/args; README example | Shared local vault | Official config documented; UI workflow not tested |
| Claude Desktop | `mcpServers` command/args; README example | Shared local vault | Generic stdio recipe; app version/OS workflow not tested |
| Claude Cowork | Requires verified local tool registration specific to Cowork | Must retain shared vault | Not verified; Desktop recipe is not evidence of Cowork compatibility |
| ChatGPT dots | Requires a verified local tool connection or authenticated adapter | Must retain shared vault | Blocked/unverified; no dot adapter, notification integration, or dot end-to-end test ships |
| Meta Muse | Requires independently documented local MCP/tool support | Must retain shared vault | Not verified; no connection method established |

macOS and Linux desktop are implementation targets, not a claim of clean-install certification on both systems. Headless Linux and Windows are unsupported. No tested pair of assistant UIs exists yet; the PRD's two-client acceptance gate remains open.

All implemented tools are available to compatible stdio hosts, subject to their approvals. Tool results may be processed by the assistant provider. No token appears in the client configuration. Do not expose a public remote endpoint or invent platform capabilities to bypass an unsupported client.

Sources: [official MCP server tutorial](https://modelcontextprotocol.io/docs/develop/build-server), [official Codex MCP guidance](https://developers.openai.com/codex/mcp). App availability and versions need independent testing before adding support claims.
