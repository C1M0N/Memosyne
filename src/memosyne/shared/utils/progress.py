"""
通用进度显示工具

提供适用于逐项处理流程和长时间等待步骤的统一进度体验。
为了兼容纯 Textual/TUI 流程，这里的 Progress 为轻量级占位实现，
不会依赖 tqdm 或尝试操作终端，调用方可以继续使用 progress_callback
获取实时进度。
"""
from __future__ import annotations

import sys
import threading
import time
from contextlib import contextmanager
from itertools import cycle
from typing import Iterable, Iterator, Optional, TypeVar

T = TypeVar("T")
_SPINNER_FRAMES = "|/-\\"


class Progress:
    """轻量级进度追踪器（不进行终端绘制，由调用方决定如何显示）。"""

    def __init__(
        self,
        *,
        total: Optional[int] = None,
        desc: str = "",
        unit: str = "item",
        enabled: bool = True,
        ncols: int = 100,
    ) -> None:
        self._enabled = enabled
        self._total = total
        self._desc = desc
        self._unit = unit
        self._ncols = ncols
        self._current = 0
        self._progress_desc: Optional[str] = desc

    def __enter__(self) -> "Progress":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def advance(self, n: int = 1, *, desc: Optional[str] = None) -> None:
        if not self._enabled:
            return
        self._current += n
        if desc is not None:
            self._progress_desc = desc

    def set_description(self, desc: str) -> None:
        if not self._enabled:
            return
        self._progress_desc = desc

    def set_postfix(self, **kwargs) -> None:
        # no-op placeholder保持兼容
        return

    def close(self) -> None:
        return

    @property
    def enabled(self) -> bool:
        return self._enabled


@contextmanager
def indeterminate_progress(message: str, enabled: bool = True, interval: float = 0.1) -> Iterator[None]:
    """
    显示一个简易的旋转指示器（适用于无法获得总数的等待场景）。
    """
    if not enabled:
        yield
        return

    stop_event = threading.Event()

    def _spin() -> None:
        frames = cycle(_SPINNER_FRAMES)
        while not stop_event.is_set():
            frame = next(frames)
            sys.stdout.write(f"\r{message} {frame}")
            sys.stdout.flush()
            time.sleep(interval)
        sys.stdout.write("\r" + " " * (len(message) + 2) + "\r")
        sys.stdout.flush()

    thread = threading.Thread(target=_spin, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop_event.set()
        thread.join()


def iterate_with_progress(
    iterable: Iterable[T],
    *,
    total: Optional[int] = None,
    desc: str = "",
    unit: str = "item",
    enabled: bool = True,
) -> Iterator[tuple[int, T, Progress]]:
    """
    结合 enumerate 与 Progress，返回 (index, item, progress)。

    注意：调用方需要在处理完每个元素后手动调用 progress.advance()
    以推进进度条，并根据需要更新描述信息。
    """
    with Progress(total=total, desc=desc, unit=unit, enabled=enabled) as progress:
        for index, item in enumerate(iterable):
            yield index, item, progress
