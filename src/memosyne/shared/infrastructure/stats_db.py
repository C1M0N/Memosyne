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

from ...lithoformer.infrastructure.prompt_defaults import (
    DEFAULT_PROMPT_VERSION,
    DEFAULT_PROMPTS,
)


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
            # v1.9.2: 使用question_number作为主键（而非id）
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS lithoformer_bank (
                    question_number TEXT PRIMARY KEY,
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
                    logger TEXT NOT NULL,
                    message TEXT
                )
                """
            )
            # 确保旧表具备 logger 列
            cursor.execute("PRAGMA table_info(lithoformer_terminal_logs)")
            terminal_columns = {row[1] for row in cursor.fetchall()}
            if "logger" not in terminal_columns:
                cursor.execute(
                    "ALTER TABLE lithoformer_terminal_logs ADD COLUMN logger TEXT NOT NULL DEFAULT ''"
                )

            # 创建新表4: lithoformer_prompts（Prompt 版本存储）
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS lithoformer_prompts (
                    section TEXT NOT NULL,
                    version TEXT NOT NULL,
                    content TEXT NOT NULL,
                    PRIMARY KEY (section, version)
                )
                """
            )

            # 若 prompt 表为空，写入默认版本
            cursor.execute("SELECT COUNT(*) FROM lithoformer_prompts")
            prompt_count = cursor.fetchone()[0]
            if prompt_count == 0:
                cursor.executemany(
                    """
                    INSERT INTO lithoformer_prompts (section, version, content)
                    VALUES (?, ?, ?)
                    """,
                    [
                        (section, DEFAULT_PROMPT_VERSION, content)
                        for section, content in DEFAULT_PROMPTS.items()
                    ],
                )

            # v1.9.2: 迁移旧的lithoformer_bank表结构（从id主键改为question_number主键）
            self._migrate_bank_table_if_needed(cursor)

            # ===== Reanimator 相关表（v0.16.0） =====

            # 创建表5: reanimator_processing_logs（处理日志）
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS reanimator_processing_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    memo_id TEXT NOT NULL,
                    wm_pair TEXT NOT NULL,
                    word TEXT NOT NULL,
                    zh_def TEXT NOT NULL,
                    model TEXT NOT NULL,
                    batch_id TEXT NOT NULL,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    processing_time REAL,
                    has_error BOOLEAN DEFAULT 0,
                    timestamp TEXT NOT NULL
                )
                """
            )

            # 创建表6: reanimator_bank（术语库，wm_pair 为主键）
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS reanimator_bank (
                    wm_pair TEXT PRIMARY KEY,
                    memo_id TEXT NOT NULL,
                    word TEXT NOT NULL,
                    zh_def TEXT NOT NULL,
                    ipa TEXT,
                    pos TEXT,
                    tag TEXT,
                    rarity TEXT,
                    en_def TEXT,
                    example TEXT,
                    pp_fix TEXT,
                    pp_means TEXT,
                    batch_id TEXT,
                    batch_note TEXT,
                    model TEXT,
                    timestamp TEXT NOT NULL
                )
                """
            )

            # 创建表7: reanimator_terminal_logs（终端日志）
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS reanimator_terminal_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    log_type TEXT NOT NULL,
                    logger TEXT NOT NULL,
                    message TEXT
                )
                """
            )

            # 创建表8: reanimator_prompts（Prompt 版本存储）
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS reanimator_prompts (
                    section TEXT NOT NULL,
                    version TEXT NOT NULL,
                    content TEXT NOT NULL,
                    PRIMARY KEY (section, version)
                )
                """
            )

            # 若 reanimator_prompts 表为空，写入默认版本
            cursor.execute("SELECT COUNT(*) FROM reanimator_prompts")
            reanimator_prompt_count = cursor.fetchone()[0]
            if reanimator_prompt_count == 0:
                # 从 reanimator/infrastructure/prompts.py 导入默认 prompts
                try:
                    from ...reanimator.infrastructure.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
                    DEFAULT_REANIMATOR_VERSION = "0001"
                    DEFAULT_REANIMATOR_PROMPTS = {
                        'reanimator_system': SYSTEM_PROMPT,
                        'reanimator_user': USER_PROMPT_TEMPLATE,
                    }
                    cursor.executemany(
                        """
                        INSERT INTO reanimator_prompts (section, version, content)
                        VALUES (?, ?, ?)
                        """,
                        [
                            (section, DEFAULT_REANIMATOR_VERSION, content)
                            for section, content in DEFAULT_REANIMATOR_PROMPTS.items()
                        ],
                    )
                except ImportError:
                    pass  # Prompts 文件可能还未创建，跳过初始化

            # 创建表9: reanimator_terms（术语表映射，数据库化）
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS reanimator_terms (
                    tag_en TEXT PRIMARY KEY,
                    tag_zh TEXT NOT NULL
                )
                """
            )

            # 若 reanimator_terms 表为空，从 CSV 导入
            cursor.execute("SELECT COUNT(*) FROM reanimator_terms")
            reanimator_terms_count = cursor.fetchone()[0]
            if reanimator_terms_count == 0:
                # 从 db/term_list_v1.csv 导入数据
                import csv
                term_list_path = self.db_path.parent / "term_list_v1.csv"
                if term_list_path.exists():
                    with open(term_list_path, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        terms_data = [(row['en'], row['cn']) for row in reader]
                        cursor.executemany(
                            """
                            INSERT INTO reanimator_terms (tag_en, tag_zh)
                            VALUES (?, ?)
                            """,
                            terms_data
                        )

            conn.commit()

    def _migrate_bank_table_if_needed(self, cursor) -> None:
        """迁移lithoformer_bank表：将id主键改为question_number主键（v1.9.2）"""
        # 检查表是否存在
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='lithoformer_bank'"
        )
        if not cursor.fetchone():
            return  # 表不存在，无需迁移

        # 检查表结构
        cursor.execute("PRAGMA table_info(lithoformer_bank)")
        columns = {row[1]: row for row in cursor.fetchall()}

        # 如果有id列且是主键（pk=1），说明是旧结构
        if "id" in columns and columns["id"][5] == 1:
            import logging
            logger = logging.getLogger("memosyne.shared.infrastructure.stats_db")
            logger.info("检测到旧版lithoformer_bank表结构，开始迁移...")

            # 步骤1: 创建新表
            cursor.execute(
                """
                CREATE TABLE lithoformer_bank_new (
                    question_number TEXT PRIMARY KEY,
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

            # 步骤2: 迁移数据（保留每个question_number的最新记录）
            cursor.execute(
                """
                INSERT INTO lithoformer_bank_new
                SELECT
                    question_number,
                    batch_id,
                    model,
                    use_translation,
                    use_parsing,
                    use_answer,
                    original_input,
                    output,
                    no_overwrite,
                    timestamp
                FROM lithoformer_bank
                WHERE id IN (
                    SELECT MAX(id)
                    FROM lithoformer_bank
                    GROUP BY question_number
                )
                """
            )

            # 步骤3: 删除旧表
            cursor.execute("DROP TABLE lithoformer_bank")

            # 步骤4: 重命名新表
            cursor.execute("ALTER TABLE lithoformer_bank_new RENAME TO lithoformer_bank")

            logger.info("lithoformer_bank表结构迁移完成")

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
        v1.9.2: 简化为使用INSERT OR REPLACE（question_number为主键）

        Args:
            question_number: 题号（主键）
            batch_id: 批次号
            model: 使用的模型
            use_translation: 是否使用翻译
            use_parsing: 是否使用解析
            original_input: 原始输入
            output: 输出结果
            no_overwrite: 禁止覆盖标记

        Returns:
            bool: 是否保存成功（如果已存在且no_overwrite=True则返回False）
        """
        timestamp = datetime.now().isoformat()

        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()

            # 检查是否已存在且设置了no_overwrite标记
            cursor.execute(
                "SELECT no_overwrite FROM lithoformer_bank WHERE question_number = ?",
                (question_number,)
            )
            existing = cursor.fetchone()

            if existing and existing[0]:  # 已存在且no_overwrite=True
                return False  # 拒绝覆盖

            # 使用INSERT OR REPLACE自动处理插入/更新
            # question_number是主键，相同题号会自动替换旧记录
            cursor.execute(
                """
                INSERT OR REPLACE INTO lithoformer_bank (
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

    def get_existing_question(self, question_number: str) -> dict[str, str] | None:
        """
        获取题库中已存在题目的详细信息（用于覆盖确认）

        Args:
            question_number: 题号

        Returns:
            包含题号、批次号、题干预览的字典，如果不存在则返回None
            格式: {
                "question_number": "L000001",
                "batch_id": "251105A015",
                "stem_preview": "Unlike fear, panic..."  # 前20个字符
            }
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT question_number, batch_id, output FROM lithoformer_bank WHERE question_number = ?",
                (question_number,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            question_number, batch_id, output_json = row

            # 解析output JSON提取stem字段
            stem_preview = ""
            try:
                import json
                output_data = json.loads(output_json)
                stem = output_data.get("stem", "")
                stem_preview = stem[:20] if stem else "(无题干)"
            except Exception:
                stem_preview = "(解析失败)"

            return {
                "question_number": question_number,
                "batch_id": batch_id,
                "stem_preview": stem_preview,
            }

    def save_terminal_log(
        self,
        log_type: str,
        message: str,
        logger: str = "",
    ) -> None:
        """
        保存终端日志到lithoformer_terminal_logs表

        Args:
            log_type: 日志类型（INFO/WARNING/ERROR等）
            message: 日志消息
            logger: 触发日志的 logger 名称
        """
        timestamp = datetime.now().isoformat()

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                INSERT INTO lithoformer_terminal_logs (timestamp, log_type, logger, message)
                VALUES (?, ?, ?, ?)
                """,
                (timestamp, log_type, logger, message),
            )
            conn.commit()

    def get_prompt_sections(self, version: str | None = None) -> dict[str, str]:
        """
        获取指定版本（或最新版本）的 prompt 片段。

        Args:
            version: 版本号（如 "0001"）。为空时自动使用最新版本。

        Returns:
            section -> content 的字典。

        Raises:
            ValueError: 当表中没有记录或指定版本不存在时抛出。
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            if version is None:
                cursor = conn.execute(
                    """
                    SELECT section, content
                    FROM lithoformer_prompts
                    WHERE version = (
                        SELECT MAX(version) FROM lithoformer_prompts
                    )
                    """
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT section, content
                    FROM lithoformer_prompts
                    WHERE version = ?
                    """,
                    (version,),
                )
            rows = cursor.fetchall()

        if not rows:
            raise ValueError("lithoformer_prompts 表中没有可用的 prompt 记录")
        return {row["section"]: row["content"] for row in rows}

    def clear_bank(self) -> int:
        """清空题库表（v1.9.1c：用于清理错误数据）

        Returns:
            删除的记录数
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM lithoformer_bank")
            count = cursor.fetchone()[0]
            cursor.execute("DELETE FROM lithoformer_bank")
            conn.commit()
            return count

    def clear_processing_logs(self, batch_id: str | None = None) -> int:
        """清空处理日志表（v1.9.1c：用于清理错误数据）

        Args:
            batch_id: 如果提供，只删除指定批次的记录；否则清空全表

        Returns:
            删除的记录数
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            if batch_id:
                cursor.execute(
                    "SELECT COUNT(*) FROM lithoformer_processing_logs WHERE batch_id = ?",
                    (batch_id,)
                )
                count = cursor.fetchone()[0]
                cursor.execute(
                    "DELETE FROM lithoformer_processing_logs WHERE batch_id = ?",
                    (batch_id,)
                )
            else:
                cursor.execute("SELECT COUNT(*) FROM lithoformer_processing_logs")
                count = cursor.fetchone()[0]
                cursor.execute("DELETE FROM lithoformer_processing_logs")
            conn.commit()
            return count


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
