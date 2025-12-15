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
    DEFAULT_PROMPT_VERSION as LITHO_PROMPT_VERSION,
    DEFAULT_PROMPTS as LITHO_DEFAULT_PROMPTS,
)
from ...reanimator.infrastructure.prompt_defaults import (
    DEFAULT_PROMPT_VERSION as REANIMATOR_PROMPT_VERSION,
    DEFAULT_PROMPTS as REANIMATOR_DEFAULT_PROMPTS,
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
                        (section, LITHO_PROMPT_VERSION, content)
                        for section, content in LITHO_DEFAULT_PROMPTS.items()
                    ],
                )

            # v1.9.2: 迁移旧的lithoformer_bank表结构（从id主键改为question_number主键）
            self._migrate_bank_table_if_needed(cursor)

            # ===== Reanimator 相关表（v0.16.0+） =====

            # 创建表5: reanimator_processing_logs（处理日志）
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS reanimator_processing_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    word_id TEXT NOT NULL,
                    wm_pair TEXT NOT NULL,
                    word_en TEXT NOT NULL,
                    mean_zh TEXT NOT NULL,
                    model TEXT NOT NULL,
                    batch_id TEXT NOT NULL,
                    batch_note TEXT,
                    have_def_en INTEGER DEFAULT 0,
                    have_example INTEGER DEFAULT 0,
                    have_rarity INTEGER DEFAULT 0,
                    have_field INTEGER DEFAULT 0,
                    note TEXT,
                    pos TEXT,
                    ipa TEXT,
                    etymo_en TEXT,
                    etymo_zh TEXT,
                    picture TEXT,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    processing_time REAL,
                    has_error BOOLEAN DEFAULT 0,
                    timestamp TEXT NOT NULL
                )
                """
            )

            # 创建表6: reanimator_bank（术语库）
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS reanimator_bank (
                    word_id TEXT PRIMARY KEY,
                    batch_id TEXT NOT NULL,
                    model TEXT NOT NULL,
                    wm_pair TEXT NOT NULL,
                    word_en TEXT NOT NULL,
                    mean_zh TEXT NOT NULL,
                    def_en TEXT,
                    example TEXT,
                    rarity TEXT,
                    field TEXT,
                    batch_note TEXT,
                    ipa TEXT,
                    pos TEXT,
                    etymo_en TEXT,
                    etymo_zh TEXT,
                    picture TEXT,
                    no_overwrite INTEGER DEFAULT 0,
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
                cursor.executemany(
                    """
                    INSERT INTO reanimator_prompts (section, version, content)
                    VALUES (?, ?, ?)
                    """,
                    [
                        (section, REANIMATOR_PROMPT_VERSION, content)
                        for section, content in REANIMATOR_DEFAULT_PROMPTS.items()
                    ],
                )

            # 确保最新版本的 prompt 被写入（幂等，不覆盖旧版本）
            self._seed_prompt_versions(cursor)

            # 迁移旧版 Reanimator 表结构（如有）
            self._migrate_reanimator_processing_logs_if_needed(cursor)
            self._migrate_reanimator_bank_table_if_needed(cursor)

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

    def _migrate_reanimator_processing_logs_if_needed(self, cursor) -> None:
        """迁移旧版 reanimator_processing_logs 表到新结构（使用 word_id 等字段）"""
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='reanimator_processing_logs'"
        )
        if not cursor.fetchone():
            return

        cursor.execute("PRAGMA table_info(reanimator_processing_logs)")
        columns = {row[1]: row for row in cursor.fetchall()}

        # 如果已经包含新字段 word_id，视为新结构
        if "word_id" in columns:
            return

        import logging

        logger = logging.getLogger("memosyne.shared.infrastructure.stats_db")
        logger.info("检测到旧版 reanimator_processing_logs 表结构，开始迁移...")

        # 重命名旧表
        cursor.execute(
            "ALTER TABLE reanimator_processing_logs RENAME TO reanimator_processing_logs_old"
        )

        # 创建新表（与 _ensure_db_exists 中的定义保持一致）
        cursor.execute(
            """
            CREATE TABLE reanimator_processing_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word_id TEXT NOT NULL,
                wm_pair TEXT NOT NULL,
                word_en TEXT NOT NULL,
                mean_zh TEXT NOT NULL,
                model TEXT NOT NULL,
                batch_id TEXT NOT NULL,
                batch_note TEXT,
                have_def_en INTEGER DEFAULT 0,
                have_example INTEGER DEFAULT 0,
                have_rarity INTEGER DEFAULT 0,
                have_field INTEGER DEFAULT 0,
                note TEXT,
                pos TEXT,
                ipa TEXT,
                etymo_en TEXT,
                etymo_zh TEXT,
                picture TEXT,
                input_tokens INTEGER,
                output_tokens INTEGER,
                processing_time REAL,
                has_error BOOLEAN DEFAULT 0,
                timestamp TEXT NOT NULL
            )
            """
        )

        # 从旧表迁移数据到新表：
        # - memo_id -> word_id
        # - word -> word_en
        # - zh_def -> mean_zh
        cursor.execute(
            """
            INSERT INTO reanimator_processing_logs (
                word_id,
                wm_pair,
                word_en,
                mean_zh,
                model,
                batch_id,
                batch_note,
                have_def_en,
                have_example,
                have_rarity,
                have_field,
                note,
                pos,
                ipa,
                etymo_en,
                etymo_zh,
                picture,
                input_tokens,
                output_tokens,
                processing_time,
                has_error,
                timestamp
            )
            SELECT
                memo_id AS word_id,
                wm_pair,
                word AS word_en,
                zh_def AS mean_zh,
                model,
                batch_id,
                NULL AS batch_note,
                0 AS have_def_en,
                0 AS have_example,
                0 AS have_rarity,
                0 AS have_field,
                NULL AS note,
                NULL AS pos,
                NULL AS ipa,
                NULL AS etymo_en,
                NULL AS etymo_zh,
                NULL AS picture,
                input_tokens,
                output_tokens,
                processing_time,
                has_error,
                timestamp
            FROM reanimator_processing_logs_old
            """
        )

        # 删除旧表
        cursor.execute("DROP TABLE reanimator_processing_logs_old")

        logger.info("reanimator_processing_logs 表结构迁移完成")

    def _migrate_reanimator_bank_table_if_needed(self, cursor) -> None:
        """迁移旧版 reanimator_bank 表到新结构（以 word_id 为主键）"""
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='reanimator_bank'"
        )
        if not cursor.fetchone():
            return

        cursor.execute("PRAGMA table_info(reanimator_bank)")
        columns = {row[1]: row for row in cursor.fetchall()}

        # 如果已经包含新字段 word_id，视为新结构
        if "word_id" in columns:
            return

        import logging

        logger = logging.getLogger("memosyne.shared.infrastructure.stats_db")
        logger.info("检测到旧版 reanimator_bank 表结构，开始迁移...")

        # 重命名旧表
        cursor.execute("ALTER TABLE reanimator_bank RENAME TO reanimator_bank_old")

        # 创建新表（与 _ensure_db_exists 中的定义保持一致）
        cursor.execute(
            """
            CREATE TABLE reanimator_bank (
                word_id TEXT PRIMARY KEY,
                batch_id TEXT NOT NULL,
                model TEXT NOT NULL,
                wm_pair TEXT NOT NULL,
                word_en TEXT NOT NULL,
                mean_zh TEXT NOT NULL,
                def_en TEXT,
                example TEXT,
                rarity TEXT,
                field TEXT,
                batch_note TEXT,
                ipa TEXT,
                pos TEXT,
                etymo_en TEXT,
                etymo_zh TEXT,
                picture TEXT,
                no_overwrite INTEGER DEFAULT 0,
                timestamp TEXT NOT NULL
            )
            """
        )

        # 从旧表迁移数据到新表：
        # - memo_id -> word_id
        # - word -> word_en
        # - zh_def -> mean_zh
        # - en_def -> def_en
        # - tag -> field
        # - pp_fix/pp_means -> etymo_en/etymo_zh
        cursor.execute(
            """
            INSERT INTO reanimator_bank (
                word_id,
                batch_id,
                model,
                wm_pair,
                word_en,
                mean_zh,
                def_en,
                example,
                rarity,
                field,
                batch_note,
                ipa,
                pos,
                etymo_en,
                etymo_zh,
                picture,
                no_overwrite,
                timestamp
            )
            SELECT
                memo_id AS word_id,
                batch_id,
                model,
                wm_pair,
                word AS word_en,
                zh_def AS mean_zh,
                en_def AS def_en,
                example,
                rarity,
                tag AS field,
                batch_note,
                ipa,
                pos,
                pp_fix AS etymo_en,
                pp_means AS etymo_zh,
                '' AS picture,
                0 AS no_overwrite,
                timestamp
            FROM reanimator_bank_old
            """
        )

        # 删除旧表
        cursor.execute("DROP TABLE reanimator_bank_old")

        logger.info("reanimator_bank 表结构迁移完成")

    def _seed_prompt_versions(self, cursor) -> None:
        """
        将当前代码中的默认 prompt 版本写入数据库（INSERT OR IGNORE，保持幂等）。
        即使表已存在旧版本，也会补齐最新版本，读取时仍按 MAX(version) 取最新。
        """
        self._upsert_prompt_set(
            cursor=cursor,
            table="lithoformer_prompts",
            version=LITHO_PROMPT_VERSION,
            prompts=LITHO_DEFAULT_PROMPTS,
        )
        self._upsert_prompt_set(
            cursor=cursor,
            table="reanimator_prompts",
            version=REANIMATOR_PROMPT_VERSION,
            prompts=REANIMATOR_DEFAULT_PROMPTS,
        )

    @staticmethod
    def _upsert_prompt_set(*, cursor, table: str, version: str, prompts: dict[str, str]) -> None:
        cursor.executemany(
            f"""
            INSERT OR IGNORE INTO {table} (section, version, content)
            VALUES (?, ?, ?)
            """,
            [(section, version, content) for section, content in prompts.items()],
        )

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

    def get_lithoformer_bank(self, limit: int | None = None) -> list[dict]:
        """获取最近的 Lithoformer 题库记录（用于命令面板预览）"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            if limit:
                cursor = conn.execute(
                    """
                    SELECT question_number, batch_id, model, output, timestamp
                    FROM lithoformer_bank
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT question_number, batch_id, model, output, timestamp
                    FROM lithoformer_bank
                    ORDER BY timestamp DESC
                    """
                )
            return [dict(row) for row in cursor.fetchall()]

    def save_terminal_log(
        self,
        log_type: str,
        message: str,
        logger: str = "",
        domain: str = "lithoformer",
    ) -> None:
        """
        保存终端日志到对应子域的 terminal_logs 表

        Args:
            log_type: 日志类型（INFO/WARNING/ERROR等）
            message: 日志消息
            logger: 触发日志的 logger 名称
            domain: "lithoformer" 或 "reanimator"
        """
        timestamp = datetime.now().isoformat()
        if domain not in {"lithoformer", "reanimator"}:
            raise ValueError(f"Unsupported domain for terminal logs: {domain}")
        table = "lithoformer_terminal_logs" if domain == "lithoformer" else "reanimator_terminal_logs"

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                f"""
                INSERT INTO {table} (timestamp, log_type, logger, message)
                VALUES (?, ?, ?, ?)
                """,
                (timestamp, log_type, logger, message),
            )
            conn.commit()

    def get_prompt_sections(self, version: str | None = None, domain: str = "lithoformer") -> dict[str, str]:
        """
        获取指定版本（或最新版本）的 prompt 片段。

        Args:
            version: 版本号（如 "0001"）。为空时自动使用最新版本。

        Returns:
            section -> content 的字典。

        Raises:
            ValueError: 当表中没有记录或指定版本不存在时抛出。
        """
        table = "lithoformer_prompts" if domain == "lithoformer" else "reanimator_prompts"
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            if version is None:
                cursor = conn.execute(
                    f"""
                    SELECT section, content
                    FROM {table}
                    WHERE version = (
                        SELECT MAX(version) FROM {table}
                    )
                    """
                )
            else:
                cursor = conn.execute(
                    f"""
                    SELECT section, content
                    FROM {table}
                    WHERE version = ?
                    """,
                    (version,),
                )
            rows = cursor.fetchall()

        if not rows:
            raise ValueError(f"{table} 表中没有可用的 prompt 记录")
        return {row["section"]: row["content"] for row in rows}

    def upsert_prompt_sections(self, *, domain: str, version: str, sections: dict[str, str]) -> None:
        """
        插入新的 prompt 版本（幂等，不覆盖已有版本）。

        Args:
            domain: "lithoformer" 或 "reanimator"
            version: 版本号（如 "0002"）
            sections: section -> content
        """
        if domain not in {"lithoformer", "reanimator"}:
            raise ValueError(f"Unsupported domain for prompts: {domain}")
        table = "lithoformer_prompts" if domain == "lithoformer" else "reanimator_prompts"

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.executemany(
                f"""
                INSERT OR IGNORE INTO {table} (section, version, content)
                VALUES (?, ?, ?)
                """,
                [(section, version, content) for section, content in sections.items()],
            )
            conn.commit()

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

    # ------------------------------------------------------------------
    # Reanimator helpers
    # ------------------------------------------------------------------
    def save_reanimator_processing_log(
        self,
        *,
        word_id: str,
        wm_pair: str,
        word_en: str,
        mean_zh: str,
        model: str,
        batch_id: str,
        batch_note: str,
        have_def_en: bool,
        have_example: bool,
        have_rarity: bool,
        have_field: bool,
        note: str,
        pos: str,
        ipa: str,
        etymo_en: str,
        etymo_zh: str,
        picture: str,
        input_tokens: int | None,
        output_tokens: int | None,
        processing_time: float | None,
        has_error: bool,
    ) -> None:
        timestamp = datetime.now().isoformat()
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                INSERT INTO reanimator_processing_logs (
                    word_id, wm_pair, word_en, mean_zh, model, batch_id, batch_note,
                    have_def_en, have_example, have_rarity, have_field, note, pos, ipa,
                    etymo_en, etymo_zh, picture, input_tokens, output_tokens,
                    processing_time, has_error, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    word_id,
                    wm_pair,
                    word_en,
                    mean_zh,
                    model,
                    batch_id,
                    batch_note,
                    int(have_def_en),
                    int(have_example),
                    int(have_rarity),
                    int(have_field),
                    note,
                    pos,
                    ipa,
                    etymo_en,
                    etymo_zh,
                    picture,
                    input_tokens,
                    output_tokens,
                    processing_time,
                    int(has_error),
                    timestamp,
                ),
            )
            conn.commit()

    def save_reanimator_bank(
        self,
        *,
        word_id: str,
        batch_id: str,
        model: str,
        wm_pair: str,
        word_en: str,
        mean_zh: str,
        def_en: str,
        example: str,
        rarity: str,
        field: str,
        batch_note: str,
        ipa: str,
        pos: str,
        etymo_en: str,
        etymo_zh: str,
        picture: str,
        no_overwrite: bool,
    ) -> bool:
        timestamp = datetime.now().isoformat()
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT no_overwrite FROM reanimator_bank WHERE word_id = ?",
                (word_id,),
            )
            row = cursor.fetchone()
            if row and row[0]:
                return False

            cursor.execute(
                """
                INSERT OR REPLACE INTO reanimator_bank (
                    word_id, batch_id, model, wm_pair, word_en, mean_zh,
                    def_en, example, rarity, field, batch_note, ipa, pos,
                    etymo_en, etymo_zh, picture, no_overwrite, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    word_id,
                    batch_id,
                    model,
                    wm_pair,
                    word_en,
                    mean_zh,
                    def_en,
                    example,
                    rarity,
                    field,
                    batch_note,
                    ipa,
                    pos,
                    etymo_en,
                    etymo_zh,
                    picture,
                    int(no_overwrite),
                    timestamp,
                ),
            )
            conn.commit()
            return True

    def reanimator_word_exists(self, word_id: str) -> bool:
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM reanimator_bank WHERE word_id = ?",
                (word_id,),
            )
            return cursor.fetchone() is not None

    def get_reanimator_entry(self, word_id: str) -> dict | None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM reanimator_bank WHERE word_id = ?",
                (word_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_reanimator_bank(self, limit: int | None = None) -> list[dict]:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            if limit:
                cursor = conn.execute(
                    """
                    SELECT * FROM reanimator_bank
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM reanimator_bank ORDER BY timestamp DESC"
                )
            return [dict(row) for row in cursor.fetchall()]

    def get_max_reanimator_word_id(self) -> str | None:
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("SELECT MAX(word_id) FROM reanimator_bank")
            row = cursor.fetchone()
            return row[0] if row and row[0] else None


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
