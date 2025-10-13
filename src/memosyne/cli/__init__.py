"""CLI interface - 导出新架构的 CLI 入口点"""

from ..reanimator.cli.main import main as reanimator_main
from ..lithoformer.cli.main import main as lithoformer_main
from .prompts import ask

__all__ = ["reanimator_main", "lithoformer_main", "ask"]
