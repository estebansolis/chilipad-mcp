# Run while chat is closed

The MCP server is not the scheduler. Run `.venv/bin/chilipad-mcp runner` independently. The computer must be awake and online with the correct local profile and an accessible unlocked OS vault. This release has not tested credential access under launchd/systemd; validate it before relying on an unattended routine. Do not use a root/system service or copy a token into service configuration.

First run `notification-test`, confirm it with `inbox`, and test `devices` from the same user/session. Create a user-approved test occurrence a few minutes in the future with a comfortable target, check history and inbox, and independently verify the physical device. Inbox-only delivery is not a wake-up guarantee.

## macOS LaunchAgent

Copy `examples/com.chilipad.mcp.runner.plist` to `~/Library/LaunchAgents/com.chilipad.mcp.runner.plist`. Replace every `/ABSOLUTE/PATH/chilipad-mcp` with your stable checkout path. Use your own user's LaunchAgent, not LaunchDaemon. If using CHILIPAD_DATA_DIR, add the same non-secret EnvironmentVariables entry for every client and the service.

```sh
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.chilipad.mcp.runner.plist
launchctl print gui/$(id -u)/com.chilipad.mcp.runner
```

Check `chilipad-mcp status` for a fresh heartbeat, actual run outcome, and vault errors. The runner avoids an initial credential prompt; its first authenticated operation may report an inaccessible Keychain. Unlock/authorize locally; never put the secret in the plist.

Remove:

```sh
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.chilipad.mcp.runner.plist
rm ~/Library/LaunchAgents/com.chilipad.mcp.runner.plist
```

## Linux systemd user service

Copy `examples/chilipad-mcp.service` to `~/.config/systemd/user/chilipad-mcp.service`, replacing the absolute executable path. Ensure the user session's Secret Service provider is running and unlocked, and D-Bus is available. Use the same profile as your clients.

```sh
systemctl --user daemon-reload
systemctl --user enable --now chilipad-mcp.service
systemctl --user status chilipad-mcp.service
```

Read runner status and test a real occurrence. A systemd user service working in a desktop session does not establish headless support. Do not enable lingering to work around a locked/missing vault.

Remove:

```sh
systemctl --user disable --now chilipad-mcp.service
rm ~/.config/systemd/user/chilipad-mcp.service
systemctl --user daemon-reload
```

Pending claims remain unknown after an interruption. Check the device before a new explicit command. To retry only messages, use `chilipad-mcp retry-notifications`. Stop the service before moving/deleting its checkout or local state.
