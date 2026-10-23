"""Strict Markdown schedules and an at-most-once local runner."""

import datetime as dt
import fcntl
import os
import re
import time
from zoneinfo import ZoneInfo

from . import api, core
from .storage import UserError, home, lock, read_json, read_md, save_json, save_md

FIELDS = {
    "id",
    "enabled",
    "target",
    "action",
    "time",
    "timezone",
    "weekdays",
    "date",
    "temperature",
    "unit",
    "on",
    "window_minutes",
    "notification",
    "reminder_hours",
    "overrides",
}


def validate(row):
    if not isinstance(row, dict) or set(row) - FIELDS:
        raise UserError("Unsupported routine fields.")
    if not isinstance(row.get("id"), str) or not re.fullmatch(r"[a-z0-9-]{1,64}", row["id"]):
        raise UserError("Routine ID must use 1–64 lowercase letters, digits, or hyphens.")
    if type(row.get("enabled")) is not bool:
        raise UserError("Routine enabled must be a boolean.")
    if row.get("action") not in ("prepare_bed", "wake_temperature", "water_check", "reminder"):
        raise UserError("Unsupported action; no audible alarm or automatic cleaning is available.")
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", row.get("time", "")):
        raise UserError("Routine time must be HH:MM.")
    api.timezone(row.get("timezone"))
    if row.get("notification") != "inbox":
        raise UserError("Only the local inbox notification channel is implemented.")
    if "date" in row:
        try:
            if dt.date.fromisoformat(row["date"]).isoformat() != row["date"]:
                raise ValueError()
        except (TypeError, ValueError):
            raise UserError("One-time date must be YYYY-MM-DD.") from None
    else:
        days = row.get("weekdays")
        if (
            not isinstance(days, list)
            or not days
            or any(type(d) is not int or d not in range(7) for d in days)
        ):
            raise UserError("Specify weekdays 0–6 (Monday–Sunday), or an explicit one-time date.")
    window = row.get("window_minutes", 0)
    if type(window) is not int or not 0 <= window <= 180:
        raise UserError("Catch-up window must be 0–180 minutes.")
    reminder = row.get("reminder_hours", 24)
    if type(reminder) is not int or not 1 <= reminder <= 8760:
        raise UserError("Water reminder interval must be 1–8760 hours.")
    if row["action"] == "wake_temperature" and window:
        raise UserError("Wake routines skip late occurrences; window_minutes must be zero.")
    if row["action"] in ("prepare_bed", "wake_temperature"):
        api.temperature(row.get("temperature"), row.get("unit"))
        if "on" in row and type(row["on"]) is not bool:
            raise UserError("on must be a boolean.")
    overrides = row.get("overrides", {})
    if not isinstance(overrides, dict):
        raise UserError("Overrides must map YYYY-MM-DD to HH:MM or null (skip).")
    for date, value in overrides.items():
        try:
            if dt.date.fromisoformat(date).isoformat() != date:
                raise ValueError()
        except (ValueError, TypeError):
            raise UserError("Override keys must be YYYY-MM-DD.") from None
        if value is not None and (
            not isinstance(value, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value)
        ):
            raise UserError("Override time must be HH:MM or null.")
    if row["enabled"]:
        core.resolve(row.get("target"))
        if read_json("notification-test.json", {}).get("channel") != "inbox":
            raise UserError("Run chilipad-mcp notification-test before enabling schedules.")
    return row


def definitions():
    rows = []
    for file in ("alarms.md", "routines.md"):
        for row in read_md(file):
            validate(row)
            rows.append(row)
    if len({r["id"] for r in rows}) != len(rows):
        raise UserError("Routine IDs must be unique across both Markdown files.")
    return rows


def update(
    row: dict | None = None,
    delete_id: str | None = None,
    alarm: bool = False,
    confirmed: bool = False,
):
    if confirmed is not True:
        raise UserError("Summarize the schedule and obtain user agreement before changing it.")
    if (row is None) == (delete_id is None):
        raise UserError("Supply a routine or a delete_id, not both.")
    with lock():
        all_rows = definitions()
        if row is not None:
            validate(row)
        key = row["id"] if row is not None else delete_id
        # Keep an existing routine in its canonical file, regardless of the caller's default.
        files = {name: read_md(name) for name in ("alarms.md", "routines.md")}
        found = [name for name, rows in files.items() if any(r["id"] == key for r in rows)]
        name = found[0] if found else "alarms.md" if alarm else "routines.md"
        rows = [r for r in files[name] if r["id"] != key]
        if row is not None:
            rows.append(row)
        save_md(name, rows)
        return {
            "saved": True,
            "id": key,
            "active_on": "next runner poll (within 15 seconds)",
            "routine_count": len(all_rows) + (not found) - (row is None),
        }


def prepare(routine_id: str, automatic: bool = False):
    rows = [r for r in definitions() if r["id"] == routine_id]
    if len(rows) != 1 or rows[0]["action"] not in ("prepare_bed", "wake_temperature"):
        raise UserError("Select a saved temperature routine.")
    row = rows[0]
    body = api.temperature(row["temperature"], row["unit"])
    if "on" in row:
        body["thermal_control_status"] = "active" if row["on"] else "standby"
    return core.change(row["target"], body, automatic=automatic)


def notify(message):
    # Local durable inbox, deliberately no shell commands/webhooks from Markdown.
    with lock("inbox"):
        items = read_json("inbox.json", [])
        items.append({"at": core.now().isoformat(), "message": message})
        save_json("inbox.json", items[-1000:])
    return "delivered_to_local_inbox"


def test_notification():
    notify("Chilipad notification test. Inbox works; this is not a push or audible alert.")
    save_json("notification-test.json", {"channel": "inbox", "tested_at": core.now().isoformat()})
    return {"channel": "inbox", "result": "delivered; view with chilipad-mcp inbox"}


def occurrence(row, date):
    if row.get("date"):
        if date.isoformat() != row["date"]:
            return None
    elif date.weekday() not in row["weekdays"]:
        return None
    clock = row.get("overrides", {}).get(date.isoformat(), row["time"])
    if clock is None:
        return None
    hour, minute = map(int, clock.split(":"))
    zone = ZoneInfo(row["timezone"])
    local = dt.datetime.combine(date, dt.time(hour, minute), zone).replace(fold=0)
    utc = local.astimezone(dt.UTC)
    # Nonexistent spring time is reported missed; repeated autumn time uses first fold once.
    exists = utc.astimezone(zone).replace(tzinfo=None) == local.replace(tzinfo=None)
    return utc, exists


def tick(at=None):
    at = at or core.now()
    history = read_json("history.json", {})
    try:
        rows = definitions()
        save_json("last-valid-routines.json", rows)
        save_json("runner-error.json", None)
    except UserError as e:
        save_json("runner-error.json", {"error": str(e), "at": at.isoformat()})
        # Invalid manual edits fail closed. Cached revision is retained for repair, not execution.
        return
    last = read_json("runner-heartbeat.json", {}).get("at")
    start = (
        dt.datetime.fromisoformat(last)
        if last
        else at.replace(hour=0, minute=0, second=0, microsecond=0)
    )
    for row in rows:
        if not row["enabled"]:
            continue
        zone = ZoneInfo(row["timezone"])
        first = start.astimezone(zone).date()
        last_date = at.astimezone(zone).date()
        # Retain at most a month of missed occurrences after long downtime.
        date = max(first, last_date - dt.timedelta(days=31))
        while date <= last_date:
            due = occurrence(row, date)
            key = row["id"] + ":" + date.isoformat()  # edits never rerun an executed local date
            date += dt.timedelta(days=1)
            if due is None or key in history:
                continue
            intended, exists = due
            if intended > at or intended < start:
                continue
            if row["action"] == "water_check":
                # Run only the latest due water check after downtime.
                later = date
                more_recent = False
                while later <= last_date:
                    nxt = occurrence(row, later)
                    if nxt and nxt[0] <= at:
                        more_recent = True
                    later += dt.timedelta(days=1)
                if more_recent:
                    history[key] = {
                        "intended_at": intended.isoformat(),
                        "outcome": "missed_coalesced",
                        "notification": "not_required",
                    }
                    save_json("history.json", history)
                    continue
            age = (at - intended).total_seconds()
            window = row.get("window_minutes", 0) * 60
            can_catch_up = row["action"] == "water_check" or (
                row["action"] == "prepare_bed" and age <= window
            )
            result = {
                "intended_at": intended.isoformat(),
                "claimed_at": at.isoformat(),
                "outcome": "claimed_unknown",
                "notification": "pending",
            }
            history[key] = result
            save_json("history.json", history)  # durable claim BEFORE side effects
            try:
                if not exists or (age >= 60 and not can_catch_up):
                    result["outcome"] = "missed"
                elif row["action"] == "water_check":
                    observation = core.water(row["target"])
                    result["outcome"] = observation
                    state = read_json("water-alerts.json", {})
                    prev = state.get(row["id"], {})
                    condition = observation["condition"]
                    previous_at = dt.datetime.fromisoformat(prev["at"]) if prev else None
                    alert = condition != prev.get("condition") or (
                        condition != "not_low"
                        and previous_at is not None
                        and (at - previous_at).total_seconds()
                        >= row.get("reminder_hours", 24) * 3600
                    )
                    if not alert:
                        result["notification"] = "suppressed_unchanged"
                    else:
                        result["notification"] = notify(
                            {"routine": row["id"], "water": observation}
                        )
                        state[row["id"]] = {"condition": condition, "at": at.isoformat()}
                        save_json("water-alerts.json", state)
                elif row["action"] == "reminder":
                    result["outcome"] = "calendar_reminder_not_sensor_finding"
                else:
                    result["outcome"] = prepare(row["id"], automatic=True)
            except UserError as e:
                result["outcome"] = {"error": str(e)}
            if result["notification"] == "pending":
                try:
                    result["notification"] = notify(
                        {"routine": row["id"], "result": result["outcome"]}
                    )
                except OSError:
                    result["notification"] = "failed_retry_with_retry-notifications"
            save_json("history.json", history)
    save_json("runner-heartbeat.json", {"at": at.isoformat(), "pid": os.getpid()})


def retry_notifications():
    with lock("runner-history"):
        history = read_json("history.json", {})
        for key, result in history.items():
            if result.get("notification") in ("pending", "failed_retry_with_retry-notifications"):
                result["notification"] = notify({"run": key, "result": result["outcome"]})
        save_json("history.json", history)
    return {"retried_notifications_only": True}


def status():
    heartbeat = read_json("runner-heartbeat.json", {})
    at = heartbeat.get("at")
    recent = bool(at and (core.now() - dt.datetime.fromisoformat(at)).total_seconds() < 45)
    return {
        "runner_recently_active": recent,
        "heartbeat": heartbeat,
        "error": read_json("runner-error.json", None),
        "history": read_json("history.json", {}),
        "overrides": read_json("overrides.json", {}),
        "inbox": read_json("inbox.json", []),
        "note": "Explicit commands suppress automatic writes to that controller for 12 hours. "
        "Use resume_automation after user agreement to clear suppression.",
    }


def run():
    fd = os.open(home() / ".runner.lock", os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(fd, "w") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise UserError("A runner already owns this profile.") from None
        while True:
            try:
                with lock("runner-history"):
                    tick()
            except Exception:
                # Never dump exception text: upstream errors could include credentials.
                save_json(
                    "runner-error.json",
                    {
                        "error": "Runner failed; check local configuration/vault.",
                        "at": core.now().isoformat(),
                    },
                )
            time.sleep(15)
