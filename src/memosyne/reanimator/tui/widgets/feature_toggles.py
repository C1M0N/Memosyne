"""Feature toggles widget for displaying and controlling concurrent processing switch."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.events import Click
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static


class FeatureTogglesWidget(Static):
    """显示并控制并发处理开关的组件"""

    # Reactive 属性：并发开关状态
    concurrent_enabled = reactive(False)

    class ToggleChanged(Message):
        """当开关被点击时发送的消息"""

        def __init__(self, toggle_name: str, new_value: bool) -> None:
            super().__init__()
            self.toggle_name = toggle_name
            self.new_value = new_value

    def __init__(
        self,
        concurrent: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.concurrent_enabled = concurrent

    def render(self) -> str:
        """渲染并发开关的 ASCII 艺术风格显示（3行紧凑布局）"""
        # 根据状态确定颜色
        # ON: #4aa8ff (蓝色), OFF: #5f6f81 (灰色)
        concurrent_color = "#4aa8ff" if self.concurrent_enabled else "#5f6f81"

        # 生成开关中间部分
        concurrent_bar = self._format_toggle(self.concurrent_enabled)

        # 组装完整显示（3行高度），边框也根据状态着色
        return (
            f"    [{concurrent_color}]┏━━━━━━━━━━┓[/{concurrent_color}]\n"
            f"并发{concurrent_bar}\n"
            f"    [{concurrent_color}]┗━━━━━━━━━━┛[/{concurrent_color}]"
        )

    def _format_toggle(self, enabled: bool) -> str:
        """
        格式化单个开关的显示

        返回开关条（bar）的显示字符串
        """
        if enabled:
            # ON 状态：蓝色 #4aa8ff
            return "[#4aa8ff]┃ ON   ████┃[/#4aa8ff]"
        else:
            # OFF 状态：灰色 #5f6f81
            return "[#5f6f81]┃████  OFF ┃[/#5f6f81]"

    def on_click(self, event: Click) -> None:
        """处理鼠标点击事件，切换并发开关"""
        # 获取点击位置的相对坐标
        widget_offset = event.get_content_offset(self)
        if widget_offset is None:
            return

        # 点击任意位置都切换开关
        self.concurrent_enabled = not self.concurrent_enabled
        self.post_message(self.ToggleChanged("concurrent", self.concurrent_enabled))

    def update_toggle(self, toggle_name: str, enabled: bool) -> None:
        """从外部更新开关的状态（用于快捷键触发）"""
        if toggle_name == "concurrent":
            self.concurrent_enabled = enabled
        self.refresh()


__all__ = ["FeatureTogglesWidget"]
