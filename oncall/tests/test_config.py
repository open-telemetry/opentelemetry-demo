import pytest

from oncall.config import Settings, load_settings


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in Settings.__dataclass_fields__:
        monkeypatch.delenv(name, raising=False)


def test_defaults_when_no_env(tmp_path):
    settings = load_settings(tmp_path / "missing.env")
    assert settings.MAX_STEPS == 12
    assert settings.CONFIDENCE_MIN == 0.7
    assert settings.DRY_RUN is True
    assert settings.compose_files == ["compose.yaml", "compose.observability.yaml"]


def test_env_file_and_process_env(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("MAX_STEPS=5\nDRY_RUN=false\nPROM_URL=http://file:9090\n")
    monkeypatch.setenv("PROM_URL", "http://env:9090")
    settings = load_settings(env_file)
    assert settings.MAX_STEPS == 5
    assert settings.DRY_RUN is False
    assert settings.PROM_URL == "http://env:9090"


def test_empty_value_keeps_default(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("MAX_STEPS=\n")
    assert load_settings(env_file).MAX_STEPS == 12


def test_bad_bool_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("DRY_RUN", "maybe")
    with pytest.raises(ValueError):
        load_settings(tmp_path / "missing.env")
