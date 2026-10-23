# Chilipad MCP — unofficial

Control supported Sleepme Chilipad devices from an assistant using a local [Model Context Protocol](https://modelcontextprotocol.io/) server. Check water status, adjust your side of the bed, read available Sleep Tracker reports, and save local temperature routines.

**This is an independent community project by Esteban Solis. It is not made, endorsed, certified, or supported by Sleepme, Chilipad, OpenAI, Anthropic, or Meta.** Product names belong to their respective owners.

**Status: experimental v0.1.0.** The server, mock API behavior, scheduler logic, and real MCP stdio handshake have automated tests. Physical devices, OS credential storage in unattended services, and end-to-end assistant clients have **not** been validated. This is a runnable implementation with release limitations, not a claim that all PRD acceptance criteria passed. See [verification status](docs/verification.md).

## Why I built this

I wanted my assistant to help manage my bed: check whether a controller needs water, adjust the right side, and prepare it before bedtime. I also wanted the same local setup and preferences to work across assistants without copying my Sleepme token into conversations. This project turns my [Sleepme Postman collection](https://github.com/estebansolis/sleepme-postman) into a reusable local server, with secure credential entry and predictable device targeting.

## What it does

- Discover claimed devices and save user-confirmed aliases such as “my side” and “partner side.”
- Read model-specific status and low-water signals. Missing or offline readings remain unknown; water level is never labeled a percentage.
- Control verified, connected Dock Pro controllers: thermal power, temperatures, display units, and device timezone.
- Identify two controllers with explicitly agreed temporary temperatures and persisted recovery snapshots.
- Retrieve account-scoped Sleep Tracker reports, preserving missing scores and nullable metrics.
- Read and edit versioned local Markdown alarms and routines; run enabled schedules while chat is closed using a separate local runner.
- Keep an execution history and a durable local notification inbox.

Normal temperatures are **55–115°F in whole degrees** or **13–48°C in 0.5° steps**. Maximum cooling/heating require named modes. Temperature changes do not turn power on implicitly. “Off” means thermal standby, not a mains disconnect. A successful request does not mean the mattress has reached the target.

No automatic refilling, water-quality sensing, medical interpretation, audible wake alarm, or public HTTP endpoint is included. No telemetry is implemented. Requests go to Sleepme’s cloud over HTTPS; this is not LAN control.

## Install on macOS or Linux desktop

Prerequisites: Python 3.11–3.14, Git, [uv](https://docs.astral.sh/uv/getting-started/installation/), a Sleepme account with API access and claimed compatible devices, and a local MCP client. macOS needs an unlocked Keychain. Linux needs an unlocked Secret Service provider and a working session D-Bus; **headless Linux is not supported in this release**. Windows is outside scope.

```sh
git clone https://github.com/estebansolis/chilipad-mcp.git
cd chilipad-mcp
uv sync --frozen
uv run --frozen chilipad-mcp setup
uv run --frozen chilipad-mcp devices
```

`uv.lock` pins the dependency graph. The server stays in this checkout, so keep its path stable. After installation, `.venv/bin/chilipad-mcp` can be used directly without invoking uv. This project has not been published to PyPI; do not install an unrelated package by name.

### Get a Sleepme API token

1. Open [Sleepme](https://www.sleep.me) yourself and sign in. Do not give your assistant your password.
2. Open **Account Details → Developer API**, following [Sleepme’s official setup guide](https://docs.developer.sleep.me/docs/setup/). The PRD also identifies [the developer account page](https://sleep.me/account/developers) as an entry point. Account menus and eligibility can vary; signed-in controls have not been verified for this release. If the option is missing, consult Sleepme support rather than inventing credentials or OAuth steps.
3. Create or retrieve your developer API token in that account interface.
4. In your **own local terminal**, run `uv run --frozen chilipad-mcp setup` and paste it at the hidden prompt. Never paste it into chat, a tool argument, an issue, or an assistant's terminal tool whose input is recorded.

Setup validates the candidate with `GET /devices` and saves it only after validation succeeds. It does not replace a working credential with a failed candidate. No device write happens during credential setup.

### How we recommend securing the token

The token grants account API access; treat it like a password. The application explicitly uses **macOS Keychain** or **Linux Secret Service**, with service `sleepme-mcp` and account `api-token`. It refuses plaintext and automatic fallback backends. A missing or locked vault is an error.

Keep your OS account and vault locked when away, use disk encryption, and install only trusted MCP clients and code. Vault storage protects the token at rest; trusted local processes may still retrieve it after unlock. A compromised assistant with shell access can access more than MCP tools. Keep device and report access approvals appropriate to your client. Do not expose this stdio process through an unauthenticated HTTP bridge.

Do not put the token in `.env`, JSON, Markdown, client config, shell arguments, scripts, screenshots, Postman exports, or Git. Runtime HTTPS requests use the token in memory and do not follow redirects or use environment proxies. Only executable paths and non-secret arguments belong in client configuration.

Replace a token by running `setup` again. Remove the local copy with:

```sh
uv run --frozen chilipad-mcp remove-token
```

Local deletion **does not revoke** the token at Sleepme. If exposed, revoke/delete or replace it through Sleepme's account controls or contact their support, then save the replacement locally. Exact provider revocation UI has not been independently validated. Do not include a token in a security report.

## Connect your assistant

Use the **absolute** path returned by `pwd` after entering this repository. The client launches the server as a subprocess; no token environment variable is needed.

Generic stdio / Claude Desktop configuration example:

```json
{
  "mcpServers": {
    "chilipad": {
      "command": "/ABSOLUTE/PATH/chilipad-mcp/.venv/bin/chilipad-mcp",
      "args": ["serve"]
    }
  }
}
```

Codex configuration example in its `config.toml`, consistent with [official MCP configuration guidance](https://developers.openai.com/codex/mcp):

```toml
[mcp_servers.chilipad]
command = "/ABSOLUTE/PATH/chilipad-mcp/.venv/bin/chilipad-mcp"
args = ["serve"]
```

Restart/reconnect the client and call `list_devices`. The automated stdio test proves a local SDK client can discover and invoke tools; it does not certify any assistant UI. [Client compatibility](docs/clients.md) records Cowork, ChatGPT dots, and Meta Muse separately. Cloud-only clients cannot reach a local subprocess just because this repo is installed. No bridge or dot adapter ships here.

Assistant starter prompt:

> Help me install and set up this unofficial Chilipad MCP locally. Read README.md and docs/setup.md, verify my operating system and client's local stdio support, and follow the locked installation steps. Never ask me to paste a token into this conversation or capture it through a recorded terminal tool. Direct me to the hidden local setup prompt. Discover devices, explain available capabilities, and ask me to confirm side assignments. Do not run Postman write recipes, enable example schedules, or perform a temperature identification test without my agreement.

## Daily use and routines

After confirming a mapping, try “Check water on my side,” “Set my side to 70°F,” or “Show my routines.” Ask explicitly for both sides to change both; the assistant calls each target separately and reports each outcome. Unmapped or ambiguous aliases fail rather than guessing.

`prepare_bed` uses a saved temperature routine, including power only if explicitly configured. For bedtime preconditioning, save the **action time** (for example 20 minutes before bedtime) and the allowed catch-up window; this release does not compute lead time from a separate bedtime field. Alarms here mean scheduled temperature changes or calendar reminders, **not reliable waking services**.

The local runner polls every 15 seconds. It claims an occurrence before a write to prevent duplicate actions after restart; an interrupted claim remains `claimed_unknown` and is not retried automatically. Explicit device changes suppress automatic writes to that device for 12 hours, visible in `get_routine_status`; resume only at the user's request. Observed changes since the last automatic write also suppress automation. External changes before the first automatic write cannot be identified reliably.

Start by testing the local inbox:

```sh
uv run --frozen chilipad-mcp notification-test
uv run --frozen chilipad-mcp inbox
uv run --frozen chilipad-mcp runner
```

Inbox delivery is durable local storage, not a push notification. Read it in a compatible assistant or with `inbox`; nothing will pop up or make a sound. Enabled routines require a confirmed target and a tested inbox. Full unattended operation also requires you to validate vault access in the actual background context. See [schedule schema](docs/routines.md) and [background services](docs/background.md).

## Local data, recovery, and troubleshooting

Run `chilipad-mcp data-dir` to find local state. Default locations are `~/Library/Application Support/chilipad-mcp` on macOS and `$XDG_CONFIG_HOME/chilipad-mcp` (usually `~/.config/chilipad-mcp`) on Linux. `devices.md`, `alarms.md`, and `routines.md` are canonical definitions outside the clone. Directory access is restricted to the current user; atomic writes and locks coordinate clients. `CHILIPAD_DATA_DIR` optionally selects an isolated profile; keep every client and runner on the same profile to share the rate budget. Never use separate profiles for one account's simultaneous activity.

- **No token / locked vault:** unlock the OS vault and use local `setup`. No plaintext workaround is supported.
- **No devices:** verify token/account and device claiming in Sleepme. Do not guess device IDs.
- **Model rejected:** writes require a status model normalized to `Dock Pro` and explicit online status. Unknown model strings fail closed pending evidence.
- **Rate limited:** all local processes share a 10-request discrete-minute budget. Other apps/Postman still count against Sleepme's account limit. Wait for the next minute or saved Retry-After. Reads can retry short 429 delays; writes never automatically retry.
- **Uncertain write:** read status before issuing another command. Request acceptance and observed target are different from actual water temperature.
- **Interrupted identification:** run `chilipad-mcp recover` or use `identify_devices` recovery. Original snapshots persist. If settings differ from the test, obtain fresh agreement before forced restoration. Sleeping/offline computers cannot restore immediately.
- **Invalid Markdown:** repair the strict JSON block. Manual invalid edits suspend schedule execution; the last valid snapshot remains available for repair. Free text cannot execute commands.
- **Runner unavailable:** check service status, vault unlock, heartbeat, `runner-error.json`, and history. Computer sleep and network outages interrupt schedules.

Stop/remove the background service before uninstalling, remove the local token if desired, and separately delete local data if you want to remove aliases, reports in history, and schedules. Local state and inbox may contain private device identifiers or sleep information; do not publish them.

## Development

```sh
uv sync --frozen --extra dev
uv run --frozen pytest
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv build
```

Tests use synthetic data and never require a real Sleepme token. [Live verification](docs/verification.md) is a separate opt-in procedure. Do not run the entire Postman collection: it contains power, temperature, and maximum-mode writes.

See [API mapping](docs/api.md), [contributing](CONTRIBUTING.md), [security reporting](SECURITY.md), and [release notes](CHANGELOG.md). Original implementation is MIT licensed; bundled Sleepme reference material retains its own attribution and is excluded from that license grant; see [NOTICE](NOTICE).
