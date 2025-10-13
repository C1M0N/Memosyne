"""
Shared Configuration

Provides application-wide configuration management using Pydantic Settings.

Following DDD principles:
- Configuration as a cross-cutting concern
- Environment-based settings (12-factor app)
- Validation at startup
"""
from .settings import Settings, get_settings

__all__ = [
    "Settings",
    "get_settings",
]
