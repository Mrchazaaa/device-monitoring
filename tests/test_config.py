from app.config import Settings


def test_database_url_takes_precedence(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./data/custom.db")
    monkeypatch.setenv("DATABASE_PATH", "./data/ignored.db")

    settings = Settings.from_env()

    assert settings.database_url == "sqlite:///./data/custom.db"


def test_database_path_is_supported_as_fallback(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_PATH", "./data/legacy.db")

    settings = Settings.from_env()

    assert settings.database_url == "sqlite:///./data/legacy.db"


def test_loki_configuration(monkeypatch):
    monkeypatch.setenv("LOKI_URL", "http://loki:3100/loki/api/v1/push")
    monkeypatch.setenv("LOKI_LABELS", '{"application":"presence","environment":"test"}')
    monkeypatch.setenv("LOKI_USERNAME", "user")
    monkeypatch.setenv("LOKI_PASSWORD", "secret")

    settings = Settings.from_env()

    assert settings.loki_url == "http://loki:3100/loki/api/v1/push"
    assert settings.loki_labels == {"application": "presence", "environment": "test"}
    assert settings.loki_username == "user"
    assert settings.loki_password == "secret"


def test_loki_has_default_application_label(monkeypatch):
    monkeypatch.delenv("LOKI_LABELS", raising=False)

    settings = Settings.from_env()

    assert settings.loki_labels == {"application": "home-wifi-presence"}


def test_app_log_level_defaults_to_debug(monkeypatch):
    monkeypatch.delenv("APP_LOG_LEVEL", raising=False)

    settings = Settings.from_env()

    assert settings.app_log_level == "DEBUG"


def test_app_log_level_is_normalized_and_validated(monkeypatch):
    monkeypatch.setenv("APP_LOG_LEVEL", "debug")
    assert Settings.from_env().app_log_level == "DEBUG"

    monkeypatch.setenv("APP_LOG_LEVEL", "verbose")
    try:
        Settings.from_env()
    except ValueError as exc:
        assert "APP_LOG_LEVEL must be" in str(exc)
    else:
        raise AssertionError("Expected invalid app log level to be rejected")
