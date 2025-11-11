"""
Reanimator 配置服务 - SQLite 实现 (v0.16.0)

Unifies access to key/value config and feature flags from SQLite.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from ..config.reanimator_config import ReanimatorConfig, ReanimatorFeature, ReanimatorConfigBundle


class SQLiteReanimatorConfigService:
    """
    Reanimator 统一配置服务 (基于 config.db)

    管理两个表：
    - reanimator_config: 配置键值对
    - reanimator_feature: 功能开关
    """

    def __init__(self, db_path: Path) -> None:
        """
        初始化配置服务

        Args:
            db_path: config.db 路径
        """
        self.db_path = db_path
        self._ensure_db_exists()

    def _ensure_db_exists(self) -> None:
        """确保数据库表已初始化（使用全局单例）"""
        from .config_db import get_config_repository
        # 使用全局单例来初始化数据库，避免重复创建实例
        get_config_repository(self.db_path)

    # --- Feature Flags ---

    def get_feature_flags(self) -> ReanimatorFeature:
        """
        从 reanimator_feature 表（key/value 格式）读取功能配置

        Returns:
            ReanimatorFeature 对象
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("SELECT key, value FROM reanimator_feature")
            rows = cursor.fetchall()

            # 将 key/value 对转换为字典
            config = {}
            for key, value in rows:
                if key == "enable_concurrent":
                    config[key] = value == "1"
                else:
                    config[key] = value

            # 如果表为空，返回默认值
            if not config:
                return ReanimatorFeature()

            return ReanimatorFeature(**config)

    def update_feature_flags(self, **kwargs) -> None:
        """
        更新功能配置（支持 bool 类型，存储为 key/value 对）

        Args:
            **kwargs: 要更新的功能开关（如 enable_concurrent=True）
        """
        if not kwargs:
            return

        valid = {"enable_concurrent"}
        fields = {k: v for k, v in kwargs.items() if k in valid}

        if not fields:
            return

        now = datetime.now().isoformat()

        with sqlite3.connect(str(self.db_path)) as conn:
            for key, value in fields.items():
                # 将 bool 转换为 '1'/'0'
                if isinstance(value, bool):
                    value_str = "1" if value else "0"
                else:
                    value_str = str(value)

                conn.execute(
                    """
                    INSERT INTO reanimator_feature (key, value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = excluded.updated_at
                    """,
                    (key, value_str, now)
                )
            conn.commit()

    # --- Key/Value Config ---

    def get_config(self, key: str) -> str | None:
        """
        获取单个配置项

        Args:
            key: 配置键

        Returns:
            配置值，如果不存在则返回 None
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT value FROM reanimator_config WHERE key = ?",
                (key,)
            ).fetchone()
            return row[0] if row else None

    def set_config(self, key: str, value: str) -> None:
        """
        设置单个配置项

        Args:
            key: 配置键
            value: 配置值
        """
        now = datetime.now().isoformat()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                INSERT INTO reanimator_config (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value, now),
            )
            conn.commit()

    def get_all_config(self) -> ReanimatorConfig:
        """
        获取所有配置项并构造为 ReanimatorConfig 对象

        Returns:
            ReanimatorConfig 对象
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("SELECT key, value FROM reanimator_config")
            rows = cursor.fetchall()

            # 将 key/value 对转换为字典
            config_dict = {row[0]: row[1] for row in rows}

            # 类型转换
            if "max_concurrent" in config_dict:
                config_dict["max_concurrent"] = int(config_dict["max_concurrent"])
            if "max_retries" in config_dict:
                config_dict["max_retries"] = int(config_dict["max_retries"])

            # 如果表为空，返回默认值
            if not config_dict:
                return ReanimatorConfig()

            return ReanimatorConfig(**config_dict)

    def update_config(self, **kwargs) -> None:
        """
        批量更新配置项

        Args:
            **kwargs: 要更新的配置项（如 max_concurrent=5）
        """
        if not kwargs:
            return

        valid = {
            "reanimator_input_dir",
            "reanimator_output_dir",
            "default_model",
            "term_list_path",
            "max_concurrent",
            "max_retries",
        }
        fields = {k: v for k, v in kwargs.items() if k in valid}

        if not fields:
            return

        now = datetime.now().isoformat()

        with sqlite3.connect(str(self.db_path)) as conn:
            for key, value in fields.items():
                conn.execute(
                    """
                    INSERT INTO reanimator_config (key, value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = excluded.updated_at
                    """,
                    (key, str(value), now)
                )
            conn.commit()

    # --- Bundle ---

    def get_config_bundle(self) -> ReanimatorConfigBundle:
        """
        获取完整的配置包（配置 + 功能开关 + 路径）

        Returns:
            ReanimatorConfigBundle 对象
        """
        config = self.get_all_config()
        feature = self.get_feature_flags()

        # 构造路径对象
        from ..config.reanimator_config import ReanimatorPaths
        paths = ReanimatorPaths(
            input_dir=Path(config.reanimator_input_dir) if config.reanimator_input_dir else None,
            output_dir=Path(config.reanimator_output_dir) if config.reanimator_output_dir else None,
        )

        return ReanimatorConfigBundle(
            config=config,
            feature=feature,
            paths=paths,
        )


# 全局单例
_reanimator_config_service_instance: SQLiteReanimatorConfigService | None = None


def get_reanimator_config_service(db_path: Path | None = None) -> SQLiteReanimatorConfigService:
    """
    获取 Reanimator 配置服务单例

    Args:
        db_path: config.db 路径（仅首次调用时需要）

    Returns:
        SQLiteReanimatorConfigService 实例
    """
    global _reanimator_config_service_instance

    if _reanimator_config_service_instance is None:
        if db_path is None:
            raise ValueError("db_path is required for first call to get_reanimator_config_service")
        _reanimator_config_service_instance = SQLiteReanimatorConfigService(db_path)

    return _reanimator_config_service_instance


__all__ = [
    "SQLiteReanimatorConfigService",
    "get_reanimator_config_service",
]
