# Security reporting

Do not post tokens, device identifiers, sleep reports, or local state in public issues. If a token is exposed, revoke/replace it at Sleepme first; deleting this app's vault entry does not revoke it.

Use GitHub's private vulnerability reporting if enabled on this repository. Otherwise open a public issue saying only that you need a private security contact, without exploit details or personal data, and wait for a maintainer-provided private channel. No response-time guarantee is offered.

The local server intentionally has no public HTTP listener. Credentials use explicit macOS Keychain or Linux Secret Service backends. No plaintext backend, token tool argument, environment-token input, or automatic cloud endpoint override is supported. Errors omit upstream response/exception bodies. Local state is private to the OS user but may contain device and sleep information. The vault does not defend against malicious code running as that user.

Experimental releases have not completed live-device, unattended-vault, or all client acceptance tests. See docs/verification.md. Keep dependencies updated and validate changes before relying on schedules.
