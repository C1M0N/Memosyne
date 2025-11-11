"""Reanimator TUI Application Entry Point."""

from __future__ import annotations

from textual.app import App

from .widgets.screens import ReanimatorScreen


class ReanimatorApp(App):
    """Reanimator TUI Application."""

    TITLE = "Reanimator - 术语重生器"
    CSS_PATH = None  # CSS defined inline in ReanimatorScreen

    def on_mount(self) -> None:
        """Push the main screen on app startup."""
        self.push_screen(ReanimatorScreen())


def main() -> None:
    """Entry point for the Reanimator TUI."""
    app = ReanimatorApp()
    app.run()


__all__ = ["ReanimatorApp", "main"]
