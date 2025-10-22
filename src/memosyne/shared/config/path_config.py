"""Path configuration loader for Memosyne."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_RELATIVE = Path("config/paths.json")


@dataclass(frozen=True)
class PathConfig:
    """Resolved path configuration."""

    project_root: Path
    base_dir: Path
    reanimator_input: Path
    reanimator_output: Path
    reanimator_templates: Path
    lithoformer_input: Path
    lithoformer_output: Path
    lithoformer_templates: Path

    @property
    def sample_root(self) -> Path:
        """Directory containing bundled, read-only samples."""
        return self.base_dir

    def is_within_samples(self, path: Path) -> bool:
        """Return True if the given path is inside the bundled sample tree."""
        try:
            return self.sample_root in path.resolve().parents or path.resolve() == self.sample_root
        except FileNotFoundError:
            # If the path does not exist yet, check via pure string comparison
            return str(path.resolve()).startswith(str(self.sample_root.resolve()))


class PathConfigError(RuntimeError):
    """Raised when path configuration cannot be loaded."""


_CACHED_CONFIG: PathConfig | None = None


def get_path_config(reload: bool = False) -> PathConfig:
    """Load and return the path configuration for the project."""
    global _CACHED_CONFIG
    if _CACHED_CONFIG is not None and not reload:
        return _CACHED_CONFIG

    project_root = _find_project_root()
    config_path = project_root / DEFAULT_CONFIG_RELATIVE
    data: dict[str, Any]

    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise PathConfigError(f"Failed to parse {config_path}: {exc}") from exc
    else:
        data = _default_config()

    base_dir = _resolve_path(project_root, data.get("base_dir", "misc"))
    reanimator = data.get("reanimator", {})
    lithoformer = data.get("lithoformer", {})

    _CACHED_CONFIG = PathConfig(
        project_root=project_root,
        base_dir=base_dir,
        reanimator_input=_resolve_path(base_dir, reanimator.get("input", "input/reanimator")),
        reanimator_output=_resolve_path(base_dir, reanimator.get("output", "output/reanimator")),
        reanimator_templates=_resolve_path(base_dir, reanimator.get("templates", "templates/reanimator")),
        lithoformer_input=_resolve_path(base_dir, lithoformer.get("input", "input/lithoformer")),
        lithoformer_output=_resolve_path(base_dir, lithoformer.get("output", "output/lithoformer")),
        lithoformer_templates=_resolve_path(base_dir, lithoformer.get("templates", "templates/lithoformer")),
    )

    return _CACHED_CONFIG


def _default_config() -> dict[str, Any]:
    return {
        "base_dir": "misc/example",
        "reanimator": {
            "input": "reanimator",
            "output": "../output/reanimator",
            "templates": "reanimator",
        },
        "lithoformer": {
            "input": "lithoformer",
            "output": "../output/lithoformer",
            "templates": "lithoformer",
        },
    }


def _resolve_path(base: Path, relative: str) -> Path:
    rel_path = Path(relative)
    if rel_path.is_absolute():
        return rel_path.resolve()
    return (base / rel_path).resolve()


def _find_project_root() -> Path:
    """Locate the project root using heuristics (presence of pyproject or src/)."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists() or (parent / "src").is_dir():
            return parent
    return Path.cwd()
