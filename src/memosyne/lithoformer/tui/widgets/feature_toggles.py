"""Lithoformer-specific Feature Toggle widget (并行/翻译/解析)."""

from __future__ import annotations

from textual.events import Click
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static


class LithoformerFeatureToggles(Static):
    """显示 Lithoformer 需要的三个功能开关。"""

    concurrent_enabled = reactive(False)
    translation_enabled = reactive(False)
    parsing_enabled = reactive(False)

    class ToggleChanged(Message):
        """开关状态变化事件。"""

        def __init__(self, toggle_name: str, new_value: bool) -> None:
            super().__init__()
            self.toggle_name = toggle_name
            self.new_value = new_value

    def __init__(
        self,
        concurrent: bool = False,
        translation: bool = False,
        parsing: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.concurrent_enabled = concurrent
        self.translation_enabled = translation
        self.parsing_enabled = parsing

    def render(self) -> str:
        concurrent_color = "#4aa8ff" if self.concurrent_enabled else "#5f6f81"
        translation_color = "#4aa8ff" if self.translation_enabled else "#5f6f81"
        parsing_color = "#4aa8ff" if self.parsing_enabled else "#5f6f81"

        concurrent_bar = self._format_toggle(self.concurrent_enabled)
        translation_bar = self._format_toggle(self.translation_enabled)
        parsing_bar = self._format_toggle(self.parsing_enabled)

        return (
            f"    [{concurrent_color}]┏━━━━━━━━━━┓[/{concurrent_color}]      "
            f"[{translation_color}]┏━━━━━━━━━━┓[/{translation_color}]      "
            f"[{parsing_color}]┏━━━━━━━━━━┓[/{parsing_color}]\n"
            f"并行{concurrent_bar}  翻译{translation_bar}  解析{parsing_bar}\n"
            f"    [{concurrent_color}]┗━━━━━━━━━━┛[/{concurrent_color}]      "
            f"[{translation_color}]┗━━━━━━━━━━┛[/{translation_color}]      "
            f"[{parsing_color}]┗━━━━━━━━━━┛[/{parsing_color}]"
        )

    @staticmethod
    def _format_toggle(enabled: bool) -> str:
        if enabled:
            return "[#4aa8ff]┃ ON   ████┃[/#4aa8ff]"
        return "[#5f6f81]┃████  OFF ┃[/#5f6f81]"

    def on_click(self, event: Click) -> None:
        offset = event.get_content_offset(self)
        if offset is None:
            return

        x = offset.x
        concurrent_end = 18
        translation_end = 38

        if 0 <= x < concurrent_end:
            self.concurrent_enabled = not self.concurrent_enabled
            self.post_message(self.ToggleChanged("concurrent", self.concurrent_enabled))
        elif concurrent_end <= x < translation_end:
            self.translation_enabled = not self.translation_enabled
            self.post_message(self.ToggleChanged("translation", self.translation_enabled))
        else:
            self.parsing_enabled = not self.parsing_enabled
            self.post_message(self.ToggleChanged("parsing", self.parsing_enabled))

    def update_toggle(self, toggle_name: str, enabled: bool) -> None:
        if toggle_name == "concurrent":
            self.concurrent_enabled = enabled
        elif toggle_name == "translation":
            self.translation_enabled = enabled
        elif toggle_name == "parsing":
            self.parsing_enabled = enabled
        self.refresh()


__all__ = ["LithoformerFeatureToggles"]
