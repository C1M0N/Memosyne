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


def _populate_default_configs(conn: sqlite3.Connection) -> None:
    """填充默认配置值到config表（替代硬编码）

    此函数将原本硬编码在代码中的配置值存入数据库，便于后续修改。
    包括：
    - 批处理配置（timezone, max_batch_runs_per_day）
    - 429重试策略配置（base_delay, max_wait, max_retries）
    - 提供商特定配置（anthropic_max_tokens, openai_max_retries）
    """
    configs = [
        # 批处理配置
        ("batch_timezone", "America/New_York"),
        ("max_batch_runs_per_day", "26"),
        ("reanimator_term_list_version", "v1"),

        # 429错误重试策略
        ("rate_limit_max_retries", "100"),  # 429错误最大重试次数
        ("rate_limit_base_delay", "15"),     # 基础延迟（秒）
        ("rate_limit_max_wait", "120"),      # 最大等待时间（秒）

        # 提供商特定配置
        ("anthropic_max_tokens", "16384"),
        ("openai_max_retries", "2"),

        # 其他错误重试间隔
        ("other_error_retry_delay", "2"),    # 非429错误的重试间隔（秒）

        # Rate Limit优化配置
        ("tokens_threshold", "5000"),  # tokens阈值，低于此值暂停发送（避免浪费）
    ]

    now = datetime.now().isoformat()
    for key, value in configs:
        conn.execute("""
            INSERT OR IGNORE INTO lithoformer_config (key, value, updated_at)
            VALUES (?, ?, ?)
        """, (key, value, now))


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
        """确保数据库文件和表结构存在（v1.9.0重构版）"""
        # 确保目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # 创建表
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # 1. 重命名config表为lithoformer_config（如果还没改名）
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='config'")
            if cursor.fetchone():
                cursor.execute("ALTER TABLE config RENAME TO lithoformer_config")

            # 创建lithoformer_config表（如果不存在）
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS lithoformer_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            # 删除reserved_config_1配置项
            conn.execute("DELETE FROM lithoformer_config WHERE key = 'reserved_config_1'")

            # 2. 重构feature表为key/value格式
            # 2.1 读取旧feature表数据（如果存在）
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='feature'")
            old_feature_exists = cursor.fetchone() is not None

            if old_feature_exists:
                # 读取旧数据
                cursor.execute("SELECT * FROM feature WHERE id = 1")
                old_data = cursor.fetchone()

                # 删除旧表
                conn.execute("DROP TABLE feature")
            else:
                old_data = None

            # 2.2 创建新的lithoformer_feature表（key/value格式）
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS lithoformer_feature (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            # 2.3 迁移数据或插入默认值
            timestamp = datetime.now().isoformat()
            if old_data:
                # 从旧数据迁移（id, enable_translation, enable_parsing, enable_concurrent, openai_tier, anthropic_tier, updated_at）
                features = [
                    ('enable_translation', '1' if old_data[1] else '0'),
                    ('enable_parsing', '1' if old_data[2] else '0'),
                    ('enable_concurrent', '1' if old_data[3] else '0'),
                    ('openai_tier', str(old_data[4] if len(old_data) > 4 and old_data[4] is not None else 1)),
                    ('anthropic_tier', str(old_data[5] if len(old_data) > 5 and old_data[5] is not None else 1)),
                ]
            else:
                # 默认值
                features = [
                    ('enable_translation', '1'),
                    ('enable_parsing', '1'),
                    ('enable_concurrent', '0'),
                    ('openai_tier', '1'),
                    ('anthropic_tier', '1'),
                ]

            # v1.9.2c: 修复 - 使用 INSERT OR IGNORE 避免覆盖用户配置
            for key, value in features:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO lithoformer_feature (key, value, updated_at)
                    VALUES (?, ?, ?)
                    """,
                    (key, value, timestamp)
                )

            # 3. 清理遗留统计表（已迁移到 stat.db）
            conn.execute("DROP TABLE IF EXISTS processing_stats")
            # 清理遗留feature_config表（旧版本）
            conn.execute("DROP TABLE IF EXISTS feature_config")

            # 4. LLM模型信息表
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS llm_models (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    alias TEXT,
                    price_input REAL NOT NULL,
                    price_output REAL NOT NULL,
                    rpm_limit_tier1 INTEGER,
                    rpm_limit_tier2 INTEGER,
                    rpm_limit_tier3 INTEGER,
                    rpm_limit_tier4 INTEGER,
                    rpm_limit_tier5 INTEGER,
                    tpm_limit_tier1 INTEGER,
                    tpm_limit_tier2 INTEGER,
                    tpm_limit_tier3 INTEGER,
                    tpm_limit_tier4 INTEGER,
                    tpm_limit_tier5 INTEGER,
                    itpm_limit_tier1 INTEGER,
                    itpm_limit_tier2 INTEGER,
                    itpm_limit_tier3 INTEGER,
                    itpm_limit_tier4 INTEGER,
                    itpm_limit_tier5 INTEGER,
                    otpm_limit_tier1 INTEGER,
                    otpm_limit_tier2 INTEGER,
                    otpm_limit_tier3 INTEGER,
                    otpm_limit_tier4 INTEGER,
                    otpm_limit_tier5 INTEGER,
                    is_active BOOLEAN DEFAULT 1,
                    is_default BOOLEAN DEFAULT 0,
                    is_display BOOLEAN DEFAULT 0,
                    created_at TEXT NOT NULL,
                    UNIQUE(provider, model_id)
                )
                """
            )

            # 初始化LLM模型数据
            self._populate_llm_models(conn)

            conn.commit()

    def _populate_llm_models(self, conn: sqlite3.Connection) -> None:
        """填充LLM模型数据（仅在表为空时执行）"""
        # 检查表是否已有数据
        cursor = conn.execute("SELECT COUNT(*) FROM llm_models")
        if cursor.fetchone()[0] > 0:
            return  # 已有数据，跳过

        now = datetime.now().isoformat()

        # OpenAI 模型数据（v0.14.0a: 精简到5个模型）
        openai_models = [
            # (model_id, display_name, alias, price_input, price_output, rpm_t1-5, tpm_t1-5)
            ("gpt-5", "GPT-5", "o50o", 1.25, 10.00, 500, 5000, 5000, 10000, 15000, 500000, 1000000, 2000000, 4000000, 40000000),
            ("gpt-5-mini", "GPT-5 Mini", "o50m", 0.25, 2.00, 500, 5000, 5000, 10000, 30000, 500000, 2000000, 4000000, 10000000, 180000000),
            ("gpt-5-nano", "GPT-5 Nano", "o50n", 0.05, 0.40, None, None, None, None, None, None, None, None, None, None),
            ("gpt-4o", "GPT-4o", "o4oo", 2.50, 10.00, 500, 5000, 5000, 10000, 10000, 30000, 450000, 800000, 2000000, 30000000),
            ("gpt-4o-mini", "GPT-4o Mini", "o4om", 0.15, 0.60, 500, 5000, 5000, 10000, 30000, 200000, 2000000, 4000000, 10000000, 150000000),
        ]

        for model_data in openai_models:
            model_id, display_name, alias, price_in, price_out = model_data[:5]
            rpm_limits = model_data[5:10]
            tpm_limits = model_data[10:15]
            # 有alias的模型在下拉菜单中显示
            is_display = 1 if alias else 0

            conn.execute(
                """
                INSERT OR IGNORE INTO llm_models (
                    provider, model_id, display_name, alias,
                    price_input, price_output,
                    rpm_limit_tier1, rpm_limit_tier2, rpm_limit_tier3, rpm_limit_tier4, rpm_limit_tier5,
                    tpm_limit_tier1, tpm_limit_tier2, tpm_limit_tier3, tpm_limit_tier4, tpm_limit_tier5,
                    is_active, is_default, is_display, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?, ?)
                """,
                ("openai", model_id, display_name, alias, price_in, price_out,
                 *rpm_limits, *tpm_limits, is_display, now)
            )

        # Anthropic 模型数据（v0.14.0c: 修正为官方文档的正确模型ID）
        # Latest models (显示在下拉菜单)
        # Legacy models (不显示在下拉菜单，但可以通过Others手动输入使用)
        anthropic_models = [
            # (model_id, display_name, alias, price_input, price_output,
            #  rpm_t1-5, itpm_t1-5, otpm_t1-5)

            # === Latest Models (2025) ===
            ("claude-sonnet-4-5-20250929", "Claude Sonnet 4.5", "cs45", 3.00, 15.00,
             50, 1000, 2000, 4000, None,
             30000, 450000, 800000, 2000000, None,
             8000, 90000, 160000, 400000, None),
            ("claude-haiku-4-5-20251001", "Claude Haiku 4.5", "ch45", 1.00, 5.00,
             50, 1000, 2000, 4000, None,
             50000, 100000, 200000, 400000, None,
             10000, 20000, 40000, 80000, None),
            ("claude-opus-4-1-20250805", "Claude Opus 4.1", "co41", 15.00, 75.00,
             50, 1000, 2000, 4000, None,
             30000, 450000, 800000, 2000000, None,
             8000, 90000, 160000, 400000, None),

            # === Legacy Models ===
            ("claude-sonnet-4-20250514", "Claude Sonnet 4", None, 3.00, 15.00,
             50, 1000, 2000, 4000, None,
             30000, 450000, 800000, 2000000, None,
             8000, 90000, 160000, 400000, None),
            ("claude-3-7-sonnet-20250219", "Claude Sonnet 3.7", None, 3.00, 15.00,
             50, 1000, 2000, 4000, None,
             20000, 40000, 80000, 200000, None,
             8000, 16000, 32000, 80000, None),
            ("claude-opus-4-20250514", "Claude Opus 4", None, 15.00, 75.00,
             50, 1000, 2000, 4000, None,
             30000, 450000, 800000, 2000000, None,
             8000, 90000, 160000, 400000, None),
            ("claude-3-5-haiku-20241022", "Claude Haiku 3.5", None, 0.80, 4.00,
             50, 1000, 2000, 4000, None,
             50000, 100000, 200000, 400000, None,
             10000, 20000, 40000, 80000, None),
            ("claude-3-haiku-20240307", "Claude Haiku 3", None, 0.25, 1.25,
             50, 1000, 2000, 4000, None,
             50000, 100000, 200000, 400000, None,
             10000, 20000, 40000, 80000, None),
        ]

        for model_data in anthropic_models:
            model_id, display_name, alias, price_in, price_out = model_data[:5]
            rpm_limits = model_data[5:10]
            itpm_limits = model_data[10:15]
            otpm_limits = model_data[15:20]
            # 有alias的模型在下拉菜单中显示
            is_display = 1 if alias else 0

            conn.execute(
                """
                INSERT OR IGNORE INTO llm_models (
                    provider, model_id, display_name, alias,
                    price_input, price_output,
                    rpm_limit_tier1, rpm_limit_tier2, rpm_limit_tier3, rpm_limit_tier4, rpm_limit_tier5,
                    itpm_limit_tier1, itpm_limit_tier2, itpm_limit_tier3, itpm_limit_tier4, itpm_limit_tier5,
                    otpm_limit_tier1, otpm_limit_tier2, otpm_limit_tier3, otpm_limit_tier4, otpm_limit_tier5,
                    is_active, is_default, is_display, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?, ?)
                """,
                ("anthropic", model_id, display_name, alias, price_in, price_out,
                 *rpm_limits, *itpm_limits, *otpm_limits, is_display, now)
            )

        # 设置默认模型（gpt-4o）
        conn.execute(
            """
            UPDATE llm_models SET is_default = 1
            WHERE provider = 'openai' AND model_id = 'gpt-4o'
            """
        )

        # 填充默认配置值（替代硬编码）
        _populate_default_configs(conn)

    def get(self, key: str) -> str | None:
        """获取配置项"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                "SELECT value FROM lithoformer_config WHERE key = ?",
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
                INSERT INTO lithoformer_config (key, value, updated_at)
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
            cursor = conn.execute("SELECT key, value FROM lithoformer_config")
            return {row[0]: row[1] for row in cursor.fetchall()}

    def delete(self, key: str) -> None:
        """删除配置项"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM lithoformer_config WHERE key = ?", (key,))
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
                INSERT INTO lithoformer_config (key, value, updated_at)
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
    SQLite 功能配置仓储实现（v1.9.0重构版）

    管理key/value格式的lithoformer_feature表
    """

    def __init__(self, db_path: Path):
        """
        初始化功能配置仓储

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path

    def get(self) -> dict[str, Any]:
        """获取功能配置（从key/value表读取）"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("SELECT key, value FROM lithoformer_feature")
            rows = cursor.fetchall()

            # 将key/value对转换为字典
            config = {}
            for key, value in rows:
                # 根据key类型解析value
                if key in ("enable_translation", "enable_parsing", "enable_concurrent", "feature_003"):
                    # Boolean类型
                    config[key] = value == "1"
                elif key in ("openai_tier", "anthropic_tier"):
                    # Integer类型
                    config[key] = int(value)
                else:
                    # 其他类型保持字符串
                    config[key] = value

            # 如果表为空，返回默认值
            if not config:
                return {
                    "enable_translation": True,
                    "enable_parsing": True,
                    "enable_concurrent": False,
                    "openai_tier": 1,
                    "anthropic_tier": 1,
                    "feature_003": False,
                }

            return config

    def update(self, **kwargs) -> None:
        """更新功能配置（支持bool和int类型，存储为key/value对）"""
        if not kwargs:
            return

        # 过滤有效字段
        valid_fields = {
            "enable_translation",
            "enable_parsing",
            "enable_concurrent",
            "openai_tier",
            "anthropic_tier",
            "feature_003",
        }
        fields_to_update = {k: v for k, v in kwargs.items() if k in valid_fields}

        if not fields_to_update:
            return

        now = datetime.now().isoformat()

        with sqlite3.connect(str(self.db_path)) as conn:
            for key, value in fields_to_update.items():
                # 将bool转换为'1'/'0'，int转换为字符串
                if isinstance(value, bool):
                    value_str = "1" if value else "0"
                else:
                    value_str = str(value)

                conn.execute(
                    """
                    INSERT INTO lithoformer_feature (key, value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = excluded.updated_at
                    """,
                    (key, value_str, now)
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
