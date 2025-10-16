"""Lithoformer TUI Application."""

from __future__ import annotations

import logging

from textual.app import App

from .widgets.screens import MainScreen


class LithoformerTUIApp(App):
    """Lithoformer TUI Application."""

    CSS_PATH = "css/lithoformer.tcss"
    TITLE = "Lithoformer TUI"

    def __init__(self):
        super().__init__()
        self._setup_logging()

    def _setup_logging(self) -> None:
        """Set up logging for the application."""
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        for handler in list(root.handlers):
            root.removeHandler(handler)

    async def on_mount(self) -> None:
        """Handle mount event."""
        await self.push_screen(MainScreen())


def run() -> None:
    """Run the Lithoformer TUI application."""
    app = LithoformerTUIApp()
    app.run()


if __name__ == "__main__":
    run()
