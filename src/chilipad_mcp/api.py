"""Fixed-host HTTPS adapter. No upstream body or exception text reaches the model."""

import datetime as dt
import time
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from . import credentials
from .storage import UserError, lock, read_json, save_json

BASE = "https://api.developer.sleep.me/v1"


def timezone(value):
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        raise UserError("Use a valid IANA timezone, for example America/Los_Angeles.") from None
    return value


def temperature(value, unit):
    if unit not in ("F", "C") or isinstance(value, bool) or not isinstance(value, (int, float)):
        raise UserError("Supply a numeric temperature and unit F or C.")
    if unit == "F" and 55 <= value <= 115 and value == int(value):
        return {"set_temperature_f": int(value)}
    if unit == "C" and 13 <= value <= 48 and value * 2 == int(value * 2):
        return {"set_temperature_c": float(value)}
    raise UserError("F requires an integer 55–115; C requires 13–48 in 0.5 steps. No rounding.")


def validate_patch(body):
    allowed = {
        "set_temperature_f",
        "set_temperature_c",
        "thermal_control_status",
        "display_temperature_unit",
        "time_zone",
    }
    if not body or set(body) - allowed:
        raise UserError("Empty or unsupported device update.")
    if "set_temperature_f" in body and "set_temperature_c" in body:
        raise UserError("Do not send both temperature scales.")
    for key, unit in (("set_temperature_f", "F"), ("set_temperature_c", "C")):
        if key in body and body[key] not in (-1, 999):
            temperature(body[key], unit)
    if "thermal_control_status" in body and body["thermal_control_status"] not in (
        "active",
        "standby",
    ):
        raise UserError("Power must be active or standby.")
    if "display_temperature_unit" in body and body["display_temperature_unit"] not in ("f", "c"):
        raise UserError("Display unit must be f or c.")
    if "time_zone" in body:
        timezone(body["time_zone"])
    return body


def reserve():
    # Same account/profile across clients and runner; other apps still consume upstream quota.
    with lock("budget"):
        now = time.time()
        state = read_json("budget.json", {})
        minute = int(now // 60)
        count = state.get("count", 0) if state.get("minute") == minute else 0
        until = state.get("blocked_until", 0)
        if count >= 10 or now < until:
            raise UserError(
                "Shared API budget exhausted; retry after the next minute or Retry-After."
            )
        save_json("budget.json", {"minute": minute, "count": count + 1, "blocked_until": until})


def request(method, path, *, body=None, params=None, candidate=None, transport=None):
    secret = candidate if candidate is not None else credentials.token()
    if method == "PATCH":
        validate_patch(body)
    for attempt in range(3):
        reserve()
        try:
            with httpx.Client(
                timeout=15, follow_redirects=False, trust_env=False, transport=transport
            ) as client:
                response = client.request(
                    method,
                    BASE + path,
                    params=params,
                    json=body,
                    headers={"Authorization": "Bearer " + secret, "Accept": "application/json"},
                )
        except httpx.HTTPError:
            raise UserError(
                "Network failure; write outcome may be unknown. Read status before "
                "retrying a write. No automatic write retry was attempted."
            ) from None
        if response.status_code == 429:
            try:
                delay = max(2**attempt, float(response.headers.get("Retry-After", 1)))
            except ValueError:
                try:
                    from email.utils import parsedate_to_datetime

                    delay = max(
                        1,
                        parsedate_to_datetime(response.headers["Retry-After"]).timestamp()
                        - time.time(),
                    )
                except Exception:
                    delay = 60
            delay = max(1, min(delay, 86400))
            with lock("budget"):
                state = read_json("budget.json", {})
                state["blocked_until"] = time.time() + delay
                save_json("budget.json", state)
            if method == "GET" and attempt < 2 and delay <= 4:
                time.sleep(delay)
                continue
            raise UserError("Sleepme rate limit reached; Retry-After saved for all local clients.")
        errors = {
            400: "Sleepme rejected the request.",
            401: "Token invalid or revoked; replace it locally.",
            403: "Token cannot access this resource.",
            404: "Device or resource not found; rediscover devices.",
        }
        if not 200 <= response.status_code < 300:
            raise UserError(
                errors.get(response.status_code, "Sleepme service error; try a read later.")
            )
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            raise UserError(
                "Sleepme returned an invalid JSON response; write acceptance is uncertain."
            ) from None
    raise UserError("Retry budget exhausted.")


def device_path(device_id):
    if not isinstance(device_id, str) or not device_id or len(device_id) > 200:
        raise UserError("Invalid device identifier.")
    return "/devices/" + quote(device_id, safe="")


def observed(raw):
    if not isinstance(raw, dict):
        raise UserError("Unexpected device status shape.")
    result = {k: v for k, v in raw.items() if k != "about"}
    about = raw.get("about") or {}
    result["about"] = {k: v for k, v in about.items() if k in ("model", "firmware_version")}
    result["observed_at"] = dt.datetime.now(dt.UTC).isoformat()
    return result


def dock_status(device_id):
    raw = request("GET", device_path(device_id))
    model = str((raw.get("about") or {}).get("model", ""))
    if model.lower().replace(" ", "").replace("_", "").replace("-", "") != "dockpro":
        raise UserError("Writes require a verified Dock Pro model in device status.")
    if (raw.get("status") or {}).get("is_connected") is not True:
        raise UserError("Device connectivity unknown or offline; no write sent.")
    return raw
