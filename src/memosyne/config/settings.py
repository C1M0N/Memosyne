"""
配置管理模块 - 使用 Pydantic Settings 实现类型安全的配置

重构收益：
- ✅ 类型验证：API Key 不能为空
- ✅ 环境分离：支持 .env.dev / .env.prod
- ✅ 默认值管理：集中在一处
- ✅ IDE 提示：完整的类型提示
"""
from pathlib import Path
from typing import Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# 查找项目根目录（包含 .env 文件的位置）
def _find_project_root() -> Path:
    """查找项目根目录（查找包含 .env 文件的目录）"""
    current = Path(__file__).resolve()
    # 向上查找包含 .env 文件的目录
    for parent in current.parents:
        if (parent / ".env").exists():
            return parent
    # 如果找不到 .env，查找同时包含 data/ 和 db/ 的目录
    for parent in current.parents:
        if (parent / "data").is_dir() and (parent / "db").is_dir():
            return parent
    # 最后返回当前工作目录
    return Path.cwd()


_PROJECT_ROOT = _find_project_root()


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
    default_anthropic_model: str = "claude-3-5-sonnet-20241022"
    default_temperature: float | None = None

    # === 路径配置 ===
    project_root: Path = Field(default=_PROJECT_ROOT)
    data_dir: Path = Field(default=Path("data"))
    db_dir: Path = Field(default=Path("db"))

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

    @field_validator("data_dir", "db_dir", mode="before")
    @classmethod
    def resolve_relative_path(cls, v: Path | str) -> Path:
        """将相对路径解析为绝对路径"""
        path = Path(v) if isinstance(v, str) else v
        if not path.is_absolute():
            return _PROJECT_ROOT / path
        return path

    @property
    def reanimater_input_dir(self) -> Path:
        """Reanimater 输入目录"""
        return self.data_dir / "input" / "reanimater"

    @property
    def reanimater_output_dir(self) -> Path:
        """Reanimater 输出目录"""
        return self.data_dir / "output" / "reanimater"

    @property
    def lithoformer_input_dir(self) -> Path:
        """Lithoformer 输入目录"""
        return self.data_dir / "input" / "lithoformer"

    @property
    def lithoformer_output_dir(self) -> Path:
        """Lithoformer 输出目录"""
        return self.data_dir / "output" / "lithoformer"

    @property
    def term_list_path(self) -> Path:
        """术语表路径"""
        return self.db_dir / f"term_list_{self.reanimator_term_list_version}.csv"

    def ensure_dirs(self) -> None:
        """确保所有必需的目录存在"""
        for dir_path in [
            self.reanimater_input_dir,
            self.reanimater_output_dir,
            self.lithoformer_input_dir,
            self.lithoformer_output_dir,
            self.db_dir,
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)


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
