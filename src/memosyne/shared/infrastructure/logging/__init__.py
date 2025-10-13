"""Shared Logging Infrastructure"""
import sys
from pathlib import Path

_parent = Path(__file__).resolve().parents[3]
if str(_parent) not in sys.path:
    sys.path.insert(0, str(_parent))

from memosyne.utils.logger import get_logger, setup_logger

__all__ = ["get_logger", "setup_logger"]
