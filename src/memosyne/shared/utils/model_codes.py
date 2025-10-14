"""
模型代码映射 - 4位简写系统

用于文件命名和 CLI 快捷输入

设计规范：
- 所有模型代码统一为 4 位
- OpenAI 模型以 'o' 开头
- Claude 模型以 'c' 开头
- 第二位表示模型类型：o=opus, s=sonnet, h=haiku, 数字表示版本
"""
from typing import Literal

# ============================================================
# 模型代码映射表
# ============================================================

# 完整模型名 -> 4位代码
MODEL_TO_CODE: dict[str, str] = {
    # OpenAI 模型
    "gpt-5-mini": "o50m",
    "gpt-5": "o50o",
    "gpt-4o": "o4oo",
    "gpt-4o-mini": "o4om",
    "o3": "oo3o",
    "o4-mini": "oo4m",  # 别名

    # Claude 模型
    "claude-opus-4-1": "co41",
    "claude-opus-4-0": "co40",
    "claude-opus-4": "co40",  # 别名（映射到 4.0）
    "claude-sonnet-4-5": "cs45",
    "claude-3-7-sonnet-latest": "cs37",
    "claude-3-5-haiku-latest": "ch35",
    "claude-haiku-4": "ch35",  # 别名（映射到 3.5）
}

# 4位代码 -> 完整模型名（默认映射）
CODE_TO_MODEL: dict[str, str] = {
    # OpenAI
    "o50m": "gpt-5-mini",
    "o50o": "gpt-5",
    "o4oo": "gpt-4o",
    "o4om": "gpt-4o-mini",
    "oo3o": "o3",

    # Claude
    "co41": "claude-opus-4-1",
    "co40": "claude-opus-4-0",
    "cs45": "claude-sonnet-4-5",
    "cs37": "claude-3-7-sonnet-latest",
    "ch35": "claude-3-5-haiku-latest",
}

# 模型提供商判断
OPENAI_PREFIXES = ("gpt-", "o1-", "o3", "o4-")
CLAUDE_PREFIXES = ("claude-",)


# ============================================================
# 公共 API
# ============================================================

def get_code_from_model(model: str) -> str:
    """
    从完整模型名获取 4 位代码

    Args:
        model: 完整模型名（如 "gpt-4o", "claude-sonnet-4-5"）

    Returns:
        4 位模型代码（如 "o4oo", "cs45"）

    Raises:
        ValueError: 不支持的模型

    Example:
        >>> get_code_from_model("gpt-4o")
        'o4oo'
        >>> get_code_from_model("claude-sonnet-4-5")
        'cs45'
    """
    model_lower = model.strip().lower()

    if model_lower in MODEL_TO_CODE:
        return MODEL_TO_CODE[model_lower]

    raise ValueError(
        f"不支持的模型：{model}\n"
        f"支持的模型：{', '.join(sorted(set(MODEL_TO_CODE.keys())))}"
    )


def get_model_from_code(code: str) -> str:
    """
    从 4 位代码获取完整模型名

    Args:
        code: 4 位模型代码（如 "o4oo", "cs45"）

    Returns:
        完整模型名（如 "gpt-4o", "claude-sonnet-4-5"）

    Raises:
        ValueError: 不支持的代码

    Example:
        >>> get_model_from_code("o4oo")
        'gpt-4o'
        >>> get_model_from_code("cs45")
        'claude-sonnet-4-5'
    """
    code_lower = code.strip().lower()

    if code_lower in CODE_TO_MODEL:
        return CODE_TO_MODEL[code_lower]

    raise ValueError(
        f"不支持的模型代码：{code}\n"
        f"支持的代码：{', '.join(sorted(CODE_TO_MODEL.keys()))}"
    )


def resolve_model_input(user_input: str) -> tuple[str, str]:
    """
    统一解析用户输入（支持完整模型名或 4 位代码）

    Args:
        user_input: 用户输入（完整模型名或 4 位代码）

    Returns:
        (model, code) 元组
        - model: 完整模型名
        - code: 4 位代码

    Example:
        >>> resolve_model_input("gpt-4o")
        ('gpt-4o', 'o4oo')
        >>> resolve_model_input("o4oo")
        ('gpt-4o', 'o4oo')
        >>> resolve_model_input("cs45")
        ('claude-sonnet-4-5', 'cs45')
    """
    user_input = user_input.strip().lower()

    # 尝试作为代码解析
    if len(user_input) == 4 and user_input in CODE_TO_MODEL:
        model = CODE_TO_MODEL[user_input]
        return model, user_input

    # 尝试作为完整模型名解析
    if user_input in MODEL_TO_CODE:
        code = MODEL_TO_CODE[user_input]
        return user_input, code

    # 都不匹配，抛出错误
    raise ValueError(
        f"无法识别的输入：{user_input}\n"
        f"支持的模型代码：{', '.join(sorted(CODE_TO_MODEL.keys()))}\n"
        f"支持的模型名：{', '.join(sorted(set(MODEL_TO_CODE.keys())))}"
    )


def get_provider_from_model(model: str) -> Literal["openai", "anthropic"]:
    """
    从模型名判断提供商

    Args:
        model: 完整模型名

    Returns:
        "openai" 或 "anthropic"

    Example:
        >>> get_provider_from_model("gpt-4o")
        'openai'
        >>> get_provider_from_model("claude-sonnet-4-5")
        'anthropic'
    """
    model_lower = model.strip().lower()

    if model_lower.startswith(OPENAI_PREFIXES):
        return "openai"
    elif model_lower.startswith(CLAUDE_PREFIXES):
        return "anthropic"
    else:
        raise ValueError(f"无法判断模型提供商：{model}")


def list_all_models() -> dict[str, list[str]]:
    """
    列出所有支持的模型（按提供商分组）

    Returns:
        字典，键为提供商名，值为模型列表

    Example:
        >>> models = list_all_models()
        >>> print(models["openai"])
        ['gpt-4o', 'gpt-5-mini', ...]
    """
    openai_models = []
    anthropic_models = []

    # 去重（因为有别名）
    seen = set()
    for model in MODEL_TO_CODE.keys():
        if model in seen:
            continue
        seen.add(model)

        if model.startswith(OPENAI_PREFIXES):
            openai_models.append(model)
        elif model.startswith(CLAUDE_PREFIXES):
            anthropic_models.append(model)

    return {
        "openai": sorted(openai_models),
        "anthropic": sorted(anthropic_models),
    }


def list_all_codes() -> dict[str, str]:
    """
    列出所有模型代码和对应的模型名

    Returns:
        字典，键为代码，值为模型名

    Example:
        >>> codes = list_all_codes()
        >>> for code, model in codes.items():
        ...     print(f"{code} -> {model}")
    """
    return dict(CODE_TO_MODEL)


# ============================================================
# 使用示例
# ============================================================
if __name__ == "__main__":
    # 示例 1: 代码 -> 模型
    print("=== 代码 -> 模型 ===")
    print(f"o4oo -> {get_model_from_code('o4oo')}")
    print(f"cs45 -> {get_model_from_code('cs45')}")
    print(f"ch35 -> {get_model_from_code('ch35')}")
    print()

    # 示例 2: 模型 -> 代码
    print("=== 模型 -> 代码 ===")
    print(f"gpt-4o -> {get_code_from_model('gpt-4o')}")
    print(f"claude-sonnet-4-5 -> {get_code_from_model('claude-sonnet-4-5')}")
    print()

    # 示例 3: 统一解析
    print("=== 统一解析 ===")
    print(f"输入 'gpt-4o': {resolve_model_input('gpt-4o')}")
    print(f"输入 'o4oo': {resolve_model_input('o4oo')}")
    print(f"输入 'cs45': {resolve_model_input('cs45')}")
    print()

    # 示例 4: 判断提供商
    print("=== 判断提供商 ===")
    print(f"gpt-4o: {get_provider_from_model('gpt-4o')}")
    print(f"claude-sonnet-4-5: {get_provider_from_model('claude-sonnet-4-5')}")
    print()

    # 示例 5: 列出所有模型
    print("=== 所有支持的模型 ===")
    all_models = list_all_models()
    print(f"OpenAI: {', '.join(all_models['openai'])}")
    print(f"Anthropic: {', '.join(all_models['anthropic'])}")
