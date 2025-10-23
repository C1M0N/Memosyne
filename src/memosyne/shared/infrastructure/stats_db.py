"""
统计数据库适配器 - SQLite 实现

职责：
- 管理processing_stats表（处理统计数据）
- 记录每次题目处理的性能指标
- 提供时间预估功能
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


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
        self._ensure_db_exists()

    def _ensure_db_exists(self) -> None:
        """确保数据库文件和表结构存在"""
        # 确保目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # 创建表
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS processing_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_number TEXT,
                    model TEXT,
                    input_char_count INTEGER,
                    output_char_count INTEGER,
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

    def save_stat(
        self,
        question_number: str,
        model: str,
        input_char_count: int,
        output_char_count: int,
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
                    question_number, model, input_char_count, output_char_count,
                    use_translation, use_parsing,
                    original_text, output_text, output_filename,
                    processing_time, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    question_number,
                    model,
                    input_char_count,
                    output_char_count,
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
                    stat.get("input_char_count", 0),
                    stat.get("output_char_count", 0),
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
                    question_number, model, input_char_count, output_char_count,
                    use_translation, use_parsing,
                    original_text, output_text, output_filename,
                    processing_time, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                  AND input_char_count BETWEEN ? AND ?
                """,
                (model, use_translation, use_parsing, char_min, char_max),
            )
            row = cursor.fetchone()
            if row and row[0] is not None:
                return float(row[0])
            return None


# 全局单例
_stats_repo_instance: SQLiteStatsRepository | None = None


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
            raise ValueError("db_path is required for first call to get_stats_repository")
        _stats_repo_instance = SQLiteStatsRepository(db_path)

    return _stats_repo_instance
