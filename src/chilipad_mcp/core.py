"""Shared application operations used by MCP, CLI, and runner."""

import datetime as dt

from . import api
from .storage import UserError, lock, read_json, read_md, save_json, save_md


def now():
    return dt.datetime.now(dt.UTC)


def mappings():
    rows = read_md("devices.md")
    aliases, ids = set(), set()
    for row in rows:
        if not isinstance(row, dict) or set(row) - {
            "id",
            "alias",
            "group",
            "position",
            "confirmed_at",
        }:
            raise UserError("Invalid mapping fields.")
        if not isinstance(row.get("alias"), str) or not row["alias"].strip():
            raise UserError("Every device needs an alias.")
        api.device_path(row.get("id"))
        alias = row["alias"].casefold()
        if alias in aliases or row["id"] in ids:
            raise UserError("Duplicate alias or device ID.")
        aliases.add(alias)
        ids.add(row["id"])
    return rows


def resolve(target):
    if not isinstance(target, str):
        raise UserError("Specify a confirmed device alias.")
    matches = [r["id"] for r in mappings() if r["alias"].casefold() == target.casefold()]
    if len(matches) != 1:
        raise UserError("Unknown or ambiguous alias; discover and confirm the mapping first.")
    return matches[0]


def list_devices():
    raw = api.request("GET", "/devices")
    if not isinstance(raw, list):
        raise UserError("Unexpected discovery response; expected a list.")
    names = {r["id"]: r["alias"] for r in mappings()}
    devices = [{k: r[k] for k in ("id", "name", "attachments") if k in r} for r in raw]
    for row in devices:
        row["alias"] = names.get(row.get("id"))
    return {
        "devices": devices,
        "guidance": (
            "No claimed devices; check Sleepme account linking."
            if not devices
            else "Offer a label and confirm it."
            if len(devices) == 1
            else "Offer an explicit two-device identification test."
            if len(devices) == 2
            else "Select a bed/group before identification."
        ),
        "capabilities": "Read status to verify model and available fields; list order is not bed side.",
    }


def save_mapping(rows: list[dict], confirmed: bool = False):
    if confirmed is not True:
        raise UserError("Read the mapping back and obtain user confirmation before saving.")
    with lock("actions"):
        devices = api.request("GET", "/devices")
        ids = {r["id"] for r in devices}
        old = read_md("devices.md")
        # Validate without writing untrusted rows to the canonical file.
        aliases, seen = set(), set()
        for r in rows:
            if not isinstance(r, dict) or set(r) - {
                "id",
                "alias",
                "group",
                "position",
                "confirmed_at",
            }:
                raise UserError("Invalid mapping fields.")
            if (
                r.get("id") not in ids
                or not isinstance(r.get("alias"), str)
                or not r["alias"].strip()
            ):
                raise UserError("Each mapping needs a claimed device ID and a nonempty alias.")
            if r["alias"].casefold() in aliases or r["id"] in seen:
                raise UserError("Duplicate alias or device ID.")
            aliases.add(r["alias"].casefold())
            seen.add(r["id"])
        # An empty list is an intentional confirmed removal.
        for r in rows:
            r["confirmed_at"] = now().isoformat()
        save_md("devices.md", rows)
        if old != rows:
            return {"saved": True, "devices": rows}
        return {"saved": True}


def status(target: str):
    return api.observed(api.request("GET", api.device_path(resolve(target))))


def water(target: str):
    s = status(target)
    raw = s.get("status") or {}
    flag = raw.get("is_water_low")
    connected = raw.get("is_connected")
    return {
        "target": target,
        "observed_at": s["observed_at"],
        "condition": "unknown"
        if connected is not True or not isinstance(flag, bool)
        else "refill_needed"
        if flag
        else "not_low",
        "is_water_low": flag,
        "water_level_raw": raw.get("water_level"),
        "note": "Raw water level has no documented unit; this does not detect cleaning or water quality.",
    }


def suppress(device_id):
    state = read_json("overrides.json", {})
    state[device_id] = (now() + dt.timedelta(hours=12)).isoformat()
    save_json("overrides.json", state)


def change(target, body, automatic=False):
    api.validate_patch(body)
    with lock("actions"):
        device_id = resolve(target)
        recovery = read_json("recovery.json", None)
        if recovery and device_id in recovery.get("devices", {}):
            raise UserError("Finish or recover the identification session before other writes.")
        overrides = read_json("overrides.json", {})
        until = overrides.get(device_id)
        if automatic and until and now() < dt.datetime.fromisoformat(until):
            return {"target": target, "outcome": "suppressed", "until": until}
        observed = api.dock_status(device_id)
        auto_state = read_json("automation-state.json", {})
        prior = auto_state.get(device_id)
        if (
            automatic
            and prior
            and any((observed.get("control") or {}).get(k) != v for k, v in prior.items())
        ):
            suppress(device_id)
            return {"target": target, "outcome": "external_change_detected_automation_suppressed"}
        # Suppress scheduled writes even if this request times out ambiguously.
        if not automatic:
            suppress(device_id)
        api.request("PATCH", api.device_path(device_id), body=body)
        if automatic:
            auto_state[device_id] = body
        else:
            auto_state.pop(device_id, None)
        save_json("automation-state.json", auto_state)
        return {
            "target": target,
            "outcome": "request_accepted",
            "requested": body,
            "note": "Acceptance does not establish observed target or physical temperature.",
        }


def set_temperature(
    target: str, value: float | None = None, unit: str | None = None, mode: str | None = None
):
    if mode:
        if (
            value is not None
            or unit is not None
            or mode not in ("maximum_cooling", "maximum_heating")
        ):
            raise UserError("Use an explicit named maximum mode without a numeric temperature.")
        body = {"set_temperature_f": -1 if mode == "maximum_cooling" else 999}
    else:
        body = api.temperature(value, unit)
    return change(target, body)


def set_power(target: str, on: bool):
    if type(on) is not bool:
        raise UserError("Power on must be a boolean.")
    return change(target, {"thermal_control_status": "active" if on else "standby"})


def settings(target: str, display_unit: str | None = None, time_zone: str | None = None):
    body = {}
    if display_unit is not None:
        body["display_temperature_unit"] = display_unit
    if time_zone is not None:
        body["time_zone"] = time_zone
    return change(target, body)


def reports(start_date: str | None = None, days_back: int = 0, time_zone: str = "UTC"):
    api.timezone(time_zone)
    if type(days_back) is not int or not 0 <= days_back <= 6:
        raise UserError("days_back must be an integer 0–6.")
    params = {"days_back": days_back, "time_zone": time_zone}
    if start_date is not None:
        try:
            if dt.date.fromisoformat(start_date).isoformat() != start_date:
                raise ValueError()
        except (ValueError, TypeError):
            raise UserError(
                "start_date must be YYYY-MM-DD; omit it instead of sending blank."
            ) from None
        params["start_date"] = start_date
    return {
        "query": params,
        "data": api.request("GET", "/sleep-reports/", params=params),
        "note": "Account-scoped provider reports; interval direction needs live verification. "
        "Nullable metrics are preserved. No side association or medical interpretation.",
    }


def identify(
    action: str,
    tests: list[dict] | None = None,
    confirmed: bool = False,
    keep: bool = False,
    force: bool = False,
):
    """Recoverable two-controller test. tests: [{id, value, unit, on?: bool}]."""
    with lock("actions"):
        rec = read_json("recovery.json", None)
        if action == "begin":
            if rec:
                raise UserError("An identification session already needs completion or recovery.")
            if confirmed is not True or not isinstance(tests, list) or len(tests) != 2:
                raise UserError(
                    "Agree two distinct comfortable test temperatures and device IDs first."
                )
            if tests[0].get("id") == tests[1].get("id"):
                raise UserError("Select two different controllers.")
            claimed = {r["id"] for r in api.request("GET", "/devices")}
            snapshots = {}
            values = []
            for t in tests:
                if set(t) - {"id", "value", "unit", "on"} or t.get("id") not in claimed:
                    raise UserError("Unknown test device or field.")
                patch = api.temperature(t.get("value"), t.get("unit"))
                values.append(t["value"] if t["unit"] == "C" else (t["value"] - 32) * 5 / 9)
                if "on" in t:
                    if type(t["on"]) is not bool:
                        raise UserError("on must be a boolean.")
                    patch["thermal_control_status"] = "active" if t["on"] else "standby"
                raw = api.dock_status(t["id"])
                c = raw.get("control") or {}
                original = {k: c[k] for k in ("thermal_control_status",) if k in c}
                unit = str(c.get("display_temperature_unit", "f")).lower()
                temp_key = "set_temperature_c" if unit == "c" else "set_temperature_f"
                if c.get(temp_key) is None or "thermal_control_status" not in original:
                    raise UserError("A reliable original power/target snapshot is required.")
                original[temp_key] = c[temp_key]
                api.validate_patch(original)
                snapshots[t["id"]] = {"original": original, "test": patch, "attempted": False}
            if abs(values[0] - values[1]) < 0.01:
                raise UserError("Test temperatures must be distinct.")
            rec = {"started_at": now().isoformat(), "devices": snapshots}
            save_json("recovery.json", rec)
            outcomes = {}
            for device_id, entry in snapshots.items():
                entry["attempted"] = True
                save_json("recovery.json", rec)  # persist BEFORE possible side effect
                try:
                    api.request("PATCH", api.device_path(device_id), body=entry["test"])
                    outcomes[device_id] = "request_accepted"
                except UserError as e:
                    outcomes[device_id] = str(e)
                    rec["failure"] = True
                    save_json("recovery.json", rec)
                    restored = _restore(rec, False)
                    return {"outcomes": outcomes, "restoration": restored}
            return {
                "outcomes": outcomes,
                "next": "Ask user to identify sides; confirm mapping, then finish. "
                "Target changes can precede physical temperature changes.",
            }
        if action == "status":
            return {"recovery": rec}
        if action not in ("finish", "cancel", "recover") or not rec:
            raise UserError("Use begin, status, finish, cancel, or recover with an active session.")
        if action == "finish" and keep:
            if confirmed is not True:
                raise UserError("Keeping test settings needs explicit user agreement.")
            save_json("recovery.json", None)
            return {"kept_test_settings": True}
        if force and confirmed is not True:
            raise UserError("Overwriting possible manual changes needs fresh user agreement.")
        return _restore(rec, force)


def _restore(rec, force):
    outcomes = {}
    pending = {}
    for device_id, entry in rec["devices"].items():
        if not entry["attempted"]:
            continue
        try:
            current = api.dock_status(device_id).get("control") or {}
            if all(current.get(k) == v for k, v in entry["original"].items()):
                outcomes[device_id] = "original_state_observed"
                continue
            if not force and any(current.get(k) != v for k, v in entry["test"].items()):
                raise UserError(
                    "Settings differ from test; obtain permission before overwriting manual changes."
                )
            api.request("PATCH", api.device_path(device_id), body=entry["original"])
            # Keep recovery until a separate read observes the original state.
            observed = api.dock_status(device_id).get("control") or {}
            if not all(observed.get(k) == v for k, v in entry["original"].items()):
                raise UserError(
                    "Restoration accepted but original state not yet observed; retry recovery later."
                )
            outcomes[device_id] = "original_state_observed"
        except UserError as e:
            outcomes[device_id] = str(e)
            pending[device_id] = entry
    rec["devices"] = pending
    save_json("recovery.json", rec if pending else None)
    return {"outcomes": outcomes, "recovery_pending": bool(pending)}
