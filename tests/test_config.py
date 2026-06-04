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
