# Assistant-assisted setup

Read README.md first. Never request passwords or tokens in conversation or pass them into tools. Token entry belongs in a user-controlled interactive terminal, separate from MCP streams.

1. Explain that this is unofficial and experimental. Check macOS/Linux desktop, Python, uv, vault availability, and the client's ability to launch local stdio. Do not promise dot connectivity.
2. Use `uv sync --frozen`. Direct the user to run `uv run --frozen chilipad-mcp setup` locally. Do not feed secrets through your terminal tool.
3. `list_devices` returns IDs, names, attachments, and discovery guidance. Zero devices means account/linking checks, one needs only a confirmed label, two may use identification, and more than two require selection of a bed/group first.
4. For each selected device, status needs a mapping. Save a temporary user-confirmed alias only if the user can identify it from the returned ID/name. Alternatively start identification with explicitly selected device IDs; never infer left/right from ordering.
5. `identify_devices(action="begin", tests=[{"id":"SELECTED_ID_A","value":68,"unit":"F"},{"id":"SELECTED_ID_B","value":76,"unit":"F"}], confirmed=true)` requires agreement to the exact values and devices. These numbers are illustrative, not comfort defaults. Include `on` only if power changes were explicitly agreed. No maximum modes.
6. Ask which controller belongs to which side. Read back aliases, IDs, optional group and viewpoint; call `save_device_mapping(rows=[...], confirmed=true)` only after confirmation. `position`, e.g. “left while lying in bed,” is optional metadata.
7. `identify_devices(action="finish")` restores by default and verifies original settings through reads. Keeping test settings requires `keep=true, confirmed=true`. If recovery remains pending, explain the actual per-controller result. For cancel/interruption use `recover` or `cancel`; never overwrite possible manual changes without fresh agreement (`force=true, confirmed=true`). Recovery is explicit on restart; the server reports it and blocks conflicting writes until resolved.
8. Register the absolute executable path in the selected client. Test a real `list_devices` invocation. Credential storage and mappings are shared across clients on this computer.
9. Offer only requested routines. Collect target, action time, timezone, recurrence or exact date, temperature, power choice, and allowed catch-up window. Explain inbox-only notifications and 12-hour command suppression. Never enable samples silently. Run notification-test and check the actual background runner before declaring the schedule operational.

Local mappings are convenience labels for one OS user, not an authorization boundary. Use a separate OS account for another person; avoid multiple active profiles using the same Sleepme account because budgets would be split.

No relative-temperature tool ships in v0.1. Read the saved target, show the computed value and unit, validate representability, and ask for clarification if a maximum mode or ambiguous side is involved. Never round or guess. Use independent calls for explicit multi-side requests and report partial failures.
