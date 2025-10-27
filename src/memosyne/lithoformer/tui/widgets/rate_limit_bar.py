"""Rate Limit Bar widget - 显示API配额信息的mini进度条"""

from __future__ import annotations

from textual.widgets import Static


class RateLimitBar(Static):
    """Rate limit mini进度条，显示API配额信息

    显示格式：
    可用请求数：｜/////     ｜  59/500  可用tokens数：｜/         ｜149k/2.0M
    """

    DEFAULT_CSS = """
    RateLimitBar {
        height: 1;
        min-height: 1;
        max-height: 1;
        padding: 0 1;
        background: $panel;
        color: $text;
        content-align: left middle;
    }
    """

    def __init__(self) -> None:
        super().__init__("", id="rate-limit-bar")
        self._rate_limit_info: dict | None = None

    @staticmethod
    def _format_number_compact(num: int) -> str:
        """将数字格式化为4个等宽字符。

        示例：
            59 -> "  59"
            1499 -> "1.5k"
            149000 -> "149k"
            2000000 -> "2.0M"
            15000000 -> " 15M"
        """
        if num < 1000:
            # 小于1000，右对齐4字符
            return f"{num:>4d}"
        elif num < 10000:
            # 1k-9.9k
            return f"{num / 1000:.1f}k"
        elif num < 1000000:
            # 10k-999k
            return f"{int(num / 1000):>3d}k"
        elif num < 10000000:
            # 1.0M-9.9M
            return f"{num / 1000000:.1f}M"
        else:
            # 10M+
            return f"{int(num / 1000000):>3d}M"

    def _build_rate_limit_display(self) -> str:
        """构建rate limit mini进度条字符串。

        Returns:
            str: 格式化的rate limit进度条，例如：
                普通模型："可用请求数：｜/////     ｜  59/500  可用tokens数：｜/         ｜149k/2.0M"
                4o-mini： "剩余请求数：9919  可用tokens数：｜////      ｜190k/200k"
        """
        if not self._rate_limit_info:
            return ""

        try:
            remaining_requests = self._rate_limit_info["remaining_requests"]
            limit_requests = self._rate_limit_info["limit_requests"]
            remaining_tokens = self._rate_limit_info["remaining_tokens"]
            limit_tokens = self._rate_limit_info["limit_tokens"]
            model = self._rate_limit_info.get("model", "")

            # 检测是否是gpt-4o-mini（OpenAI API返回的是RPD，不是RPM，容易误导）
            is_4o_mini = "gpt-4o-mini" in model.lower()

            # Tokens部分：所有模型都正常显示进度条
            tok_percentage = remaining_tokens / limit_tokens if limit_tokens > 0 else 0
            tok_filled = int(tok_percentage * 8)
            tok_bar = "/" * tok_filled + " " * (8 - tok_filled)
            tok_remaining_str = self._format_number_compact(remaining_tokens)
            tok_limit_str = self._format_number_compact(limit_tokens)
            tokens_part = f"可用tokens数：｜{tok_bar}｜{tok_remaining_str}/{tok_limit_str}"

            # Requests部分：4o-mini特殊处理
            if is_4o_mini:
                # 4o-mini：只显示剩余数量，不显示进度条和总数（因为API返回的是RPD）
                req_remaining_str = self._format_number_compact(remaining_requests)
                requests_part = f"剩余请求数：{req_remaining_str}"
            else:
                # 其他模型：正常显示进度条
                req_percentage = remaining_requests / limit_requests if limit_requests > 0 else 0
                req_filled = int(req_percentage * 8)
                req_bar = "/" * req_filled + " " * (8 - req_filled)
                req_remaining_str = self._format_number_compact(remaining_requests)
                req_limit_str = self._format_number_compact(limit_requests)
                requests_part = f"可用请求数：｜{req_bar}｜{req_remaining_str}/{req_limit_str}"

            # Reset时间部分（用于debug）
            reset_seconds = self._rate_limit_info.get("reset_tokens_seconds")
            reset_part = f"  重置：{reset_seconds}s" if reset_seconds is not None else ""

            return f"{requests_part}  {tokens_part}{reset_part}"

        except (KeyError, TypeError, ZeroDivisionError):
            # 数据不完整或无效，返回空字符串
            return ""

    def update_rate_limit(self, rate_limit_info: dict | None) -> None:
        """更新rate limit信息（由1秒定时器调用）。

        Args:
            rate_limit_info: rate limit信息字典，包含：
                - remaining_requests: 剩余请求数
                - limit_requests: 请求数限制
                - remaining_tokens: 剩余token数
                - limit_tokens: token限制
                - provider: 提供商名称
                - timestamp: 时间戳
        """
        self._rate_limit_info = rate_limit_info
        self.update(self._build_rate_limit_display())
