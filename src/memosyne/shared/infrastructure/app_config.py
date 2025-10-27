"""Application-level config aggregation service.

Unifies access to key/value config and feature flags from SQLite.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from ..config.app_config import FeatureFlags, RuntimeTuning, AppConfigBundle, LithoformerPaths, LLMModelInfo


class SQLiteAppConfigService:
    """Unified configuration service backed by SQLite (config.db)."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._ensure_db_exists()

    def _ensure_db_exists(self) -> None:
        """确保数据库表已初始化（使用全局单例）"""
        from .config_db import get_config_repository
        # 使用全局单例来初始化数据库，避免重复创建实例
        get_config_repository(self.db_path)

    # --- feature flags ---
    def get_feature_flags(self) -> FeatureFlags:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT enable_translation, enable_parsing, enable_concurrent,"
                "       openai_tier, anthropic_tier, feature_003"
                "  FROM feature WHERE id = 1"
            ).fetchone()
            if not row:
                return FeatureFlags()
            return FeatureFlags(
                enable_translation=bool(row["enable_translation"]),
                enable_parsing=bool(row["enable_parsing"]),
                enable_concurrent=bool(row["enable_concurrent"]),
                openai_tier=int(row["openai_tier"]),
                anthropic_tier=int(row["anthropic_tier"]),
                feature_003=bool(row["feature_003"]),
            )

    def update_feature_flags(self, **kwargs) -> None:
        """更新功能配置（支持bool和int类型）"""
        if not kwargs:
            return
        valid = {
            "enable_translation",
            "enable_parsing",
            "enable_concurrent",
            "openai_tier",
            "anthropic_tier",
            "feature_003",
        }
        fields = {k: v for k, v in kwargs.items() if k in valid}
        if not fields:
            return
        set_clause = ", ".join(f"{k} = ?" for k in fields.keys())
        values = list(fields.values())
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                f"UPDATE feature SET {set_clause}, updated_at = datetime('now') WHERE id = 1",
                values,
            )
            conn.commit()

    # --- key/value config ---
    def get_config(self, key: str) -> str | None:
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
            return row[0] if row else None

    def set_config(self, key: str, value: str) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                "INSERT INTO config (key, value, updated_at) VALUES (?, ?, datetime('now'))"
                " ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (key, value),
            )
            conn.commit()

    # --- aggregated ---
    def get_runtime_tuning(self) -> RuntimeTuning:
        max_concurrent = self.get_config("max_concurrent")
        max_retries = self.get_config("max_retries")
        return RuntimeTuning(
            max_concurrent=int(max_concurrent) if max_concurrent else 10,
            max_retries=int(max_retries) if max_retries else 1,
        )

    def get_default_model(self) -> str:
        """获取默认模型（格式：provider::model_id）"""
        # 优先从数据库的is_default标记读取
        model_info = self.get_default_model_info()
        if model_info:
            provider = model_info.provider.capitalize()  # openai -> OpenAI
            if provider == "Openai":
                provider = "OpenAI"
            elif provider == "Anthropic":
                provider = "Anthropic"
            return f"{provider}::{model_info.model_id}"

        # 降级到配置表（向后兼容）
        value = self.get_config("default_model")
        return value or "OpenAI::gpt-4o"

    def get_bundle(self) -> AppConfigBundle:
        return AppConfigBundle(
            default_model=self.get_default_model(),
            feature=self.get_feature_flags(),
            tuning=self.get_runtime_tuning(),
        )

    # --- paths ---
    def get_paths(self) -> LithoformerPaths:
        input_dir = self.get_config("lithoformer_input_dir")
        output_dir = self.get_config("lithoformer_output_dir")
        from pathlib import Path
        return LithoformerPaths(
            input_dir=Path(input_dir).expanduser().resolve() if input_dir else None,
            output_dir=Path(output_dir).expanduser().resolve() if output_dir else None,
        )

    def update_paths(self, *, input_dir: str | None = None, output_dir: str | None = None) -> None:
        from pathlib import Path
        if input_dir is not None:
            self.set_config("lithoformer_input_dir", str(Path(input_dir).expanduser().resolve()))
        if output_dir is not None:
            self.set_config("lithoformer_output_dir", str(Path(output_dir).expanduser().resolve()))

    # --- LLM models ---
    def get_all_models(self, active_only: bool = True) -> list[LLMModelInfo]:
        """获取所有LLM模型信息"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            query = """
                SELECT * FROM llm_models
                WHERE is_active = 1
                ORDER BY provider, model_id
            """ if active_only else """
                SELECT * FROM llm_models
                ORDER BY provider, model_id
            """
            rows = conn.execute(query).fetchall()
            return [self._row_to_model_info(row) for row in rows]

    def get_model_by_id(self, provider: str, model_id: str) -> LLMModelInfo | None:
        """根据provider和model_id获取模型信息"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM llm_models WHERE provider = ? AND model_id = ?",
                (provider, model_id)
            ).fetchone()
            return self._row_to_model_info(row) if row else None

    def get_default_model_info(self) -> LLMModelInfo | None:
        """获取默认模型信息"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM llm_models WHERE is_default = 1"
            ).fetchone()
            return self._row_to_model_info(row) if row else None

    def get_display_models(self) -> list[LLMModelInfo]:
        """获取下拉菜单显示的模型（is_display=1）"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM llm_models WHERE is_display = 1 ORDER BY provider, model_id"
            ).fetchall()
            return [self._row_to_model_info(row) for row in rows]

    def set_default_model(self, provider: str, model_id: str) -> None:
        """设置默认模型"""
        with sqlite3.connect(str(self.db_path)) as conn:
            # 清除所有默认标记
            conn.execute("UPDATE llm_models SET is_default = 0")
            # 设置新的默认模型
            conn.execute(
                "UPDATE llm_models SET is_default = 1 WHERE provider = ? AND model_id = ?",
                (provider, model_id)
            )
            conn.commit()

    def _row_to_model_info(self, row: sqlite3.Row) -> LLMModelInfo:
        """将数据库行转换为LLMModelInfo对象"""
        return LLMModelInfo(
            id=row["id"],
            provider=row["provider"],
            model_id=row["model_id"],
            display_name=row["display_name"],
            alias=row["alias"],
            price_input=row["price_input"],
            price_output=row["price_output"],
            rpm_limit_tier1=row["rpm_limit_tier1"],
            rpm_limit_tier2=row["rpm_limit_tier2"],
            rpm_limit_tier3=row["rpm_limit_tier3"],
            rpm_limit_tier4=row["rpm_limit_tier4"],
            rpm_limit_tier5=row["rpm_limit_tier5"],
            tpm_limit_tier1=row["tpm_limit_tier1"],
            tpm_limit_tier2=row["tpm_limit_tier2"],
            tpm_limit_tier3=row["tpm_limit_tier3"],
            tpm_limit_tier4=row["tpm_limit_tier4"],
            tpm_limit_tier5=row["tpm_limit_tier5"],
            itpm_limit_tier1=row["itpm_limit_tier1"],
            itpm_limit_tier2=row["itpm_limit_tier2"],
            itpm_limit_tier3=row["itpm_limit_tier3"],
            itpm_limit_tier4=row["itpm_limit_tier4"],
            itpm_limit_tier5=row["itpm_limit_tier5"],
            otpm_limit_tier1=row["otpm_limit_tier1"],
            otpm_limit_tier2=row["otpm_limit_tier2"],
            otpm_limit_tier3=row["otpm_limit_tier3"],
            otpm_limit_tier4=row["otpm_limit_tier4"],
            otpm_limit_tier5=row["otpm_limit_tier5"],
            is_active=bool(row["is_active"]),
            is_default=bool(row["is_default"]),
            is_display=bool(row["is_display"]),
        )

    def get_model_code_mappings(self) -> tuple[dict[str, str], dict[str, str]]:
        """从数据库获取模型代码映射（替代硬编码字典）

        Returns:
            tuple: (model_to_code, code_to_model)
                - model_to_code: {model_id: alias}
                - code_to_model: {alias: model_id}
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT model_id, alias
                FROM llm_models
                WHERE alias IS NOT NULL AND alias != ''
            """)
            rows = cursor.fetchall()

            model_to_code = {row["model_id"]: row["alias"] for row in rows}
            code_to_model = {row["alias"]: row["model_id"] for row in rows}

            return model_to_code, code_to_model

    def get_providers_list(self) -> list[tuple[str, str]]:
        """从数据库获取提供商列表（替代硬编码列表）

        Returns:
            list: [(display_name, provider_value), ...]
                例如：[("OpenAI", "openai"), ("Anthropic", "anthropic")]
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("""
                SELECT DISTINCT provider FROM llm_models ORDER BY provider
            """)
            providers = cursor.fetchall()

            # 返回格式：[(display_name, value), ...]
            return [(p[0].title(), p[0].lower()) for p in providers]

    def get_provider_display_name(self, provider: str) -> str:
        """获取提供商的显示名称

        Args:
            provider: 提供商标识（如 "openai"）

        Returns:
            str: 显示名称（如 "OpenAI"）
        """
        return provider.title()

    def get_batch_config(self) -> dict[str, Any]:
        """获取批处理配置（从数据库读取，替代硬编码）

        Returns:
            dict: 包含批处理配置的字典
                - batch_timezone: str
                - max_batch_runs_per_day: int
                - reanimator_term_list_version: str
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT key, value FROM config
                WHERE key IN ('batch_timezone', 'max_batch_runs_per_day', 'reanimator_term_list_version')
            """)
            rows = cursor.fetchall()

            config = {row["key"]: row["value"] for row in rows}

            # 转换类型并提供默认值
            return {
                "batch_timezone": config.get("batch_timezone", "America/New_York"),
                "max_batch_runs_per_day": int(config.get("max_batch_runs_per_day", "26")),
                "reanimator_term_list_version": config.get("reanimator_term_list_version", "v1"),
            }

    def get_retry_config(self) -> dict[str, Any]:
        """获取重试策略配置（从数据库读取，替代硬编码）

        Returns:
            dict: 包含重试配置的字典
                - rate_limit_max_retries: int
                - rate_limit_base_delay: int
                - rate_limit_max_wait: int
                - other_error_retry_delay: int
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT key, value FROM config
                WHERE key IN ('rate_limit_max_retries', 'rate_limit_base_delay',
                             'rate_limit_max_wait', 'other_error_retry_delay')
            """)
            rows = cursor.fetchall()

            config = {row["key"]: row["value"] for row in rows}

            # 转换类型并提供默认值
            return {
                "rate_limit_max_retries": int(config.get("rate_limit_max_retries", "100")),
                "rate_limit_base_delay": int(config.get("rate_limit_base_delay", "15")),
                "rate_limit_max_wait": int(config.get("rate_limit_max_wait", "120")),
                "other_error_retry_delay": int(config.get("other_error_retry_delay", "2")),
            }

    def get_provider_config(self) -> dict[str, Any]:
        """获取提供商特定配置（从数据库读取，替代硬编码）

        Returns:
            dict: 包含提供商配置的字典
                - anthropic_max_tokens: int
                - openai_max_retries: int
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT key, value FROM config
                WHERE key IN ('anthropic_max_tokens', 'openai_max_retries')
            """)
            rows = cursor.fetchall()

            config = {row["key"]: row["value"] for row in rows}

            # 转换类型并提供默认值
            return {
                "anthropic_max_tokens": int(config.get("anthropic_max_tokens", "16384")),
                "openai_max_retries": int(config.get("openai_max_retries", "2")),
            }
