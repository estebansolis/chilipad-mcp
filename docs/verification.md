# Verification status and opt-in hardware procedure

Release: experimental 0.1.0, October 23, 2026. No real Sleepme credential or device was used to develop or test this release. No hardware state was changed during publication.

## Completed locally

The automated test suite passes with warnings treated as errors; CI reports the current count.

- Locked dependency resolution and clean Python environment installation on macOS arm64 / Python 3.14.
- Synthetic API tests: valid/invalid unit boundaries, sentinel modes, minimal PATCH payloads, model/connectivity guards, redacted errors, ambiguous write timeouts, shared budget, and 429 blocking.
- Mapping targeting and confirmation, read-only discovery-ID inspection before mapping, device-count discovery branches, water unknown handling, candidate credential validation before replacement, and rejection of visible token-entry fallback.
- Identification original-state snapshots, restoration reads, second-device failure, manual temperature/power change protection, and explicit recovery.
- Markdown validation, rejected-edit preservation, duplicate prevention across runner restarts, missed alarms, date-specific overrides, autumn/spring DST policy, notification-only retries, explicit/external change suppression and resumption, deadline checks after slow operations, changed-definition guards, local-date startup, and orphaned-routine pause/deletion.
- Actual MCP SDK subprocess initialization, tools/list, and tools/call validation; no hardware or vault lookup required.
- Static Postman CLI lint: fourteen requests, zero errors, zero warnings. Lint does not send API requests.

GitHub Actions runs macOS/Ubuntu with Python 3.11 and 3.14 using mocks. A green workflow verifies software behavior, not OS credential access or physical controls. Refer to actual workflow results for platform evidence rather than assuming that a configured matrix passed.

## Remaining release gates

| Area | Evidence still needed |
| --- | --- |
| macOS Keychain | User-controlled save/read/delete and unattended LaunchAgent access |
| Linux desktop | Actual Secret Service/session unlock and systemd-user credential access |
| Headless Linux | Unsupported; secure unattended backend not selected/tested |
| Hardware | Real discovery/model strings, connected-state semantics, minimal writes, water fields, identification/restoration |
| Reports | Provider shapes and actual date interval boundaries; no invented side attribution |
| Clients | End-to-end UI tests; two compatible clients sharing one vault; Cowork, dots, Muse each independently |
| Notifications | Only local inbox implemented; push/dot/audible integration absent |
| Usability | First-run pilot and setup-time study not performed |

The PRD's complete acceptance criteria are not yet certified. Known v0.1 scope choices include a fixed 12-hour explicit-command suppression window; explicit recovery on reconnect; weekly or exact-date triggers; action time instead of computed preconditioning lead time; a 31-day maximum missed-run enumeration; no automatic groups, dot bridge, or push notifications. Pending identification is reported and blocks conflicting writes; restoration cannot execute while the computer is stopped/offline. User cancellation and recovery are explicit commands, not an automatic wall-clock timeout. Compatibility targets remain unverified until tested, rather than being silently enabled.

## Opt-in live verification

This is a manual procedure, not an instruction for assistants to run without user agreement.

1. Install from the lockfile. Enter your token yourself at the hidden local `setup` prompt. Verify it was stored in the expected OS vault. Never include it in logs, screenshots, command arguments, chat, or environment exports.
2. Run only discovery and selected read-only status/report operations first. Record sanitized model/field availability and platform/client versions privately. Respect the account budget of ten requests per discrete minute, shared with other consumers.
3. Select one controller by a confirmed ID/alias. Explain the exact proposed power/temperature change and original state. Obtain agreement before a write; save original settings before testing. Do not test maximum modes unless specifically requested.
4. Apply one minimal update. Read status separately within budget. Distinguish acceptance, observed target, and physical temperature. Inspect actual hardware. Restore and verify original state; record only synthetic/sanitized examples publicly.
5. For identification, agree two comfortable distinct targets, verify reliable snapshots, inspect controllers, confirm aliases/viewpoint, and finish with restoration. Deliberately test interruption only when you can restore manually. A failed restoration must remain pending; don't erase recovery to get a clean result.
6. Validate a future one-time routine with an awake computer and a tested inbox, first foreground, then the actual background user service. Close chat, wait for the agreed occurrence, inspect history/inbox, and verify the device. Check missed-run behavior after downtime and vault lock errors separately. Never use it as your sole wake alarm.
7. Test each advertised assistant by invoking tools through its real connection. Do not mark dots or any other UI compatible based solely on the Python stdio test.

The bundled Postman collection is reference material. If using Postman, choose a single authorized request with `-i` and a private local environment; do not run the entire collection, since it includes every device write recipe. For ordinary use, prefer the vault-backed server rather than exporting a token to Postman. Postman is not a runtime dependency.
