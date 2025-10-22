"""配置管理模块 - 使用 Pydantic Settings 实现类型安全的配置。"""

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .path_config import get_path_config
from memosyne.core.interfaces import ConfigRepository


def _find_project_root() -> Path:
    """查找项目根目录（优先以 .env 或 src/ 为参考）。"""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / ".env").exists():
            return parent
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd()


_PROJECT_ROOT = _find_project_root()
_PATH_CONFIG = get_path_config()


class Settings(BaseSettings):
    """
    应用配置（从环境变量和数据库加载）

    配置优先级：
    1. 数据库配置（SQLite）
    2. 环境变量
    3. path_config.json（已废弃）
    4. 默认值
    """

    # 配置仓储（用于持久化配置）
    _config_repo: ConfigRepository | None = None

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
        """
        Lithoformer 输入目录

        优先级：数据库 > 环境变量 > path_config.json
        """
        # 1. 优先从数据库读取
        if self._config_repo:
            db_value = self._config_repo.get("lithoformer_input_dir")
            if db_value:
                return Path(db_value)

        # 2. 使用环境变量 override
        if self.lithoformer_input_dir_override:
            return self._normalize_path(self.lithoformer_input_dir_override, _PATH_CONFIG.lithoformer_input)

        # 3. fallback 到 path_config.json
        return _PATH_CONFIG.lithoformer_input

    @property
    def lithoformer_output_dir(self) -> Path:
        """
        Lithoformer 输出目录

        优先级：数据库 > 环境变量 > path_config.json
        """
        # 1. 优先从数据库读取
        if self._config_repo:
            db_value = self._config_repo.get("lithoformer_output_dir")
            if db_value:
                return Path(db_value)

        # 2. 使用环境变量 override
        if self.lithoformer_output_dir_override:
            return self._normalize_path(self.lithoformer_output_dir_override, _PATH_CONFIG.lithoformer_output)

        # 3. fallback 到 path_config.json
        return _PATH_CONFIG.lithoformer_output

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

    def set_config_repository(self, repo: ConfigRepository) -> None:
        """
        设置配置仓储（用于从数据库读取/写入配置）

        Args:
            repo: ConfigRepository 实现
        """
        self._config_repo = repo

    def get_default_model(self) -> str:
        """
        获取默认模型（格式：provider:model）

        Returns:
            默认模型字符串，如 "openai:gpt-4o-mini"
        """
        if self._config_repo:
            db_value = self._config_repo.get("default_model")
            if db_value:
                return db_value
        # fallback 到环境变量或默认值
        return f"{self.default_llm_provider}:{self.default_openai_model}"

    def save_config(self, key: str, value: str) -> None:
        """
        保存配置到数据库

        Args:
            key: 配置键
            value: 配置值
        """
        if not self._config_repo:
            raise ValueError("ConfigRepository 未初始化，请先调用 set_config_repository")
        self._config_repo.set(key, value)

    def reload_from_db(self) -> None:
        """从数据库重新加载配置（实时生效）"""
        # 由于使用了property，配置会自动从数据库读取
        # 这个方法主要用于清除可能的缓存（如果有的话）
        pass


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

        # 初始化配置仓储（从 SQLite 读取配置）
        from memosyne.shared.infrastructure.config_db import get_config_repository
        db_path = _settings_instance.db_dir / "config.db"
        try:
            config_repo = get_config_repository(db_path)
            _settings_instance.set_config_repository(config_repo)
        except Exception:
            # 如果配置仓储初始化失败，继续使用默认配置
            pass

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
