"""
配置数据库适配器 - SQLite 实现

遵循 Hexagonal Architecture：
- 实现 ConfigRepository 端口接口
- 提供配置的持久化存储
- 使用 SQLite 作为存储引擎
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from memosyne.core.interfaces import ConfigRepository, ConfigError


class SQLiteConfigRepository:
    """
    SQLite 配置仓储实现

    Adapter（适配器）：实现了 ConfigRepository 端口接口
    """

    def __init__(self, db_path: Path):
        """
        初始化配置数据库

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self._ensure_db_exists()

    def _ensure_db_exists(self) -> None:
        """确保数据库文件和表结构存在"""
        # 确保目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # 创建表
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def get(self, key: str) -> str | None:
        """获取配置项"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                "SELECT value FROM config WHERE key = ?",
                (key,)
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def set(self, key: str, value: str) -> None:
        """设置配置项"""
        now = datetime.now().isoformat()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                INSERT INTO config (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value, now)
            )
            conn.commit()

    def get_all(self) -> dict[str, str]:
        """获取所有配置项"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("SELECT key, value FROM config")
            return {row[0]: row[1] for row in cursor.fetchall()}

    def delete(self, key: str) -> None:
        """删除配置项"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM config WHERE key = ?", (key,))
            conn.commit()

    def batch_set(self, configs: dict[str, str]) -> None:
        """
        批量设置配置项

        Args:
            configs: 配置字典
        """
        now = datetime.now().isoformat()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.executemany(
                """
                INSERT INTO config (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                [(k, v, now) for k, v in configs.items()]
            )
            conn.commit()


# 全局单例
_config_repo_instance: SQLiteConfigRepository | None = None


def get_config_repository(db_path: Path | None = None) -> ConfigRepository:
    """
    获取配置仓储单例

    Args:
        db_path: 数据库路径（仅首次调用时需要）

    Returns:
        ConfigRepository 实现

    Raises:
        ConfigError: 如果首次调用时未提供 db_path
    """
    global _config_repo_instance

    if _config_repo_instance is None:
        if db_path is None:
            raise ConfigError("首次调用 get_config_repository 时必须提供 db_path")
        _config_repo_instance = SQLiteConfigRepository(db_path)

    return _config_repo_instance


__all__ = ["SQLiteConfigRepository", "get_config_repository"]
