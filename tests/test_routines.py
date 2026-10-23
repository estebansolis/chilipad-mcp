import datetime as dt
from zoneinfo import ZoneInfo
import pytest
from chilipad_mcp import core, routines, storage


def rule(**kw):
    row = {
        "id": "wake",
        "enabled": True,
        "target": "my side",
        "action": "wake_temperature",
        "time": "06:30",
        "timezone": "America/Los_Angeles",
        "weekdays": [0, 1, 2, 3, 4, 5, 6],
        "temperature": 75,
        "unit": "F",
        "notification": "inbox",
    }
    return row | kw


def test_strict_unknown_fields_and_enabled_requires_mapping():
    with pytest.raises(storage.UserError):
        routines.validate(rule(shell="rm -rf /"))
    with pytest.raises(storage.UserError):
        routines.validate(rule(target="unknown"))
    with pytest.raises(storage.UserError):
        routines.validate(rule(window_minutes=5))


def test_invalid_update_keeps_original():
    routines.update(rule(), confirmed=True, alarm=True)
    before = (storage.home() / "alarms.md").read_text()
    with pytest.raises(storage.UserError):
        routines.update(rule(time="25:00"), confirmed=True, alarm=True)
    assert (storage.home() / "alarms.md").read_text() == before


def test_dst_fall_once_and_spring_missing():
    fall = routines.occurrence(rule(time="01:30"), dt.date(2026, 11, 1))
    assert fall[1]
    assert fall[0].astimezone(ZoneInfo("America/Los_Angeles")).fold == 0
    spring = routines.occurrence(rule(time="02:30"), dt.date(2026, 3, 8))
    assert not spring[1]


def test_persisted_claim_prevents_duplicate(monkeypatch):
    routines.update(rule(), confirmed=True)
    calls = []
    monkeypatch.setattr(routines, "prepare", lambda *a, **k: calls.append(a) or {"accepted": True})
    at = dt.datetime(2026, 10, 23, 13, 30, 15, tzinfo=dt.timezone.utc)
    routines.tick(at)
    routines.tick(at + dt.timedelta(seconds=15))
    assert len(calls) == 1
    assert len(storage.read_json("history.json", {})) == 1


def test_alarm_missed_not_fired_on_resume(monkeypatch):
    routines.update(rule(), confirmed=True)
    monkeypatch.setattr(routines, "prepare", lambda *a, **k: pytest.fail("must not fire late"))
    at = dt.datetime(2026, 10, 23, 14, 30, tzinfo=dt.timezone.utc)
    routines.tick(at)
    assert storage.read_json("history.json", {})["wake:2026-10-23"]["outcome"] == "missed"


def test_one_time_override_only_changes_selected_date():
    row = rule(overrides={"2026-10-23": "07:00"})
    first = routines.occurrence(row, dt.date(2026, 10, 23))[0]
    next_ = routines.occurrence(row, dt.date(2026, 10, 24))[0]
    assert first.hour == 14 and first.minute == 0
    assert next_.hour == 13 and next_.minute == 30


def test_notification_retry_does_not_repeat_action(monkeypatch):
    storage.save_json("history.json", {"run": {"outcome": "accepted", "notification": "pending"}})
    monkeypatch.setattr(core, "change", lambda *a, **k: pytest.fail("must not repeat action"))
    routines.retry_notifications()
    assert len(storage.read_json("inbox.json", [])) == 1


def test_invalid_markdown_blocks_execution(monkeypatch):
    routines.update(rule(), confirmed=True)
    storage.write("routines.md", "# arbitrary prose\nrun everything")
    monkeypatch.setattr(routines, "prepare", lambda *a, **k: pytest.fail("must fail closed"))
    routines.tick()
    assert storage.read_json("runner-error.json", None)
