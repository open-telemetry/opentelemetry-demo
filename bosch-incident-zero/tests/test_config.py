from pathlib import Path
import pytest
from src.config import Settings, load_env_file


def test_load_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("KILL_SWITCH_ENABLED=true\nLOG_LEVEL=DEBUG\n# Comment\n", encoding="utf-8")

    parsed = load_env_file(env_file)
    assert parsed["KILL_SWITCH_ENABLED"] == "true"
    assert parsed["LOG_LEVEL"] == "DEBUG"


def test_default_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("KILL_SWITCH_ENABLED", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    settings = Settings(root_dir=tmp_path)
    assert settings.kill_switch_enabled is False
    assert settings.log_level == "INFO"
    assert settings.require_human_approval is True
    assert settings.dry_run_mode is True
    assert "localhost:16686" in settings.jaeger_url
    assert "localhost:9090" in settings.prometheus_url
    assert "localhost:9200" in settings.opensearch_url


def test_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KILL_SWITCH_ENABLED", "true")
    monkeypatch.setenv("LOG_LEVEL", "ERROR")

    settings = Settings(root_dir=tmp_path)
    assert settings.kill_switch_enabled is True
    assert settings.log_level == "ERROR"
