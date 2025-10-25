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
            # 1. 配置表
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            # 2. 功能状态表（单行配置）— 新表名：feature
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS feature (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    enable_translation BOOLEAN DEFAULT 1,
                    enable_parsing BOOLEAN DEFAULT 1,
                    enable_concurrent BOOLEAN DEFAULT 0,
                    feature_001 BOOLEAN DEFAULT 0,
                    feature_002 BOOLEAN DEFAULT 0,
                    feature_003 BOOLEAN DEFAULT 0,
                    updated_at TEXT NOT NULL
                )
                """
            )

            # 初始化feature表（确保有且仅有一行）
            conn.execute(
                """
                INSERT OR IGNORE INTO feature (id, updated_at)
                VALUES (1, datetime('now'))
                """
            )

            # 3. 迁移旧表 feature_config -> feature（如存在）
            cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='feature_config'")
            if cur.fetchone():
                # 将旧表数据迁移到新表
                conn.execute(
                    """
                    UPDATE feature SET
                        enable_translation = COALESCE((SELECT enable_translation FROM feature_config WHERE id = 1), enable_translation),
                        enable_parsing = COALESCE((SELECT enable_parsing FROM feature_config WHERE id = 1), enable_parsing),
                        enable_concurrent = COALESCE((SELECT enable_concurrent FROM feature_config WHERE id = 1), enable_concurrent),
                        feature_001 = COALESCE((SELECT feature_001 FROM feature_config WHERE id = 1), feature_001),
                        feature_002 = COALESCE((SELECT feature_002 FROM feature_config WHERE id = 1), feature_002),
                        feature_003 = COALESCE((SELECT feature_003 FROM feature_config WHERE id = 1), feature_003),
                        updated_at = datetime('now')
                    WHERE id = 1
                    """
                )
                # 删除旧表
                conn.execute("DROP TABLE IF EXISTS feature_config")

            # 4. 清理遗留统计表（已迁移到 stat.db）
            conn.execute("DROP TABLE IF EXISTS processing_stats")

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


class SQLiteFeatureConfigRepository:
    """
    SQLite 功能配置仓储实现

    管理单行功能配置表（feature）
    """

    def __init__(self, db_path: Path):
        """
        初始化功能配置仓储

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path

    def get(self) -> dict[str, Any]:
        """获取功能配置（单行配置）"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT enable_translation, enable_parsing, enable_concurrent,
                       feature_001, feature_002, feature_003
                FROM feature WHERE id = 1
                """
            )
            row = cursor.fetchone()
            if row:
                return {
                    "enable_translation": bool(row["enable_translation"]),
                    "enable_parsing": bool(row["enable_parsing"]),
                    "enable_concurrent": bool(row["enable_concurrent"]),
                    "feature_001": bool(row["feature_001"]),
                    "feature_002": bool(row["feature_002"]),
                    "feature_003": bool(row["feature_003"]),
                }
            # 返回默认值
            return {
                "enable_translation": True,
                "enable_parsing": True,
                "enable_concurrent": False,
                "feature_001": False,
                "feature_002": False,
                "feature_003": False,
            }

    def update(self, **kwargs: bool) -> None:
        """更新功能配置"""
        if not kwargs:
            return

        # 构建UPDATE语句
        valid_fields = {
            "enable_translation",
            "enable_parsing",
            "enable_concurrent",
            "feature_001",
            "feature_002",
            "feature_003",
        }
        fields_to_update = {k: v for k, v in kwargs.items() if k in valid_fields}

        if not fields_to_update:
            return

        set_clause = ", ".join(f"{field} = ?" for field in fields_to_update.keys())
        values = list(fields_to_update.values())
        now = datetime.now().isoformat()
        values.append(now)

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                f"""
                UPDATE feature
                SET {set_clause}, updated_at = ?
                WHERE id = 1
                """,
                values
            )
            conn.commit()


# 全局单例（功能配置）
_feature_config_repo_instance: SQLiteFeatureConfigRepository | None = None


def get_feature_config_repository(db_path: Path | None = None):
    """
    获取功能配置仓储单例

    Args:
        db_path: 数据库路径（仅首次调用时需要）

    Returns:
        FeatureConfigRepository 实现
    """
    global _feature_config_repo_instance

    if _feature_config_repo_instance is None:
        if db_path is None:
            from memosyne.core.interfaces import ConfigError
            raise ConfigError("首次调用 get_feature_config_repository 时必须提供 db_path")
        _feature_config_repo_instance = SQLiteFeatureConfigRepository(db_path)

    return _feature_config_repo_instance


def get_stats_repository(db_path: Path | None = None):
    """
    获取统计仓储单例

    Args:
        db_path: 数据库路径（仅首次调用时需要）

    Returns:
        StatsRepository 实现
    """
    from .stats_db import get_stats_repository as _get_stats_repo
    return _get_stats_repo(db_path)


__all__ = [
    "SQLiteConfigRepository",
    "get_config_repository",
    "SQLiteFeatureConfigRepository",
    "get_feature_config_repository",
    "get_stats_repository",
]
