"""
统计数据库适配器 - SQLite 实现 (v1.9.0重构版)

职责：
- 管理lithoformer_processing_logs表（处理日志）
- 管理lithoformer_bank表（题库）
- 管理lithoformer_terminal_logs表（终端日志）
"""

import sqlite3
from datetime import datetime
from pathlib import Path


class SQLiteStatsRepository:
    """
    SQLite 统计仓储实现 (v1.9.0重构版)

    管理三个新表：
    - lithoformer_processing_logs: 处理日志（两阶段记录）
    - lithoformer_bank: 题库
    - lithoformer_terminal_logs: 终端日志
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

        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # 删除旧表（保留llm_models等其他表）
            cursor.execute("DROP TABLE IF EXISTS processing_stats")

            # 创建新表1: lithoformer_processing_logs（处理日志）
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS lithoformer_processing_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_number TEXT NOT NULL,
                    batch_id TEXT NOT NULL,
                    model TEXT NOT NULL,
                    input_char_count INTEGER,
                    use_translation BOOLEAN,
                    use_parsing BOOLEAN,
                    note TEXT,
                    question_type TEXT,
                    output_char_count INTEGER,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    processing_time REAL,
                    has_error BOOLEAN DEFAULT 0,
                    timestamp TEXT NOT NULL
                )
                """
            )

            # 创建新表2: lithoformer_bank（题库）
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS lithoformer_bank (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_number TEXT UNIQUE NOT NULL,
                    batch_id TEXT,
                    model TEXT,
                    use_translation BOOLEAN,
                    use_parsing BOOLEAN,
                    use_answer BOOLEAN DEFAULT 0,
                    original_input TEXT,
                    output TEXT,
                    no_overwrite BOOLEAN DEFAULT 0,
                    timestamp TEXT NOT NULL
                )
                """
            )

            # 创建新表3: lithoformer_terminal_logs（终端日志）
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS lithoformer_terminal_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    log_type TEXT NOT NULL,
                    message TEXT
                )
                """
            )

            conn.commit()

    def save_processing_log(
        self,
        question_number: str,
        batch_id: str,
        model: str,
        input_char_count: int,
        use_translation: bool,
        use_parsing: bool,
        note: str = "",
        question_type: str | None = None,
        output_char_count: int | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        processing_time: float | None = None,
        has_error: bool = False,
    ) -> None:
        """
        保存处理日志到lithoformer_processing_logs表

        Args:
            question_number: 题号
            batch_id: 批次号
            model: 使用的模型
            input_char_count: 输入字符数
            use_translation: 是否使用翻译
            use_parsing: 是否使用解析
            note: 备注信息
            question_type: 题型（处理完成后填充）
            output_char_count: 输出字符数（处理完成后填充）
            input_tokens: 输入tokens数（处理完成后填充）
            output_tokens: 输出tokens数（处理完成后填充）
            processing_time: 处理时间（处理完成后填充）
            has_error: 是否发生错误
        """
        timestamp = datetime.now().isoformat()

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                INSERT INTO lithoformer_processing_logs (
                    question_number, batch_id, model, input_char_count,
                    use_translation, use_parsing, note,
                    question_type, output_char_count,
                    input_tokens, output_tokens, processing_time,
                    has_error, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    question_number,
                    batch_id,
                    model,
                    input_char_count,
                    use_translation,
                    use_parsing,
                    note,
                    question_type,
                    output_char_count,
                    input_tokens,
                    output_tokens,
                    processing_time,
                    has_error,
                    timestamp,
                ),
            )
            conn.commit()

    def save_to_bank(
        self,
        question_number: str,
        batch_id: str,
        model: str,
        use_translation: bool,
        use_parsing: bool,
        original_input: str,
        output: str,
        no_overwrite: bool = False,
    ) -> bool:
        """
        保存到题库（lithoformer_bank表）

        Args:
            question_number: 题号（唯一键）
            batch_id: 批次号
            model: 使用的模型
            use_translation: 是否使用翻译
            use_parsing: 是否使用解析
            original_input: 原始输入
            output: 输出结果
            no_overwrite: 禁止覆盖标记

        Returns:
            bool: 是否保存成功
        """
        timestamp = datetime.now().isoformat()

        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # 检查是否已存在
            cursor.execute(
                "SELECT no_overwrite FROM lithoformer_bank WHERE question_number = ?",
                (question_number,)
            )
            existing = cursor.fetchone()

            if existing:
                # 如果存在且设置了no_overwrite，拒绝覆盖
                if existing[0]:  # no_overwrite = True
                    return False

                # 否则更新记录
                cursor.execute(
                    """
                    UPDATE lithoformer_bank
                    SET batch_id = ?, model = ?, use_translation = ?, use_parsing = ?,
                        original_input = ?, output = ?, no_overwrite = ?, timestamp = ?
                    WHERE question_number = ?
                    """,
                    (batch_id, model, use_translation, use_parsing,
                     original_input, output, no_overwrite, timestamp, question_number)
                )
            else:
                # 插入新记录
                cursor.execute(
                    """
                    INSERT INTO lithoformer_bank (
                        question_number, batch_id, model, use_translation, use_parsing,
                        use_answer, original_input, output, no_overwrite, timestamp
                    ) VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
                    """,
                    (question_number, batch_id, model, use_translation, use_parsing,
                     original_input, output, no_overwrite, timestamp)
                )

            conn.commit()
            return True

    def check_bank_exists(self, question_number: str) -> bool:
        """检查题号是否已存在于题库"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM lithoformer_bank WHERE question_number = ?",
                (question_number,)
            )
            return cursor.fetchone() is not None

    def save_terminal_log(
        self,
        log_type: str,
        message: str,
    ) -> None:
        """
        保存终端日志到lithoformer_terminal_logs表

        Args:
            log_type: 日志类型（INFO/WARNING/ERROR等）
            message: 日志消息
        """
        timestamp = datetime.now().isoformat()

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                INSERT INTO lithoformer_terminal_logs (timestamp, log_type, message)
                VALUES (?, ?, ?)
                """,
                (timestamp, log_type, message),
            )
            conn.commit()


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
