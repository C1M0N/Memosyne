"""
日志配置模块

提供统一的日志记录器，支持多种输出格式和日志级别
"""
import logging
import sys
from pathlib import Path
from typing import Literal

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def setup_logger(
    name: str = "memosyne",
    level: LogLevel = "INFO",
    log_file: Path | str | None = None,
    format_type: Literal["simple", "detailed"] = "simple"
) -> logging.Logger:
    """
    配置并返回日志记录器

    Args:
        name: 日志记录器名称
        level: 日志级别
        log_file: 日志文件路径（None 表示只输出到控制台）
        format_type: 格式类型
            - "simple": 简洁格式（用于终端）
            - "detailed": 详细格式（用于文件）

    Returns:
        配置好的 logger 对象

    Example:
        >>> logger = setup_logger("memosyne", "INFO")
        >>> logger.info("开始处理术语")
        >>> logger.error("LLM 调用失败", exc_info=True)
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level))

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 格式定义
    formats = {
        "simple": "%(levelname)s: %(message)s",
        "detailed": "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
    }
    formatter = logging.Formatter(formats[format_type])

    # 控制台 handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件 handler（如果指定）
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(formats["detailed"]))
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "memosyne") -> logging.Logger:
    """
    获取已配置的日志记录器（如果未配置则使用默认配置）

    Args:
        name: 日志记录器名称

    Returns:
        日志记录器
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logger(name)
    return logger
