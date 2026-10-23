"""Local setup lives outside MCP stdin/stdout and never accepts a token argument."""

import argparse
import getpass
import json
import sys

from . import api, core, credentials, routines
from .storage import UserError, home, read_json


def capture_token():
    if not sys.stdin.isatty():
        raise UserError("Setup requires a local interactive terminal, never chat or MCP stdin.")
    credentials.backend()  # fail before requesting a secret if no secure vault exists
    value = getpass.getpass("Sleepme API token (hidden, stored only in your OS vault): ").strip()
    if not value or any(c.isspace() for c in value):
        raise UserError("Token is empty or contains whitespace; nothing saved.")
    api.request("GET", "/devices", candidate=value)  # read-only validation BEFORE replacement
    credentials.store(value)
    return {"credential": "validated and saved", "next": "Run chilipad-mcp devices."}


def main():
    p = argparse.ArgumentParser(description="Unofficial Chilipad local MCP; macOS/Linux only")
    p.add_argument(
        "command",
        choices=[
            "serve",
            "setup",
            "remove-token",
            "status",
            "devices",
            "runner",
            "inbox",
            "notification-test",
            "retry-notifications",
            "recover",
            "data-dir",
        ],
    )
    args = p.parse_args()
    try:
        if sys.platform != "darwin" and not sys.platform.startswith("linux"):
            raise UserError("Only macOS and Linux are supported targets.")
        if args.command == "serve":
            from .server import serve

            serve()
            return
        if args.command == "runner":
            routines.run()
            return
        if args.command == "setup":
            result = capture_token()
        elif args.command == "remove-token":
            credentials.delete()
            result = {
                "removed_locally": True,
                "note": "Also revoke it in your Sleepme account if needed.",
            }
        elif args.command == "devices":
            result = core.list_devices()
        elif args.command == "recover":
            result = core.identify("recover")
        elif args.command == "status":
            from .server import setup_status

            result = setup_status()
        elif args.command == "inbox":
            result = read_json("inbox.json", [])
        elif args.command == "notification-test":
            result = routines.test_notification()
        elif args.command == "retry-notifications":
            result = routines.retry_notifications()
        else:
            result = str(home())
        print(json.dumps(result, indent=2))
    except UserError as e:
        print(str(e), file=sys.stderr)
        raise SystemExit(1) from None
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    except Exception:
        print(
            "Local operation failed. Check configuration and OS vault access; no secrets logged.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
