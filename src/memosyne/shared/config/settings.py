"""配置管理模块 - 使用 Pydantic Settings 实现类型安全的配置。"""

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .path_config import get_path_config


def _find_project_root() -> Path:
    """查找项目根目录（优先以 .env 或 src/ 为参考）。"""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / ".env").exists():
            return parent
    for parent in current.parents:
        if (parent / "config" / "paths.json").exists() or (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd()


_PROJECT_ROOT = _find_project_root()
_PATH_CONFIG = get_path_config()


class Settings(BaseSettings):
    """应用配置（从环境变量加载）"""

    # === LLM API 配置 ===
    openai_api_key: str = Field(
        ...,  # 必填
        min_length=20,
        description="OpenAI API 密钥"
    )
    anthropic_api_key: str | None = Field(
        None,
        min_length=20,
        description="Anthropic API 密钥（可选）"
    )

    # === 默认模型配置 ===
    default_llm_provider: Literal["openai", "anthropic"] = "openai"
    default_openai_model: str = "gpt-4o-mini"
    default_anthropic_model: str = "claude-sonnet-4-5"
    default_temperature: float | None = None

    # === 路径配置 ===
    project_root: Path = Field(default=_PROJECT_ROOT)
    db_dir: Path = Field(default=_PROJECT_ROOT / "db")
    reanimator_input_dir_override: Path | None = Field(
        default=None,
        validation_alias="REANIMATOR_INPUT_DIR",
        description="Override for Reanimator input directory",
    )
    reanimator_output_dir_override: Path | None = Field(
        default=None,
        validation_alias="REANIMATOR_OUTPUT_DIR",
        description="Override for Reanimator output directory",
    )
    lithoformer_input_dir_override: Path | None = Field(
        default=None,
        validation_alias="LITHOFORMER_INPUT_DIR",
        description="Override for Lithoformer input directory",
    )
    lithoformer_output_dir_override: Path | None = Field(
        default=None,
        validation_alias="LITHOFORMER_OUTPUT_DIR",
        description="Override for Lithoformer output directory",
    )

    # === 业务配置 ===
    batch_timezone: str = "America/New_York"
    max_batch_runs_per_day: int = Field(default=26, ge=1, le=26)
    reanimator_term_list_version: str = "v1"

    # === 日志配置 ===
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "console"

    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),  # 使用绝对路径
        env_file_encoding="utf-8",
        case_sensitive=False,  # 环境变量不区分大小写
        extra="ignore",  # 忽略额外的环境变量
    )

    @field_validator("anthropic_api_key", mode="before")
    @classmethod
    def optional_api_key_empty_to_none(cls, v: str | None) -> str | None:
        """将空字符串转换为 None（用于可选的 API Key）"""
        if isinstance(v, str) and v.strip() == "":
            return None
        return v
    @field_validator("default_temperature", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: str | float | None) -> float | None:
        """将空字符串转换为 None"""
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

    @field_validator("db_dir", mode="before")
    @classmethod
    def ensure_db_absolute(cls, v: Path | str) -> Path:
        """确保数据库目录为绝对路径。"""
        path = Path(v) if isinstance(v, str) else v
        if not path.is_absolute():
            return (_PROJECT_ROOT / path).resolve()
        return path.resolve()

    @property
    def reanimator_input_dir(self) -> Path:
        """Reanimator 输入目录"""
        return self._normalize_path(self.reanimator_input_dir_override, _PATH_CONFIG.reanimator_input)

    @property
    def reanimator_output_dir(self) -> Path:
        """Reanimator 输出目录"""
        return self._normalize_path(self.reanimator_output_dir_override, _PATH_CONFIG.reanimator_output)

    @property
    def lithoformer_input_dir(self) -> Path:
        """Lithoformer 输入目录"""
        return self._normalize_path(self.lithoformer_input_dir_override, _PATH_CONFIG.lithoformer_input)

    @property
    def lithoformer_output_dir(self) -> Path:
        """Lithoformer 输出目录"""
        return self._normalize_path(self.lithoformer_output_dir_override, _PATH_CONFIG.lithoformer_output)

    @property
    def term_list_path(self) -> Path:
        """术语表路径"""
        return self.db_dir / f"term_list_{self.reanimator_term_list_version}.csv"

    @property
    def sample_root(self) -> Path:
        """只读示例资源目录。"""
        return _PATH_CONFIG.sample_root

    def is_sample_path(self, path: Path) -> bool:
        """判断路径是否位于只读示例资源内。"""
        return _PATH_CONFIG.is_within_samples(path)

    def ensure_dirs(self) -> None:
        """确保需要写入的目录存在（排除只读示例资源）。"""
        dirs_to_check = [
            self.db_dir,
            Path.cwd() / "output",
        ]
        for dir_path in dirs_to_check:
            if self.is_sample_path(dir_path):
                continue
            dir_path.mkdir(parents=True, exist_ok=True)

    def _normalize_path(self, override: Path | None, default: Path) -> Path:
        if override:
            return (self.project_root / override).resolve() if not override.is_absolute() else override.resolve()
        if self.is_sample_path(default):
            return default
        return default


# === 单例模式 - 全局配置实例 ===
_settings_instance: Settings | None = None


def get_settings(reload: bool = False) -> Settings:
    """
    获取全局配置实例（单例模式）

    Args:
        reload: 是否强制重新加载配置

    Returns:
        Settings 实例

    Example:
        >>> settings = get_settings()
        >>> print(settings.openai_api_key[:10])
        sk-proj-pZ...
    """
    global _settings_instance
    if _settings_instance is None or reload:
        _settings_instance = Settings()
    return _settings_instance


# === 使用示例 ===
if __name__ == "__main__":
    # 加载配置
    settings = get_settings()

    # 类型安全访问
    print(f"OpenAI Model: {settings.default_openai_model}")
    print(f"Term List Path: {settings.term_list_path}")

    # 确保目录存在
    settings.ensure_dirs()

    # 验证会自动进行
    # 如果 OPENAI_API_KEY 为空或太短，会在此处抛出 ValidationError
