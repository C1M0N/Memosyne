"""Application-level config aggregation service.

Unifies access to key/value config and feature flags from SQLite.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from ..config.app_config import FeatureFlags, RuntimeTuning, AppConfigBundle, LithoformerPaths


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
                "       feature_001, feature_002, feature_003"
                "  FROM feature WHERE id = 1"
            ).fetchone()
            if not row:
                return FeatureFlags()
            return FeatureFlags(
                enable_translation=bool(row["enable_translation"]),
                enable_parsing=bool(row["enable_parsing"]),
                enable_concurrent=bool(row["enable_concurrent"]),
                feature_001=bool(row["feature_001"]),
                feature_002=bool(row["feature_002"]),
                feature_003=bool(row["feature_003"]),
            )

    def update_feature_flags(self, **kwargs: bool) -> None:
        if not kwargs:
            return
        valid = {
            "enable_translation",
            "enable_parsing",
            "enable_concurrent",
            "feature_001",
            "feature_002",
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
        value = self.get_config("default_model")
        return value or "OpenAI::gpt-4o-mini"

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
