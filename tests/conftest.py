import pytest
from chilipad_mcp import storage


@pytest.fixture(autouse=True)
def profile(tmp_path, monkeypatch):
    monkeypatch.setenv("CHILIPAD_DATA_DIR", str(tmp_path / "profile"))
    storage.save_md(
        "devices.md",
        [{"id": "fixture-a", "alias": "my side"}, {"id": "fixture-b", "alias": "partner side"}],
    )
    storage.save_json("notification-test.json", {"channel": "inbox"})
