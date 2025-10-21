"""Custom Progress Bar with Time and Tokens Display."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.widget import Widget
from textual.widgets import Static


class CustomProgressBar(Widget):
    """自定义进度条：显示时间、剩余时间、tokens、进度条和百分比。

    格式：
    运行时间：4:00 剩余时间：6:00 已使用tokens：18866
    |################                        | 4/10
                    40%
    """

    DEFAULT_CSS = """
    CustomProgressBar {
        height: auto;
        background: $panel;
        border: round $primary;
        padding: 0 1;
    }

    CustomProgressBar > #progress-info {
        height: 1;
        color: $text;
        content-align: left middle;
    }

    CustomProgressBar > #progress-bar-line {
        height: 1;
        color: $accent;
        content-align: left middle;
    }

    CustomProgressBar > #progress-percentage {
        height: 1;
        color: $accent;
        content-align: left middle;
        text-style: bold;
    }
    """

    def __init__(
        self,
        total: int = 100,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._total = total
        self._current = 0
        self._elapsed_time = "0:00"
        self._remaining_time = "--:--"
        self._tokens = 0

    def compose(self) -> ComposeResult:
        """Compose the progress bar widgets."""
        yield Static("", id="progress-info")
        yield Static("", id="progress-bar-line")
        yield Static("", id="progress-percentage")

    def update_progress(
        self,
        current: int,
        total: int | None = None,
        elapsed_time: str = "0:00",
        remaining_time: str = "--:--",
        tokens: int = 0,
    ) -> None:
        """更新进度条显示。

        Args:
            current: 当前完成数
            total: 总数（如果提供则更新）
            elapsed_time: 已运行时间（格式：m:ss 或 h:mm）
            remaining_time: 剩余时间（格式：m:ss 或 h:mm）
            tokens: 已使用的 tokens 数量
        """
        if total is not None:
            self._total = total

        self._current = current
        self._elapsed_time = elapsed_time
        self._remaining_time = remaining_time
        self._tokens = tokens

        self._refresh_display()

    def _refresh_display(self) -> None:
        """刷新进度条显示。"""
        # 计算百分比
        if self._total > 0:
            percentage = (self._current / self._total) * 100
        else:
            percentage = 0

        # 第一行：时间和 tokens 信息
        info_line = (
            f"运行时间：{self._elapsed_time}  "
            f"剩余时间：{self._remaining_time}  "
            f"已使用tokens：{self._tokens}"
        )

        # 第二行：进度条
        # 根据终端宽度动态调整进度条长度
        # 获取当前widget的宽度（减去边框和padding）
        try:
            # 获取content区域的宽度
            content_width = max(self.size.width - 4, 20)  # 至少20个字符
        except Exception:
            content_width = 50  # 默认50个字符

        # 计算进度条实际宽度（减去其他文本的空间）
        counter_text = f" {self._current}/{self._total}"
        bar_width = max(content_width - len(counter_text) - 3, 20)  # 至少20个字符

        filled = int((percentage / 100) * bar_width)
        empty = bar_width - filled

        bar_line = (
            f"|{'#' * filled}{' ' * empty}|{counter_text}"
        )

        # 第三行：百分比（跟随进度条移动）
        percentage_text = f"{percentage:.0f}%"

        # 计算百分比位置：上面有几个#号，下面就空几个空格
        # bar_line: |################                        | 4/10
        # pct_line: ################40%（#号数量=空格数量）
        pct_position = filled
        pct_line = " " * pct_position + percentage_text

        # 更新 widgets
        try:
            info_widget = self.query_one("#progress-info", Static)
            bar_widget = self.query_one("#progress-bar-line", Static)
            pct_widget = self.query_one("#progress-percentage", Static)

            info_widget.update(info_line)
            bar_widget.update(bar_line)
            pct_widget.update(pct_line)

        except Exception:
            # 如果 widgets 还没有挂载，忽略错误
            pass

    def reset(self) -> None:
        """重置进度条。"""
        self._current = 0
        self._elapsed_time = "0:00"
        self._remaining_time = "--:--"
        self._tokens = 0
        self._refresh_display()
