"""Reanimator-specific Feature Toggle widget (仅并行开关)."""

from __future__ import annotations

from textual.events import Click
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static


class ReanimatorFeatureToggles(Static):
    """只包含并行开关的 Reanimator 控件。"""

    concurrent_enabled = reactive(False)

    class ToggleChanged(Message):
        """开关状态变化事件。"""

        def __init__(self, new_value: bool) -> None:
            super().__init__()
            self.toggle_name = "concurrent"
            self.new_value = new_value

    def __init__(self, concurrent: bool = False, **kwargs) -> None:
        super().__init__(**kwargs)
        self.concurrent_enabled = concurrent

    def render(self) -> str:
        color = "#4aa8ff" if self.concurrent_enabled else "#5f6f81"
        bar = self._format_toggle(self.concurrent_enabled)
        return (
            f"    [{color}]┏━━━━━━━━━━┓[/{color}]\n"
            f"并行{bar}\n"
            f"    [{color}]┗━━━━━━━━━━┛[/{color}]"
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
        # 单个开关，点击任意位置都切换
        self.concurrent_enabled = not self.concurrent_enabled
        self.post_message(self.ToggleChanged(self.concurrent_enabled))

    def update_toggle(self, enabled: bool) -> None:
        self.concurrent_enabled = enabled
        self.refresh()


__all__ = ["ReanimatorFeatureToggles"]
