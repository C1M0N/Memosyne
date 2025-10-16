"""Logging helpers for the Textual-based Lithoformer TUI."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable

# Type alias for the callback used to push formatted log strings to the UI.
LogSink = Callable[[str], None]


class TextualLogHandler(logging.Handler):
    """Logging handler that forwards formatted log messages to the TUI."""

    LEVEL_STYLES: dict[int, str] = {
        logging.DEBUG: "dim",
        logging.INFO: "cyan",
        logging.WARNING: "yellow",
        logging.ERROR: "bold red",
        logging.CRITICAL: "bold reverse red",
    }

    def __init__(self, sink: LogSink, level: int = logging.INFO) -> None:
        super().__init__(level=level)
        self._sink = sink

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D401 - standard override
        """Emit a log record to the attached sink."""
        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        level_name = record.levelname.upper()
        message = self.format(record)

        style = self.LEVEL_STYLES.get(record.levelno, "white")
        rendered = f"[grey50]{timestamp}[/] [{style}]{level_name:<8}[/] {message}"

        try:
            self._sink(rendered)
        except Exception:  # pragma: no cover - we never want logging to crash the app
            self.handleError(record)


def build_textual_handler(sink: LogSink) -> TextualLogHandler:
    """Create a handler configured with the project's preferred log format."""
    handler = TextualLogHandler(sink)
    formatter = logging.Formatter("%(name)s :: %(message)s")
    handler.setFormatter(formatter)
    return handler


__all__ = ["build_textual_handler", "TextualLogHandler"]
