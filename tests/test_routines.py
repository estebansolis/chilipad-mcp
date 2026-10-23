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


@pytest.mark.parametrize("operation", ["pause", "delete"])
def test_missing_mapping_does_not_prevent_stopping_routine(operation):
    routines.update(rule(), confirmed=True)
    storage.save_md("devices.md", [])
    assert routines.definitions()[0]["id"] == "wake"
    if operation == "pause":
        routines.update(rule(enabled=False), confirmed=True)
        assert routines.definitions()[0]["enabled"] is False
    else:
        routines.update(delete_id="wake", confirmed=True)
        assert routines.definitions() == []


@pytest.mark.parametrize("change", ["disabled", "deleted", "temperature"])
def test_claimed_occurrence_does_not_adopt_later_rule(change, monkeypatch):
    original = rule()
    routines.update(original, confirmed=True)
    if change == "deleted":
        routines.update(delete_id="wake", confirmed=True)
    elif change == "disabled":
        routines.update(rule(enabled=False), confirmed=True)
    else:
        routines.update(rule(temperature=80), confirmed=True)
    monkeypatch.setattr(core, "change", lambda *a, **k: pytest.fail("must not write changed rule"))
    assert (
        routines.prepare("wake", automatic=True, expected=original)["outcome"]
        == "skipped_definition_changed"
    )


def test_slow_earlier_routine_cannot_make_wake_fire_late(monkeypatch):
    routines.update(rule(id="first"), confirmed=True)
    routines.update(rule(id="second"), confirmed=True)
    at = dt.datetime(2026, 10, 23, 13, 30, 15, tzinfo=dt.UTC)
    clock = [at]
    calls = []

    def slow(*args, **kwargs):
        calls.append(args[0])
        clock[0] += dt.timedelta(seconds=60)
        return {"outcome": "request_accepted"}

    monkeypatch.setattr(routines, "prepare", slow)
    routines.tick(at, clock=lambda: clock[0])
    assert calls == ["first"]
    assert storage.read_json("history.json", {})["second:2026-10-23"]["outcome"] == "missed"


def test_first_start_uses_routine_local_date(monkeypatch):
    routines.update(rule(action="water_check", time="18:00"), confirmed=True)
    # 10am in Los Angeles, with yesterday's 6pm after the current UTC midnight.
    at = dt.datetime(2026, 10, 23, 17, 0, tzinfo=dt.UTC)
    monkeypatch.setattr(
        core, "water", lambda *a: pytest.fail("must not run yesterday on first start")
    )
    routines.tick(at)
    assert storage.read_json("history.json", {}) == {}


def test_failed_water_notification_keeps_observation_for_retry(monkeypatch):
    routines.update(rule(action="water_check"), confirmed=True)
    observation = {"target": "my side", "condition": "refill_needed"}
    monkeypatch.setattr(core, "water", lambda _: observation)

    def fail(_):
        raise OSError("notification storage unavailable")

    monkeypatch.setattr(routines, "notify", fail)
    routines.tick(dt.datetime(2026, 10, 23, 13, 30, 15, tzinfo=dt.UTC))
    result = storage.read_json("history.json", {})["wake:2026-10-23"]
    assert result["outcome"] == observation
    assert result["notification"] == "failed_retry_with_retry-notifications"
