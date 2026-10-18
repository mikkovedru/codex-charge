import pytest

@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("RECHARGE_AI_TASK_CONFIG_DIR", str(tmp_path / "config"))
