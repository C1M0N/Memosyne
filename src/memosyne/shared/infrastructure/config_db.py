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

            # 2. 功能状态表（单行配置）
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS feature_config (
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

            # 初始化feature_config表（确保有且仅有一行）
            conn.execute(
                """
                INSERT OR IGNORE INTO feature_config (id, updated_at)
                VALUES (1, datetime('now'))
                """
            )

            # 3. 处理统计表
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS processing_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_number TEXT,
                    model TEXT,
                    char_count INTEGER,
                    use_translation BOOLEAN,
                    use_parsing BOOLEAN,
                    original_text TEXT,
                    output_text TEXT,
                    output_filename TEXT,
                    processing_time REAL,
                    created_at TEXT NOT NULL
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


class SQLiteFeatureConfigRepository:
    """
    SQLite 功能配置仓储实现

    管理单行功能配置表（feature_config）
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
                FROM feature_config WHERE id = 1
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
                UPDATE feature_config
                SET {set_clause}, updated_at = ?
                WHERE id = 1
                """,
                values
            )
            conn.commit()


class SQLiteStatsRepository:
    """
    SQLite 处理统计仓储实现

    管理问题处理的性能统计数据（processing_stats）
    """

    def __init__(self, db_path: Path):
        """
        初始化统计仓储

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path

    def save_stat(
        self,
        question_number: str,
        model: str,
        char_count: int,
        use_translation: bool,
        use_parsing: bool,
        original_text: str,
        output_text: str,
        output_filename: str,
        processing_time: float,
    ) -> None:
        """保存单条处理统计"""
        # 截断文本到最大长度
        original_text = original_text[:50000]
        output_text = output_text[:50000]

        now = datetime.now().isoformat()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                INSERT INTO processing_stats (
                    question_number, model, char_count,
                    use_translation, use_parsing,
                    original_text, output_text, output_filename,
                    processing_time, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    question_number,
                    model,
                    char_count,
                    use_translation,
                    use_parsing,
                    original_text,
                    output_text,
                    output_filename,
                    processing_time,
                    now,
                ),
            )
            conn.commit()

    def batch_save_stats(self, stats: list[dict[str, Any]]) -> None:
        """批量保存统计数据"""
        if not stats:
            return

        now = datetime.now().isoformat()
        values = []
        for stat in stats:
            values.append(
                (
                    stat.get("question_number", ""),
                    stat.get("model", ""),
                    stat.get("char_count", 0),
                    stat.get("use_translation", False),
                    stat.get("use_parsing", False),
                    stat.get("original_text", "")[:50000],
                    stat.get("output_text", "")[:50000],
                    stat.get("output_filename", ""),
                    stat.get("processing_time", 0.0),
                    now,
                )
            )

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.executemany(
                """
                INSERT INTO processing_stats (
                    question_number, model, char_count,
                    use_translation, use_parsing,
                    original_text, output_text, output_filename,
                    processing_time, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
            conn.commit()

    def get_estimated_time(
        self,
        model: str,
        char_count: int,
        use_translation: bool,
        use_parsing: bool,
    ) -> float | None:
        """
        获取预估处理时长（基于历史数据平均值）

        查询条件：
        1. 相同模型
        2. 相同功能配置（翻译+解析）
        3. 字符数在±20%范围内

        Returns:
            平均处理时长（秒），如果没有匹配数据返回None
        """
        char_min = int(char_count * 0.8)
        char_max = int(char_count * 1.2)

        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                """
                SELECT AVG(processing_time) as avg_time
                FROM processing_stats
                WHERE model = ?
                  AND use_translation = ?
                  AND use_parsing = ?
                  AND char_count BETWEEN ? AND ?
                """,
                (model, use_translation, use_parsing, char_min, char_max),
            )
            row = cursor.fetchone()
            if row and row[0] is not None:
                return float(row[0])
            return None


# 全局单例（功能配置和统计）
_feature_config_repo_instance: SQLiteFeatureConfigRepository | None = None
_stats_repo_instance: SQLiteStatsRepository | None = None


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
    global _stats_repo_instance

    if _stats_repo_instance is None:
        if db_path is None:
            from memosyne.core.interfaces import ConfigError
            raise ConfigError("首次调用 get_stats_repository 时必须提供 db_path")
        _stats_repo_instance = SQLiteStatsRepository(db_path)

    return _stats_repo_instance


__all__ = [
    "SQLiteConfigRepository",
    "get_config_repository",
    "SQLiteFeatureConfigRepository",
    "get_feature_config_repository",
    "SQLiteStatsRepository",
    "get_stats_repository",
]
