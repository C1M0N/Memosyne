"""Data access layer - Repositories"""

from .csv_repository import CSVTermRepository
from .term_list_repository import TermListRepo

__all__ = [
    "CSVTermRepository",
    "TermListRepo",
]
