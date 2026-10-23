import datetime as dt
import httpx
import pytest
from chilipad_mcp import api, core, storage


@pytest.mark.parametrize("value,unit", [(55, "F"), (115, "F"), (13, "C"), (48, "C"), (20.5, "C")])
def test_temperature_boundaries(value, unit):
    assert list(api.temperature(value, unit).values()) == [value]


@pytest.mark.parametrize(
    "value,unit",
    [
        (54, "F"),
        (116, "F"),
        (70.5, "F"),
        (12.5, "C"),
        (48.5, "C"),
        (20.1, "C"),
        (True, "F"),
        (-1, "F"),
        (999, "C"),
        (float("nan"), "C"),
        (float("inf"), "F"),
    ],
)
def test_temperature_invalid(value, unit):
    with pytest.raises(storage.UserError):
        api.temperature(value, unit)


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"evil": 1},
        {"set_temperature_f": 70, "set_temperature_c": 20},
        {"thermal_control_status": "on"},
        {"display_temperature_unit": "F"},
        {"time_zone": "Mars/Olympus"},
    ],
)
def test_patch_rejected(body):
    with pytest.raises(storage.UserError):
        api.validate_patch(body)


def test_payload_is_top_level_and_secret_redacted(monkeypatch):
    monkeypatch.setattr(api.credentials, "token", lambda: "fake-test-secret")
    seen = []

    def respond(req):
        seen.append(req)
        return httpx.Response(401, text="fake-test-secret Authorization: Bearer fake-test-secret")

    with pytest.raises(storage.UserError) as e:
        api.request(
            "PATCH",
            "/devices/fixture-a",
            body={"set_temperature_f": 70},
            transport=httpx.MockTransport(respond),
        )
    assert "fake-test-secret" not in str(e.value)
    assert seen[0].content == b'{"set_temperature_f":70}'
    assert seen[0].headers["content-type"] == "application/json"


def test_ambiguous_write_not_retried(monkeypatch):
    monkeypatch.setattr(api.credentials, "token", lambda: "fake-test-secret")
    calls = []

    def respond(req):
        calls.append(req)
        raise httpx.ReadTimeout("fake-test-secret")

    with pytest.raises(storage.UserError, match="outcome may be unknown"):
        api.request(
            "PATCH",
            "/devices/fixture-a",
            body={"thermal_control_status": "active"},
            transport=httpx.MockTransport(respond),
        )
    assert len(calls) == 1


def test_limiter_shared_budget():
    for _ in range(10):
        api.reserve()
    with pytest.raises(storage.UserError, match="budget exhausted"):
        api.reserve()


def test_429_write_not_retried_and_shared_block(monkeypatch):
    monkeypatch.setattr(api.credentials, "token", lambda: "fake-test-secret")
    calls = []

    def respond(req):
        calls.append(req)
        return httpx.Response(429, headers={"Retry-After": "60"})

    with pytest.raises(storage.UserError, match="rate limit"):
        api.request(
            "PATCH",
            "/devices/fixture-a",
            body={"set_temperature_f": 70},
            transport=httpx.MockTransport(respond),
        )
    assert len(calls) == 1
    with pytest.raises(storage.UserError, match="budget exhausted"):
        api.reserve()


@pytest.mark.parametrize("days", [0, 6])
def test_report_nullable_data_and_params(monkeypatch, days):
    seen = []

    def req(method, path, **kw):
        seen.append((method, path, kw))
        return {"reports": [{"date": "2026-10-22", "sleep_score_percent": None, "sessions": []}]}

    monkeypatch.setattr(api, "request", req)
    result = core.reports(days_back=days, time_zone="America/Los_Angeles")
    assert "start_date" not in result["query"]
    assert result["data"]["reports"][0]["sleep_score_percent"] is None
    assert seen[0][1] == "/sleep-reports/"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"days_back": -1},
        {"days_back": 7},
        {"days_back": True},
        {"start_date": ""},
        {"start_date": "2026-02-30"},
        {"time_zone": "invalid"},
    ],
)
def test_invalid_reports_never_transmitted(monkeypatch, kwargs):
    monkeypatch.setattr(api, "request", lambda *a, **k: pytest.fail("must validate first"))
    with pytest.raises(storage.UserError):
        core.reports(**kwargs)


def test_status_redacts_identity():
    r = api.observed(
        {
            "about": {"model": "Dock Pro", "serial_number": "private", "ip_address": "private"},
            "status": {"water_level": None, "extra_sensor": 4},
        }
    )
    assert r["about"] == {"model": "Dock Pro"}
    assert r["status"]["extra_sensor"] == 4
    dt.datetime.fromisoformat(r["observed_at"])


def test_fixture_reports_round_trip(monkeypatch):
    import json
    from pathlib import Path

    data = json.loads((Path(__file__).parent / "fixtures/synthetic-reports.json").read_text())
    monkeypatch.setattr(api, "request", lambda *a, **k: data)
    result = core.reports(start_date="2026-10-22", days_back=6)
    assert result["data"] == data
    assert result["query"]["start_date"] == "2026-10-22"
    assert (
        result["data"]["reports"][0]["sessions"][0]["hypnogram"]["segments"][0]["stage"]
        == "NO_DATA"
    )
