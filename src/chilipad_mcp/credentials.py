"""Explicit vault backends only; never allow a plaintext fallback."""

import sys

from .storage import UserError

SERVICE = "sleepme-mcp"
ACCOUNT = "api-token"


def backend():
    try:
        if sys.platform == "darwin":
            from keyring.backends.macOS import Keyring
        elif sys.platform.startswith("linux"):
            from keyring.backends.SecretService import Keyring
        else:
            raise UserError("Only macOS and Linux desktop sessions are supported.")
        k = Keyring()
        if k.priority <= 0:
            raise ValueError()
        return k
    except Exception:
        raise UserError(
            "OS vault unavailable. Unlock macOS Keychain or a Linux Secret Service "
            "collection and session D-Bus. No plaintext fallback is supported."
        ) from None


def token():
    try:
        value = backend().get_password(SERVICE, ACCOUNT)
        if not value:
            raise UserError("No token saved. Run chilipad-mcp setup in your local terminal.")
        return value
    except UserError:
        raise
    except Exception:
        raise UserError("Credential vault is locked or inaccessible; unlock it locally.") from None


def store(value):
    try:
        backend().set_password(SERVICE, ACCOUNT, value)
    except Exception:
        raise UserError(
            "Could not save token in OS vault. No plaintext copy was written."
        ) from None


def delete():
    try:
        backend().delete_password(SERVICE, ACCOUNT)
    except Exception:
        raise UserError("Could not remove credential; check the OS vault locally.") from None
