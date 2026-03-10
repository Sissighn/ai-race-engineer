from src.config.settings import Settings


def test_settings_paths_exist():
    assert Settings.PROJECT_ROOT.exists()
    assert Settings.DATA_DIR.exists()
    assert Settings.CACHE_DIR.exists()
    assert Settings.LOGS_DIR.exists()


def test_get_setting_reads_env(monkeypatch):
    monkeypatch.setenv("MY_CUSTOM_SETTING", "123")
    assert Settings.get_setting("MY_CUSTOM_SETTING") == "123"
    assert Settings.get_setting("DOES_NOT_EXIST", "fallback") == "fallback"


def test_environment_helpers(monkeypatch):
    monkeypatch.setattr(Settings, "ENVIRONMENT", "production")
    assert Settings.is_production() is True
    assert Settings.is_development() is False

    monkeypatch.setattr(Settings, "ENVIRONMENT", "development")
    assert Settings.is_production() is False
    assert Settings.is_development() is True
