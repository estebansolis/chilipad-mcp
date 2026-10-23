"""Private local state, strict Markdown data, and cross-process locking."""

import contextlib
import fcntl
import json
import os
import sys
import tempfile
from pathlib import Path


class UserError(Exception):
    """A safe, actionable error suitable for tool output."""


def home() -> Path:
    override = os.environ.get("CHILIPAD_DATA_DIR")  # non-secret, useful for isolated profiles
    if override:
        p = Path(override).expanduser().resolve()
    elif sys.platform == "darwin":
        p = Path.home() / "Library/Application Support/chilipad-mcp"
    else:
        p = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "chilipad-mcp"
    p.mkdir(parents=True, exist_ok=True, mode=0o700)
    p.chmod(0o700)
    return p


@contextlib.contextmanager
def lock(name="state"):
    p = home() / f".{name}.lock"
    fd = os.open(p, os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(fd, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield


def write(name, data):
    p = home() / name
    fd, tmp = tempfile.mkstemp(dir=p.parent)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read_json(name, default):
    p = home() / name
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text())
    except (ValueError, OSError):
        raise UserError(f"Invalid local {name}; repair it before continuing.") from None


def save_json(name, value):
    write(name, json.dumps(value, indent=2) + "\n")


def read_md(name):
    p = home() / name
    if not p.exists():
        return []
    text = p.read_text()
    # One fenced JSON object. Prose is ignored; it cannot execute code.
    if text.count("```json\n") != 1:
        raise UserError(f"{name}: expected one JSON data block.")
    try:
        block = text.split("```json\n", 1)[1].split("\n```", 1)[0]
        data = json.loads(block)
        if set(data) != {"schema_version", "items"} or data["schema_version"] != 1:
            raise ValueError()
        if not isinstance(data["items"], list):
            raise ValueError()
        return data["items"]
    except (ValueError, KeyError, TypeError):
        raise UserError(f"{name}: invalid schema version 1 data.") from None


def save_md(name, items):
    data = {"schema_version": 1, "items": items}
    write(name, f"# Chilipad {name[:-3]}\n\n```json\n{json.dumps(data, indent=2)}\n```\n")
