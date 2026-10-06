import pytest

@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_CHARGE_CONFIG_DIR", str(tmp_path / "config"))
