"""
通用进度显示工具

提供适用于逐项处理流程和长时间等待步骤的统一进度体验。
"""
from __future__ import annotations

import sys
import threading
import time
from contextlib import contextmanager
from itertools import cycle
from typing import Iterable, Iterator, Optional, TypeVar

from tqdm import tqdm

T = TypeVar("T")
_SPINNER_FRAMES = "|/-\\"


class Progress:
    """简单封装 tqdm 以便在各个子域复用。"""

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
        self._bar: Optional[tqdm] = None

    def __enter__(self) -> "Progress":
        if self._enabled:
            bar_format = "{l_bar}{bar}| {n_fmt}/{total_fmt}" if self._total else "{l_bar}{bar}| {n_fmt}"
            self._bar = tqdm(
                total=self._total,
                desc=self._desc,
                unit=self._unit,
                ncols=self._ncols,
                ascii=True,
                mininterval=0.0,
                miniters=1,
                smoothing=0.0,
                dynamic_ncols=False,
                bar_format=bar_format,
                leave=True,
            )
            self._bar.refresh()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def advance(self, n: int = 1, *, desc: Optional[str] = None) -> None:
        if not self._bar:
            return
        if desc is not None:
            self._bar.set_description(desc)
        self._bar.update(n)
        self._bar.refresh()

    def set_description(self, desc: str) -> None:
        if self._bar:
            self._bar.set_description(desc)

    def set_postfix(self, **kwargs) -> None:
        if self._bar:
            self._bar.set_postfix(kwargs, refresh=True)

    def close(self) -> None:
        if self._bar:
            self._bar.close()
            self._bar = None

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
