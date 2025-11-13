"""
Shared lookup database (library.db).

Currently stores reanimator_fieldterms (FieldEn -> FieldZh) derived from
the historical db/term_list_v1.csv file. Future reference tables for
other modules can be colocated here.
"""

from __future__ import annotations

import csv
import sqlite3
from pathlib import Path
from typing import Dict, Iterable, Tuple


class SQLiteLibraryRepository:
    """Simple helper around library.db."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._ensure_db_exists()

    def _ensure_db_exists(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reanimator_fieldterms (
                    field_en TEXT PRIMARY KEY,
                    field_zh TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def seed_field_terms_from_csv(self, csv_path: Path) -> None:
        """Populate reanimator_fieldterms if empty."""
        if not csv_path.exists():
            return

        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM reanimator_fieldterms")
            if cursor.fetchone()[0]:
                return

            rows: Iterable[Tuple[str, str]] = []
            with open(csv_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                rows = [
                    ((row.get("en") or "").strip().lower(), (row.get("cn") or "").strip())
                    for row in reader
                ]

            rows = [(en, zh) for en, zh in rows if en and zh]
            if rows:
                cursor.executemany(
                    """
                    INSERT OR IGNORE INTO reanimator_fieldterms (field_en, field_zh)
                    VALUES (?, ?)
                    """,
                    rows,
                )
                conn.commit()

    def get_field_terms(self) -> Dict[str, str]:
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT field_en, field_zh FROM reanimator_fieldterms")
            return {row[0]: row[1] for row in cursor.fetchall()}


_library_repo_instance: SQLiteLibraryRepository | None = None


def get_library_repository(db_path: Path | None = None) -> SQLiteLibraryRepository:
    global _library_repo_instance
    if _library_repo_instance is None:
        if db_path is None:
            raise ValueError("db_path is required for first call to get_library_repository")
        _library_repo_instance = SQLiteLibraryRepository(db_path)
        seed_source = db_path.parent / "term_list_v1.csv"
        _library_repo_instance.seed_field_terms_from_csv(seed_source)
    return _library_repo_instance


__all__ = ["SQLiteLibraryRepository", "get_library_repository"]
