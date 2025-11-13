"""Field term adapter backed by library.db."""
from __future__ import annotations

from pathlib import Path

from ...shared.infrastructure.library_db import get_library_repository


class TermListAdapter:
    def __init__(self, mapping: dict[str, str]):
        self._mapping = mapping

    @property
    def mapping(self) -> dict[str, str]:
        return self._mapping

    @classmethod
    def from_settings(cls, settings) -> "TermListAdapter":
        repo = get_library_repository(settings.db_dir / "library.db")
        return cls(mapping=repo.get_field_terms())

    @classmethod
    def from_path(cls, term_list_path: Path) -> "TermListAdapter":
        repo = get_library_repository(term_list_path.parent / "library.db")
        repo.seed_field_terms_from_csv(term_list_path)
        return cls(mapping=repo.get_field_terms())
