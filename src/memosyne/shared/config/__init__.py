"""Shared Configuration"""
import sys
from pathlib import Path

_parent = Path(__file__).resolve().parents[2]
if str(_parent) not in sys.path:
    sys.path.insert(0, str(_parent))

from memosyne.config import get_settings, Settings

__all__ = ["get_settings", "Settings"]
