"""Database Log Handler - 将日志写入数据库

将TUI中的日志消息保存到lithoformer_terminal_logs表，用于后续分析和调试。
"""
import logging
from pathlib import Path

from ...shared.infrastructure.stats_db import get_stats_repository


class DatabaseLogHandler(logging.Handler):
    """将日志记录到数据库的Handler

    职责：
    - 接收logging模块的日志记录
    - 过滤并保存到lithoformer_terminal_logs表
    - 支持异步写入（避免阻塞主线程）

    Usage:
        >>> handler = DatabaseLogHandler(db_path=Path("db/stat.db"))
        >>> handler.setLevel(logging.INFO)
        >>> logger = logging.getLogger("memosyne.lithoformer")
        >>> logger.addHandler(handler)
    """

    def __init__(self, db_path: Path, level: int = logging.INFO):
        """初始化DatabaseLogHandler

        Args:
            db_path: 数据库路径
            level: 最低日志级别（默认INFO）
        """
        super().__init__(level=level)
        self.db_path = db_path
        self._stats_repo = None

    def _get_stats_repo(self):
        """延迟初始化stats_repo（避免在import时创建数据库）"""
        if self._stats_repo is None:
            self._stats_repo = get_stats_repository(self.db_path)
        return self._stats_repo

    def emit(self, record: logging.LogRecord) -> None:
        """处理日志记录（logging.Handler的核心方法）

        Args:
            record: 日志记录对象
        """
        try:
            # 格式化日志消息
            message = self.format(record)

            # 获取日志级别名称
            log_type = record.levelname  # DEBUG, INFO, WARNING, ERROR, CRITICAL

            # 写入数据库
            stats_repo = self._get_stats_repo()
            stats_repo.save_terminal_log(
                log_type=log_type,
                message=message,
            )
        except Exception:
            # 避免日志记录本身出错影响程序运行
            # 调用handleError让logging模块处理异常
            self.handleError(record)


def setup_database_logging(logger: logging.Logger, db_path: Path, level: int = logging.INFO) -> DatabaseLogHandler:
    """便捷函数：为logger添加DatabaseLogHandler

    Args:
        logger: 目标logger对象
        db_path: 数据库路径
        level: 最低日志级别

    Returns:
        DatabaseLogHandler: 创建的handler实例

    Example:
        >>> logger = logging.getLogger("memosyne.lithoformer")
        >>> handler = setup_database_logging(logger, Path("db/stat.db"))
    """
    handler = DatabaseLogHandler(db_path=db_path, level=level)

    # 设置日志格式（可选，默认使用默认格式）
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    return handler
