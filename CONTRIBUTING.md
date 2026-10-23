# Contributing

Use Python 3.11 or newer and the frozen uv dependency graph. Run the commands in README.md, add deterministic mock tests for behavior changes, and never require a token for CI. Contributions should preserve minimal allowlisted PATCH payloads, side confirmation, vault-only secrets, recovery snapshots, and shared rate limiting.

Do not commit personal environments, live IDs, tokens, local Markdown/state, or raw sleep reports. Synthetic fixtures must say they are synthetic. Do not run a whole write-bearing collection as validation. Hardware testing requires an explicit opt-in, selected controller, agreed setting, and documented restoration.

Changing client support claims requires an end-to-end result recording client/version, OS, connection method, tool call, shared vault behavior, and limitations. A generic MCP handshake alone does not certify dots, Cowork, or Muse. Keep unfinished features disabled and update the verification matrix when evidence changes.

Original code contributions are submitted under this project's MIT license. Bundled third-party references retain their attribution and are excluded from that grant.
