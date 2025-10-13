"""Lithoformer Infrastructure - File Adapter"""
from pathlib import Path


class FileAdapter:
    """File adapter (implements FileRepositoryPort)"""

    def read_markdown(self, path: Path) -> str:
        """Read markdown file"""
        return path.read_text(encoding="utf-8")

    def write_text(self, path: Path, content: str) -> None:
        """Write text file"""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    @classmethod
    def create(cls) -> "FileAdapter":
        return cls()
