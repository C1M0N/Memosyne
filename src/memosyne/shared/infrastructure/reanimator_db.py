"""
Reanimator 数据库适配器 - SQLite 实现 (v0.16.0)

职责：
- 管理 reanimator_processing_logs 表（处理日志）
- 管理 reanimator_bank 表（术语库）
- 管理 reanimator_terminal_logs 表（终端日志）
- 管理 reanimator_prompts 表（Prompt 版本）
- 管理 reanimator_terms 表（术语表映射）
"""

import sqlite3
from datetime import datetime
from pathlib import Path


class SQLiteReanimatorRepository:
    """
    SQLite Reanimator 仓储实现 (v0.16.0)

    管理五个表：
    - reanimator_processing_logs: 处理日志
    - reanimator_bank: 术语库（wm_pair 为主键）
    - reanimator_terminal_logs: 终端日志
    - reanimator_prompts: Prompt 版本存储
    - reanimator_terms: 术语表映射
    """

    def __init__(self, db_path: Path):
        """
        初始化 Reanimator 仓储

        Args:
            db_path: 数据库文件路径（stat.db）
        """
        self.db_path = db_path

    def save_processing_log(
        self,
        memo_id: str,
        wm_pair: str,
        word: str,
        zh_def: str,
        model: str,
        batch_id: str,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        processing_time: float | None = None,
        has_error: bool = False,
    ) -> None:
        """
        保存处理日志到 reanimator_processing_logs 表

        Args:
            memo_id: 术语 ID（M000001）
            wm_pair: 词义对（word - zh_def）
            word: 英文单词
            zh_def: 中文释义
            model: 使用的模型
            batch_id: 批次号（YYMMDDX###）
            input_tokens: 输入 tokens 数
            output_tokens: 输出 tokens 数
            processing_time: 处理时间（秒）
            has_error: 是否发生错误
        """
        timestamp = datetime.now().isoformat()

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                INSERT INTO reanimator_processing_logs (
                    memo_id, wm_pair, word, zh_def, model, batch_id,
                    input_tokens, output_tokens, processing_time,
                    has_error, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memo_id,
                    wm_pair,
                    word,
                    zh_def,
                    model,
                    batch_id,
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
        wm_pair: str,
        memo_id: str,
        word: str,
        zh_def: str,
        model: str,
        ipa: str = "",
        pos: str = "",
        tag: str = "",
        rarity: str = "",
        en_def: str = "",
        example: str = "",
        pp_fix: str = "",
        pp_means: str = "",
        batch_id: str = "",
        batch_note: str = "",
    ) -> bool:
        """
        保存到术语库（reanimator_bank 表）

        使用 INSERT OR REPLACE 策略，wm_pair 为主键

        Args:
            wm_pair: 词义对（主键，格式: word - zh_def）
            memo_id: 术语 ID（M000001）
            word: 英文单词
            zh_def: 中文释义
            model: 使用的模型
            ipa: 音标
            pos: 词性（n./vt./vi. 等）
            tag: 中文领域标签
            rarity: 稀有度标记（RARE 或空）
            en_def: 英文定义
            example: 例句
            pp_fix: 词根词缀
            pp_means: 词根含义
            batch_id: 批次号
            batch_note: 批次备注

        Returns:
            bool: 是否保存成功
        """
        timestamp = datetime.now().isoformat()

        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                # 使用 INSERT OR REPLACE 自动处理插入/更新
                # wm_pair 是主键，相同词义对会自动替换旧记录
                conn.execute(
                    """
                    INSERT OR REPLACE INTO reanimator_bank (
                        wm_pair, memo_id, word, zh_def, ipa, pos, tag, rarity,
                        en_def, example, pp_fix, pp_means, batch_id, batch_note,
                        model, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        wm_pair, memo_id, word, zh_def, ipa, pos, tag, rarity,
                        en_def, example, pp_fix, pp_means, batch_id, batch_note,
                        model, timestamp
                    )
                )
                conn.commit()
                return True
        except Exception:
            return False

    def get_existing_term(self, wm_pair: str) -> dict[str, str] | None:
        """
        获取术语库中已存在术语的详细信息（用于覆盖确认）

        Args:
            wm_pair: 词义对（word - zh_def）

        Returns:
            包含术语信息的字典，如果不存在则返回 None
            格式: {
                "wm_pair": "word - zh_def",
                "memo_id": "M000001",
                "pos": "n.",
                "tag": "心理学"
            }
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT wm_pair, memo_id, pos, tag FROM reanimator_bank WHERE wm_pair = ?",
                (wm_pair,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            return {
                "wm_pair": row[0],
                "memo_id": row[1],
                "pos": row[2] or "",
                "tag": row[3] or "",
            }

    def check_bank_exists(self, wm_pair: str) -> bool:
        """检查词义对是否已存在于术语库"""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM reanimator_bank WHERE wm_pair = ?",
                (wm_pair,)
            )
            return cursor.fetchone() is not None

    def get_max_memo_id(self) -> str | None:
        """
        获取术语库中最大的 Memo ID

        Returns:
            最大的 Memo ID（如 "M000123"），如果库为空则返回 None
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT MAX(memo_id) FROM reanimator_bank"
            )
            row = cursor.fetchone()
            return row[0] if row and row[0] else None

    def save_terminal_log(
        self,
        log_type: str,
        message: str,
        logger: str = "",
    ) -> None:
        """
        保存终端日志到 reanimator_terminal_logs 表

        Args:
            log_type: 日志类型（INFO/WARNING/ERROR 等）
            message: 日志消息
            logger: 触发日志的 logger 名称
        """
        timestamp = datetime.now().isoformat()

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                INSERT INTO reanimator_terminal_logs (timestamp, log_type, logger, message)
                VALUES (?, ?, ?, ?)
                """,
                (timestamp, log_type, logger, message),
            )
            conn.commit()

    def get_term_mapping(self) -> dict[str, str]:
        """
        获取术语表映射（英文标签 → 中文标签）

        从 reanimator_terms 表读取

        Returns:
            术语映射字典，格式: {"psychology": "心理学", "neuroscience": "神经科学", ...}
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT tag_en, tag_zh FROM reanimator_terms")
            return {row[0]: row[1] for row in cursor.fetchall()}

    def get_prompts(self, version: str | None = None) -> dict[str, str]:
        """
        获取指定版本（或最新版本）的 Reanimator prompt 片段

        Args:
            version: 版本号（如 "0001"）。为空时自动使用最新版本。

        Returns:
            section -> content 的字典
            格式: {"reanimator_system": "...", "reanimator_user": "..."}

        Raises:
            ValueError: 当表中没有记录或指定版本不存在时抛出
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            if version is None:
                cursor = conn.execute(
                    """
                    SELECT section, content
                    FROM reanimator_prompts
                    WHERE version = (
                        SELECT MAX(version) FROM reanimator_prompts
                    )
                    """
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT section, content
                    FROM reanimator_prompts
                    WHERE version = ?
                    """,
                    (version,),
                )
            rows = cursor.fetchall()

        if not rows:
            raise ValueError("reanimator_prompts 表中没有可用的 prompt 记录")
        return {row["section"]: row["content"] for row in rows}

    def get_all_terms_from_bank(self, limit: int | None = None) -> list[dict]:
        """
        获取术语库中的所有术语（用于显示和导出）

        Args:
            limit: 限制返回的术语数量，None 表示不限制

        Returns:
            术语列表，每项为字典，包含所有字段
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            if limit:
                cursor = conn.execute(
                    """
                    SELECT * FROM reanimator_bank
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (limit,)
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM reanimator_bank ORDER BY timestamp DESC"
                )

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def clear_bank(self) -> int:
        """
        清空术语库表（用于清理错误数据）

        Returns:
            删除的记录数
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM reanimator_bank")
            count = cursor.fetchone()[0]
            cursor.execute("DELETE FROM reanimator_bank")
            conn.commit()
            return count

    def clear_processing_logs(self, batch_id: str | None = None) -> int:
        """
        清空处理日志表（用于清理错误数据）

        Args:
            batch_id: 如果提供，只删除指定批次的记录；否则清空全表

        Returns:
            删除的记录数
        """
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            if batch_id:
                cursor.execute(
                    "SELECT COUNT(*) FROM reanimator_processing_logs WHERE batch_id = ?",
                    (batch_id,)
                )
                count = cursor.fetchone()[0]
                cursor.execute(
                    "DELETE FROM reanimator_processing_logs WHERE batch_id = ?",
                    (batch_id,)
                )
            else:
                cursor.execute("SELECT COUNT(*) FROM reanimator_processing_logs")
                count = cursor.fetchone()[0]
                cursor.execute("DELETE FROM reanimator_processing_logs")
            conn.commit()
            return count


# 全局单例
_reanimator_repo_instance: SQLiteReanimatorRepository | None = None


def get_reanimator_repository(db_path: Path | None = None):
    """
    获取 Reanimator 仓储单例

    Args:
        db_path: 数据库路径（仅首次调用时需要）

    Returns:
        SQLiteReanimatorRepository 实现
    """
    global _reanimator_repo_instance

    if _reanimator_repo_instance is None:
        if db_path is None:
            raise ValueError("db_path is required for first call to get_reanimator_repository")
        _reanimator_repo_instance = SQLiteReanimatorRepository(db_path)

    return _reanimator_repo_instance


__all__ = [
    "SQLiteReanimatorRepository",
    "get_reanimator_repository",
]
