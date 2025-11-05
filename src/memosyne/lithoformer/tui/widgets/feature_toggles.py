"""Feature toggles widget for displaying and controlling concurrent/translation/parsing switches."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.events import Click
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static


class FeatureTogglesWidget(Static):
    """显示并控制三个功能开关的组件（并行、翻译、解析）"""

    # Reactive 属性：三个开关状态
    concurrent_enabled = reactive(False)
    translation_enabled = reactive(False)
    parsing_enabled = reactive(False)

    class ToggleChanged(Message):
        """当开关被点击时发送的消息"""

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
        """渲染三个开关的 ASCII 艺术风格显示（3行紧凑布局）"""
        # 根据状态确定颜色（使用tcss中的配色方案）
        # ON: #4aa8ff (蓝色), OFF: #5f6f81 (灰色)
        concurrent_color = "#4aa8ff" if self.concurrent_enabled else "#5f6f81"
        translation_color = "#4aa8ff" if self.translation_enabled else "#5f6f81"
        parsing_color = "#4aa8ff" if self.parsing_enabled else "#5f6f81"

        # 生成开关中间部分
        concurrent_bar = self._format_toggle(self.concurrent_enabled)
        translation_bar = self._format_toggle(self.translation_enabled)
        parsing_bar = self._format_toggle(self.parsing_enabled)

        # 组装完整显示（3行高度），边框也根据状态着色
        return (
            f"    [{concurrent_color}]┏━━━━━━━━━━┓[/{concurrent_color}]      [{translation_color}]┏━━━━━━━━━━┓[/{translation_color}]      [{parsing_color}]┏━━━━━━━━━━┓[/{parsing_color}] \n"
            f"并行{concurrent_bar}  翻译{translation_bar}  解析{parsing_bar}\n"
            f"    [{concurrent_color}]┗━━━━━━━━━━┛[/{concurrent_color}]      [{translation_color}]┗━━━━━━━━━━┛[/{translation_color}]      [{parsing_color}]┗━━━━━━━━━━┛[/{parsing_color}]"
        )

    def _format_toggle(self, enabled: bool) -> str:
        """
        格式化单个开关的显示

        返回开关条（bar）的显示字符串
        """
        if enabled:
            # ON 状态：蓝色 #4aa8ff（与tcss中的焦点颜色一致）
            return "[#4aa8ff]┃ ON   ████┃[/#4aa8ff]"
        else:
            # OFF 状态：灰色 #5f6f81（与tcss中的禁用颜色一致）
            return "[#5f6f81]┃████  OFF ┃[/#5f6f81]"

    def on_click(self, event: Click) -> None:
        """处理鼠标点击事件，判断点击了哪个开关"""
        # 获取点击位置的相对坐标
        widget_offset = event.get_content_offset(self)
        if widget_offset is None:
            return

        # ============ 点击区域边界配置（可微调） ============
        # 布局参考：
        #     ┏━━━━━━━━━━┓      ┏━━━━━━━━━━┓      ┏━━━━━━━━━━┓
        # 并行┃████  OFF ┃  翻译┃ ON   ████┃  解析┃ ON   ████┃
        #     ┗━━━━━━━━━━┛      ┗━━━━━━━━━━┛      ┗━━━━━━━━━━┛
        #
        # 每个开关约占：空格(4) + 标签(4) + 边框+内容(14) = 22字符
        # 根据实际显示调整以下边界值：

        CONCURRENT_X_END = 18    # 并行开关右边界（可调整，建议16-20）
        TRANSLATION_X_END = 38   # 翻译开关右边界（可调整，建议36-42）
        # 解析开关：TRANSLATION_X_END 到末尾
        # ===================================================

        x = widget_offset.x

        if 0 <= x < CONCURRENT_X_END:
            # 点击了并行开关
            self.concurrent_enabled = not self.concurrent_enabled
            self.post_message(self.ToggleChanged("concurrent", self.concurrent_enabled))
        elif CONCURRENT_X_END <= x < TRANSLATION_X_END:
            # 点击了翻译开关
            self.translation_enabled = not self.translation_enabled
            self.post_message(self.ToggleChanged("translation", self.translation_enabled))
        elif TRANSLATION_X_END <= x:
            # 点击了解析开关
            self.parsing_enabled = not self.parsing_enabled
            self.post_message(self.ToggleChanged("parsing", self.parsing_enabled))

    def update_toggle(self, toggle_name: str, enabled: bool) -> None:
        """从外部更新某个开关的状态（用于快捷键触发）"""
        if toggle_name == "concurrent":
            self.concurrent_enabled = enabled
        elif toggle_name == "translation":
            self.translation_enabled = enabled
        elif toggle_name == "parsing":
            self.parsing_enabled = enabled
        self.refresh()


__all__ = ["FeatureTogglesWidget"]
