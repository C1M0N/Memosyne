"""
Reanimator Domain Services - 领域服务（纯业务逻辑）

依赖原则：
- ✅ 零外部依赖（仅依赖本领域的模型）
- ✅ 无状态函数（纯函数，可测试）
- ✅ 封装业务规则（POS 修正、标签映射、ID 生成等）

业务规则：
1. 词组（含空格）→ 强制 POS='P.'（缩写词例外）
2. 缩写词（abbr.）→ IPA 必须为空
3. Example 与 EnDef 相同 → 清空 Example
4. PPfix/PPmeans → 小写化、空白折叠
5. 英文标签 → 中文标签（精确匹配或包含匹配）
"""
from .models import LLMResponse, MemoID


def apply_business_rules(word: str, llm_response: LLMResponse) -> LLMResponse:
    """
    应用业务规则（修正 LLM 输出）

    Args:
        word: 原始词条
        llm_response: LLM 响应

    Returns:
        修正后的响应

    Example:
        >>> resp = LLMResponse(POS="n.", EnDef="def", Example="def")
        >>> fixed = apply_business_rules("neural network", resp)
        >>> fixed.pos
        'P.'
        >>> fixed.example
        ''
    """
    # 规则1：词组（含空格）→ 强制 POS='P.'（但 abbr. 例外）
    if " " in word and llm_response.pos != "abbr.":
        llm_response.pos = "P."

    # 规则2：缩写词 → IPA 必须为空（已在 LLMResponse 验证器处理，这里保险起见再检查）
    if llm_response.pos == "abbr." and llm_response.ipa:
        llm_response.ipa = ""

    # 规则3：Example 与 EnDef 相同 → 清空 Example
    if llm_response.example.strip().lower() == llm_response.en_def.strip().lower():
        llm_response.example = ""

    # 规则4：PPfix/PPmeans 规范化（小写、空白折叠）
    llm_response.pp_fix = " ".join(llm_response.pp_fix.lower().split())
    llm_response.pp_means = " ".join(llm_response.pp_means.lower().split())

    return llm_response


def get_chinese_tag(tag_en: str, term_mapping: dict[str, str]) -> str:
    """
    获取中文标签（精确匹配或宽松包含匹配）

    Args:
        tag_en: 英文标签
        term_mapping: 术语表映射（英文 -> 两字中文）

    Returns:
        两字中文标签（找不到返回空字符串）

    Example:
        >>> mapping = {"psychology": "心理", "neuroscience": "神经", "biology": "生物"}
        >>> get_chinese_tag("psychology", mapping)
        '心理'
        >>> get_chinese_tag("neurobiology", mapping)  # 包含 "biology"
        '生物'
        >>> get_chinese_tag("unknown", mapping)
        ''
    """
    tag_lower = tag_en.strip().lower()

    if not tag_lower:
        return ""

    # 1. 精确匹配
    if tag_lower in term_mapping:
        return term_mapping[tag_lower]

    # 2. 宽松包含匹配（如 "neurobiology" 匹配 "biology"）
    for en_key, cn_value in term_mapping.items():
        if en_key and en_key in tag_lower:
            return cn_value

    return ""


def generate_memo_id(start_memo_index: int, current_index: int) -> str:
    """
    生成 Memo ID（格式：M + 6位数字）

    Args:
        start_memo_index: 起始 Memo 编号（如 2700 表示从 M002701 开始）
        current_index: 当前词条索引（从0开始）

    Returns:
        Memo ID（如 "M002701"）

    Example:
        >>> generate_memo_id(2700, 0)
        'M002701'
        >>> generate_memo_id(2700, 5)
        'M002706'
    """
    memo = MemoID(start_memo_index + current_index)
    return str(memo)


def validate_word_format(word: str) -> tuple[bool, str]:
    """
    验证词条格式

    Args:
        word: 词条

    Returns:
        (is_valid, error_message)

    Example:
        >>> validate_word_format("neuroscience")
        (True, '')
        >>> validate_word_format("  ")
        (False, '词条不能为空或仅包含空白')
        >>> validate_word_format("神经科学")
        (False, '词条不应为纯中文')
    """
    # 检查空白
    if not word or not word.strip():
        return False, "词条不能为空或仅包含空白"

    # 检查纯中文
    stripped = word.strip()
    if all('\u4e00' <= c <= '\u9fff' for c in stripped if not c.isspace()):
        return False, "词条不应为纯中文"

    return True, ""


def should_force_phrase_pos(word: str, current_pos: str) -> bool:
    """
    判断是否应强制修正为短语词性（P.）

    Args:
        word: 词条
        current_pos: 当前词性

    Returns:
        是否应强制为 P.

    Example:
        >>> should_force_phrase_pos("neural network", "n.")
        True
        >>> should_force_phrase_pos("DNA", "abbr.")
        False
        >>> should_force_phrase_pos("neuron", "n.")
        False
    """
    # 词组（含空格）且非缩写词 → 强制 P.
    return " " in word and current_pos != "abbr."


# ============================================================
# 使用示例
# ============================================================
if __name__ == "__main__":
    # 1. 应用业务规则
    response = LLMResponse(
        IPA="/ˈnjʊrəl/",
        POS="n.",
        EnDef="A network of neurons.",
        Example="A network of neurons.",  # 与 EnDef 相同
        PPfix="NEURO Network",  # 大小写混乱
        PPmeans="NERVE   NET"  # 多余空白
    )
    fixed = apply_business_rules("neural network", response)
    print(f"修正后的 POS: {fixed.pos}")  # 应为 'P.'
    print(f"修正后的 Example: {fixed.example!r}")  # 应为空
    print(f"修正后的 PPfix: {fixed.pp_fix!r}")  # 应为 'neuro network'

    # 2. 标签映射
    mapping = {
        "psychology": "心理",
        "neuroscience": "神经",
        "biology": "生物",
    }
    tag1 = get_chinese_tag("psychology", mapping)
    tag2 = get_chinese_tag("neurobiology", mapping)  # 包含 "biology"
    print(f"\\n标签映射: psychology -> {tag1}")
    print(f"标签映射: neurobiology -> {tag2}")

    # 3. Memo ID 生成
    memo1 = generate_memo_id(2700, 0)
    memo2 = generate_memo_id(2700, 5)
    print(f"\\nMemo ID: {memo1}, {memo2}")

    # 4. 词条验证
    valid, msg = validate_word_format("neuroscience")
    print(f"\\n验证 'neuroscience': {valid}, {msg}")
    valid, msg = validate_word_format("神经科学")
    print(f"验证 '神经科学': {valid}, {msg}")
