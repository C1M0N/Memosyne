"""Database Log Handler for the Reanimator TUI."""

from __future__ import annotations

import logging
from pathlib import Path

from ...shared.infrastructure.stats_db import get_stats_repository


class DatabaseLogHandler(logging.Handler):
    """Persist TUI logs into reanimator_terminal_logs for later analysis."""

    def __init__(self, db_path: Path, level: int = logging.INFO) -> None:
        super().__init__(level=level)
        self._db_path = db_path
        self._stats_repo = None

    def _repo(self):
        if self._stats_repo is None:
            self._stats_repo = get_stats_repository(self._db_path)
        return self._stats_repo

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if record.name.startswith("httpx"):
                return

            message = self.format(record)
            log_type = record.levelname

            for prefix in (
                f"{log_type} - ",
                f"{record.levelname} - ",
                f"{record.levelname}: ",
            ):
                if message.startswith(prefix):
                    message = message[len(prefix):]

            if " - " in message:
                parts = message.split(" - ")
                if len(parts) >= 4 and parts[0][:4].isdigit():
                    message = " - ".join(parts[3:])

            self._repo().save_terminal_log(
                log_type=log_type,
                message=message,
                logger=record.name,
                domain="reanimator",
            )
        except Exception:
            self.handleError(record)


def setup_database_logging(logger: logging.Logger, db_path: Path, level: int = logging.INFO) -> DatabaseLogHandler:
    """Attach a database log handler to the provided logger."""

    handler = DatabaseLogHandler(db_path=db_path, level=level)
    logger.addHandler(handler)
    return handler


__all__ = ["DatabaseLogHandler", "setup_database_logging"]
