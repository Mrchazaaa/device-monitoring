import logging

from app.logging_config import configure_loki_logging


class FakeLokiHandler(logging.Handler):
    instances = []

    def __init__(self, **kwargs):
        super().__init__()
        self.kwargs = kwargs
        self.__class__.instances.append(self)

    def emit(self, record):
        pass


def test_loki_logging_is_disabled_without_url():
    app_logger = logging.getLogger("app")
    original_level = app_logger.level
    try:
        assert configure_loki_logging(None, {"application": "presence"}, app_log_level="DEBUG") is None
        assert app_logger.level == logging.DEBUG
    finally:
        app_logger.setLevel(original_level)


def test_loki_logging_configures_dependency_and_cleans_up(monkeypatch):
    FakeLokiHandler.instances.clear()
    monkeypatch.setattr("app.logging_config.logging_loki.LokiHandler", FakeLokiHandler)
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    app_logger = logging.getLogger("app")
    original_app_level = app_logger.level

    listener = configure_loki_logging(
        "http://loki:3100/loki/api/v1/push",
        {"application": "presence", "environment": "test"},
        username="user",
        password="secret",
        app_log_level="DEBUG",
    )

    assert listener is not None
    assert FakeLokiHandler.instances[0].kwargs == {
        "url": "http://loki:3100/loki/api/v1/push",
        "tags": {"application": "presence", "environment": "test"},
        "auth": ("user", "secret"),
        "version": "1",
    }
    assert len(root_logger.handlers) == len(original_handlers) + 1
    assert app_logger.level == logging.DEBUG

    listener.stop()

    assert root_logger.handlers == original_handlers
    app_logger.setLevel(original_app_level)
