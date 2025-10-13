"""
Shared Utilities

Provides cross-cutting utility functions and classes that can be reused
across different bounded contexts.

Following DDD principles:
- Utility layer, no domain logic
- Stateless helper functions
- Technical concerns only (paths, batching, formatting, logging)
"""
from .batch import BatchIDGenerator
from .path import unique_path, resolve_input_path
from .model_codes import (
    get_code_from_model,
    get_model_from_code,
    resolve_model_input,
    get_provider_from_model,
)
from .filename import extract_short_filename, generate_output_filename
from .logger import get_logger, setup_logger

__all__ = [
    "BatchIDGenerator",
    "unique_path",
    "resolve_input_path",
    "get_code_from_model",
    "get_model_from_code",
    "resolve_model_input",
    "get_provider_from_model",
    "extract_short_filename",
    "generate_output_filename",
    "get_logger",
    "setup_logger",
]
