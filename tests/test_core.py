import copy
import pytest
from chilipad_mcp import api, core, storage, credentials, cli


@pytest.fixture
def device_api(monkeypatch):
    states = {
        key: {
            "about": {"model": "Dock Pro"},
            "control": {
                "set_temperature_f": 72,
                "thermal_control_status": "standby",
                "display_temperature_unit": "f",
            },
            "status": {"is_connected": True, "is_water_low": False},
        }
        for key in ("fixture-a", "fixture-b")
    }
    patches = []

    def req(method, path, **kw):
        if path == "/devices":
            return [{"id": k, "name": k} for k in states]
        key = path.rsplit("/", 1)[-1]
        if method == "PATCH":
            patches.append((key, kw["body"].copy()))
            states[key]["control"].update(kw["body"])
            return {}
        return copy.deepcopy(states[key])

    monkeypatch.setattr(api, "request", req)
    return states, patches


def test_minimal_writes_and_alias(device_api):
    states, patches = device_api
    core.set_temperature("my side", 70, "F")
    core.set_power("my side", True)
    core.settings("my side", display_unit="c")
    assert patches == [
        ("fixture-a", {"set_temperature_f": 70}),
        ("fixture-a", {"thermal_control_status": "active"}),
        ("fixture-a", {"display_temperature_unit": "c"}),
    ]
    assert states["fixture-b"]["control"]["set_temperature_f"] == 72


def test_maximum_requires_named_mode(device_api):
    with pytest.raises(storage.UserError):
        core.set_temperature("my side", -1, "F")
    core.set_temperature("my side", mode="maximum_cooling")
    assert device_api[1][-1][1] == {"set_temperature_f": -1}


def test_unsupported_or_offline_no_write(device_api):
    states, patches = device_api
    states["fixture-a"]["about"]["model"] = "Sleep Tracker"
    with pytest.raises(storage.UserError, match="Dock Pro"):
        core.set_power("my side", True)
    states["fixture-a"]["about"]["model"] = "Dock Pro"
    states["fixture-a"]["status"]["is_connected"] = None
    with pytest.raises(storage.UserError, match="connectivity"):
        core.set_power("my side", True)
    assert not patches


def test_unknown_water_is_not_fine(device_api):
    device_api[0]["fixture-a"]["status"]["is_water_low"] = None
    assert core.water("my side")["condition"] == "unknown"


def test_mapping_confirmed_and_no_duplicate(device_api):
    with pytest.raises(storage.UserError):
        core.save_mapping([{"id": "fixture-a", "alias": "a"}])
    with pytest.raises(storage.UserError):
        core.save_mapping(
            [{"id": "fixture-a", "alias": "a"}, {"id": "fixture-b", "alias": "A"}], True
        )
    core.save_mapping([{"id": "fixture-a", "alias": "my side"}], True)
    assert core.resolve("MY SIDE") == "fixture-a"
    with pytest.raises(storage.UserError):
        core.resolve("both")


def identification_spec():
    return [
        {"id": "fixture-a", "value": 68, "unit": "F"},
        {"id": "fixture-b", "value": 76, "unit": "F"},
    ]


def test_identification_snapshots_restores(device_api):
    core.identify("begin", identification_spec(), True)
    rec = storage.read_json("recovery.json", None)
    assert rec["devices"]["fixture-a"]["original"]["set_temperature_f"] == 72
    with pytest.raises(storage.UserError, match="identification"):
        core.set_power("my side", True)
    assert not core.identify("finish")["recovery_pending"]
    assert device_api[0]["fixture-a"]["control"]["set_temperature_f"] == 72


def test_identification_manual_change_preserved(device_api):
    core.identify("begin", identification_spec(), True)
    device_api[0]["fixture-a"]["control"]["set_temperature_f"] = 71
    assert core.identify("recover")["recovery_pending"]
    assert device_api[0]["fixture-a"]["control"]["set_temperature_f"] == 71
    assert not core.identify("recover", force=True, confirmed=True)["recovery_pending"]


def test_failed_second_identification_restores_first(device_api, monkeypatch):
    real = api.request

    def req(method, path, **kw):
        if (
            method == "PATCH"
            and path.endswith("fixture-b")
            and kw["body"].get("set_temperature_f") == 76
        ):
            raise storage.UserError("network failure")
        return real(method, path, **kw)

    monkeypatch.setattr(api, "request", req)
    result = core.identify("begin", identification_spec(), True)
    assert "restoration" in result
    assert device_api[0]["fixture-a"]["control"]["set_temperature_f"] == 72


def test_explicit_command_suppresses_scheduler(device_api):
    core.set_temperature("my side", 70, "F")
    result = core.change("my side", {"set_temperature_f": 75}, automatic=True)
    assert result["outcome"] == "suppressed"
    assert len(device_api[1]) == 1


def test_external_change_suppresses_scheduler(device_api):
    core.change("my side", {"set_temperature_f": 70}, automatic=True)
    device_api[0]["fixture-a"]["control"]["set_temperature_f"] = 73
    result = core.change("my side", {"set_temperature_f": 75}, automatic=True)
    assert result["outcome"] == "external_change_detected_automation_suppressed"
    assert len(device_api[1]) == 1


def test_vault_does_not_use_global_fallback(monkeypatch):
    import keyring
    import sys
    from unittest.mock import Mock

    monkeypatch.setattr(keyring, "get_keyring", lambda: pytest.fail("must not autodetect"))
    if sys.platform == "darwin":
        from keyring.backends import macOS as module
    else:
        from keyring.backends import SecretService as module
    fake = Mock(priority=1)
    monkeypatch.setattr(module, "Keyring", lambda: fake)
    assert credentials.backend() is fake


def test_failed_candidate_never_replaces_token(monkeypatch):
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(credentials, "backend", lambda: object())
    monkeypatch.setattr(cli.getpass, "getpass", lambda _: "fake-test-secret")
    monkeypatch.setattr(
        credentials, "store", lambda _: pytest.fail("must not replace existing token")
    )

    def reject(*a, **k):
        raise storage.UserError("Token invalid")

    monkeypatch.setattr(api, "request", reject)
    with pytest.raises(storage.UserError):
        cli.capture_token()


@pytest.mark.parametrize("count", [0, 1, 2, 3])
def test_discovery_branches(monkeypatch, count):
    monkeypatch.setattr(
        api,
        "request",
        lambda *a, **k: [{"id": f"synthetic-{n}", "name": "synthetic"} for n in range(count)],
    )
    result = core.list_devices()
    assert len(result["devices"]) == count
    expected = ["No claimed", "Offer a label", "two-device", "Select a bed"]
    assert expected[count] in result["guidance"]


def test_resume_clears_external_change_baseline(device_api):
    from chilipad_mcp.server import resume_automation

    core.change("my side", {"set_temperature_f": 70}, automatic=True)
    device_api[0]["fixture-a"]["control"]["set_temperature_f"] = 73
    core.change("my side", {"set_temperature_f": 75}, automatic=True)
    resume_automation("my side", confirmed=True)
    assert (
        core.change("my side", {"set_temperature_f": 75}, automatic=True)["outcome"]
        == "request_accepted"
    )


def test_read_discovered_status_without_premature_mapping(device_api):
    storage.save_md("devices.md", [])
    result = core.status(device_id="fixture-a")
    assert result["about"]["model"] == "Dock Pro"
    assert storage.read_md("devices.md") == []
    assert device_api[1] == []
    with pytest.raises(storage.UserError, match="discovery"):
        core.status(device_id="not-claimed")
    with pytest.raises(storage.UserError, match="exactly one"):
        core.status(target="my side", device_id="fixture-a")


def test_recovery_preserves_manual_power_change(device_api):
    core.identify("begin", identification_spec(), True)
    device_api[0]["fixture-a"]["control"]["thermal_control_status"] = "active"
    result = core.identify("recover")
    assert result["recovery_pending"]
    assert device_api[0]["fixture-a"]["control"]["thermal_control_status"] == "active"
    assert device_api[0]["fixture-a"]["control"]["set_temperature_f"] == 68
    assert "fixture-a" in storage.read_json("recovery.json", {})["devices"]


def test_automation_retains_power_expectation_after_temperature_only_write(device_api):
    core.change(
        "my side", {"set_temperature_f": 70, "thermal_control_status": "active"}, automatic=True
    )
    core.change("my side", {"set_temperature_f": 71}, automatic=True)
    device_api[0]["fixture-a"]["control"]["thermal_control_status"] = "standby"
    result = core.change("my side", {"set_temperature_f": 75}, automatic=True)
    assert result["outcome"] == "external_change_detected_automation_suppressed"
    assert len(device_api[1]) == 2


def test_automatic_write_checks_deadline_after_status_read(device_api, monkeypatch):
    import datetime as dt

    start = dt.datetime(2026, 10, 23, 13, 30, 55, tzinfo=dt.UTC)
    clock = [start]
    real = api.dock_status

    def slow_status(device_id):
        clock[0] += dt.timedelta(seconds=10)
        return real(device_id)

    monkeypatch.setattr(api, "dock_status", slow_status)
    result = core.change(
        "my side",
        {"set_temperature_f": 75},
        automatic=True,
        deadline=start + dt.timedelta(seconds=5),
        clock=lambda: clock[0],
    )
    assert result["outcome"] == "missed"
    assert device_api[1] == []


def test_token_entry_refuses_visible_input_fallback(monkeypatch):
    import warnings

    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(credentials, "backend", lambda: object())
    monkeypatch.setattr(credentials, "store", lambda _: pytest.fail("must not save"))

    def fallback(_):
        warnings.warn("Cannot control echo", cli.getpass.GetPassWarning)
        pytest.fail("must stop before visible fallback reads a token")

    monkeypatch.setattr(cli.getpass, "getpass", fallback)
    with pytest.raises(storage.UserError, match="Hidden input"):
        cli.capture_token()
