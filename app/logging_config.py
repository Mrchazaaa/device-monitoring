from __future__ import annotations

import logging
import logging.handlers
import queue
from collections.abc import Mapping

import logging_loki


class LokiQueueListener(logging.handlers.QueueListener):
    def __init__(self, log_queue, loki_handler, queue_handler, attached_loggers):
        super().__init__(log_queue, loki_handler, respect_handler_level=True)
        self.queue_handler = queue_handler
        self.attached_loggers = attached_loggers

    def stop(self) -> None:
        for logger in self.attached_loggers:
            logger.removeHandler(self.queue_handler)
        super().stop()


def configure_loki_logging(
    url: str | None,
    labels: Mapping[str, str],
    username: str | None = None,
    password: str | None = None,
    app_log_level: str = "DEBUG",
) -> LokiQueueListener | None:
    logging.getLogger("app").setLevel(app_log_level)

    if not url:
        return None

    auth = (username, password or "") if username is not None else None
    loki_handler = logging_loki.LokiHandler(url=url, tags=dict(labels), auth=auth, version="1")
    loki_handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))

    log_queue: queue.Queue[logging.LogRecord] = queue.Queue()
    queue_handler = logging.handlers.QueueHandler(log_queue)

    attached_loggers = [logging.getLogger()]
    for logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        logger = logging.getLogger(logger_name)
        if not logger.propagate:
            attached_loggers.append(logger)

    for logger in attached_loggers:
        logger.addHandler(queue_handler)

    listener = LokiQueueListener(log_queue, loki_handler, queue_handler, attached_loggers)
    listener.start()
    return listener
