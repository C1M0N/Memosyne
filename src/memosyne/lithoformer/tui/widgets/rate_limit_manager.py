"""Rate Limit Manager - 管理rate limit信息的缓存、计算和过期检测

负责：
- 缓存管理：存储从API获取的rate limit信息
- 过期检测：标记长时间未更新的数据
- 动态计算：实时计算reset倒计时
"""
from __future__ import annotations

import time
from typing import Any


class RateLimitManager:
    """Rate limit信息管理器

    职责：
    1. 缓存从OpenAI API获取的rate limit信息
    2. 动态计算reset倒计时（每秒递减）
    3. 检测缓存是否过期（超过15秒无更新）
    4. 提供统一的接口给Timer查询当前状态
    """

    # 缓存过期阈值（秒）：超过这个时间未更新，标记为可能过期
    STALE_THRESHOLD = 15

    def __init__(self) -> None:
        """初始化管理器"""
        self._cache: dict[str, Any] | None = None  # 原始缓存数据
        self._last_update_time: float = 0.0  # 最后一次update()的时间

    def update(self, info: dict[str, Any] | None) -> None:
        """更新缓存（当从LLM调用获得新的rate limit数据时调用）

        只保留timestamp最新的数据，避免并发场景下旧数据覆盖新数据。

        Args:
            info: rate limit信息字典，包含：
                - remaining_requests: 剩余请求数
                - limit_requests: 请求数限制
                - remaining_tokens: 剩余token数
                - limit_tokens: token限制
                - reset_tokens_seconds: reset时间（秒）
                - reset_timestamp: reset的绝对时间戳
                - timestamp: 数据获取时间戳
                - provider: 提供商
                - model: 模型名称
        """
        if info is None:
            self._cache = None
            self._last_update_time = 0.0
            return

        # 检查timestamp，只保留最新数据（避免并发场景下旧数据覆盖新数据）
        if self._cache:
            old_timestamp = self._cache.get("timestamp", 0)
            new_timestamp = info.get("timestamp", 0)
            if new_timestamp < old_timestamp:
                # 忽略旧数据
                return

        self._cache = info
        self._last_update_time = time.time()

    def get_current_info(self) -> dict[str, Any] | None:
        """获取当前的rate limit信息（包含动态计算的reset倒计时）

        Returns:
            dict | None: 更新后的rate limit信息，如果无缓存则返回None

        计算规则：
        - reset_tokens_seconds: 从原始值减去经过的时间（最小为0）
        - is_stale: 标记数据是否可能过期（超过15秒未更新）
        """
        if not self._cache:
            return None

        # 创建副本（避免修改原始缓存）
        info = dict(self._cache)

        # 动态计算reset剩余时间（倒计时）
        # 优先使用reset_timestamp（绝对时间），更准确
        reset_timestamp = self._cache.get("reset_timestamp")
        if reset_timestamp is not None:
            # 使用绝对时间戳计算倒计时（消除网络延迟影响）
            remaining_reset = max(0, int(reset_timestamp - time.time()))
            info["reset_tokens_seconds"] = remaining_reset
        else:
            # fallback：使用原有逻辑（经过时间）
            original_reset = self._cache.get("reset_tokens_seconds")
            if original_reset is not None:
                elapsed_since_update = time.time() - self._last_update_time
                remaining_reset = max(0, original_reset - int(elapsed_since_update))
                info["reset_tokens_seconds"] = remaining_reset

        # 动态计算tokens恢复（OpenAI滑动窗口机制）
        limit_tokens = self._cache.get("limit_tokens")
        original_remaining = self._cache.get("remaining_tokens")
        elapsed = time.time() - self._last_update_time

        if limit_tokens and original_remaining is not None:
            # 恢复速率：每秒恢复 TPM/60 tokens
            recovery_rate = limit_tokens / 60.0
            recovered_tokens = int(elapsed * recovery_rate)
            new_remaining = min(original_remaining + recovered_tokens, limit_tokens)
            info["remaining_tokens"] = new_remaining

        # 检测缓存是否过期（超过阈值未调用update）
        age = time.time() - self._last_update_time
        info["is_stale"] = age > self.STALE_THRESHOLD

        return info

    def clear(self) -> None:
        """清除缓存（处理结束时调用）"""
        self._cache = None
        self._last_update_time = 0.0

    @property
    def has_data(self) -> bool:
        """是否有缓存数据"""
        return self._cache is not None

    @property
    def age(self) -> float:
        """缓存年龄（秒）：距离上次update的时间"""
        if not self._cache:
            return 0.0
        return time.time() - self._last_update_time
