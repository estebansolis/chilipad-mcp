# Changelog

## Unreleased

- Put token acquisition and MCP registration before tool-based onboarding; allow read-only status by a discovered ID before assigning sides.
- Preserve manual power changes during identification recovery and prior power expectations across automatic temperature-only writes.
- Recheck schedule deadlines after slow work and prevent claimed temperature occurrences from adopting edited or paused rules.
- Allow orphaned routines to be listed, paused, or deleted; use each routine's local midnight on first runner start.
- Preserve water observations when inbox delivery fails, reject visible token-entry fallback, and retain the longest shared Retry-After deadline.
- Remove a systemd startup ordering cycle, document foreground-to-background handoff, and add explicit MCP tool descriptions.

## 0.1.0 — 2026-10-23

Initial experimental source release: local stdio MCP with 15 tools; explicit OS vault adapters and hidden local token setup; read/control/report API mapping; alias persistence; recoverable two-controller identification; Markdown schedules, a single-owner runner, durable inbox, cross-process API budget, and service examples.

Automated tests use synthetic responses and a real SDK stdio subprocess. Hardware, background vault access, and assistant UI acceptance are pending. Inbox delivery replaces the proposed dot notification integration for this release; headless Linux is unsupported. See docs/verification.md for deviations from the PRD.
