"""
Quiz Schema - Quiz 题目 JSON Schema

用于 Lithoformer 的 LLM 结构化输出

设计说明：
- 所有字段都是必需的（required），保持 strict: True
- 不同题型的不需要的字段设为空值（空数组、空字符串）
  - MCQ: options 必填（支持 A-Z），cloze_answers=[], answer="A"-"Z"
  - CLOZE: cloze_answers 必填，options 中所有键设空字符串，answer=""

动态Schema支持（v0.11+）：
- 根据功能配置动态生成schema（4种组合）
- full: 翻译 + 解析
- no_translation: 仅解析
- no_analysis: 仅翻译
- minimal: 基础字段
"""

from ..domain.models import OPTION_LETTERS

def get_dynamic_schema(schema_type: str) -> dict:
    """
    根据schema类型动态生成JSON Schema

    Args:
        schema_type: schema类型，可选值：
            - "full": 翻译 + 解析（完整schema）
            - "no_translation": 仅解析（移除translation字段）
            - "no_analysis": 仅翻译（移除analysis字段）
            - "minimal": 基础字段（移除translation和analysis）

    Returns:
        动态生成的JSON Schema

    Examples:
        >>> schema = get_dynamic_schema("full")
        >>> schema["name"]
        'QuizQuestion'
        >>> schema = get_dynamic_schema("minimal")
        >>> "stem_translation" in schema["schema"]["properties"]
        False
    """
    import copy

    # 基础属性（所有schema都包含）
    base_properties = {
        "qtype": {
            "type": "string",
            "enum": ["MCQ", "CLOZE"],
            "description": "题目类型：MCQ=选择题, CLOZE=填空题"
        },
        "stem": {
            "type": "string",
            "description": "题干内容（保留原始换行，使用 <br> 表示）"
        },
        "options": {
            "type": "object",
            "additionalProperties": False,
            "properties": {letter: {"type": "string"} for letter in OPTION_LETTERS},
            "required": list(OPTION_LETTERS),
            "description": "选择题选项（无选项则均为空字符串）"
        },
        "answer": {
            "type": "string",
            "description": "正确答案：MCQ 填 A-Z（大写字母，可多选时连续写），CLOZE 填空字符串"
        },
        "cloze_answers": {
            "type": "array",
            "items": {"type": "string"},
            "description": "填空题答案列表（CLOZE 类型必填，其他类型填 []）"
        },
    }

    # 翻译字段
    translation_properties = {
        "stem_translation": {
            "type": "string",
            "description": "题干的简体中文翻译"
        },
        "options_translation": {
            "type": "object",
            "additionalProperties": False,
            "properties": {letter: {"type": "string"} for letter in OPTION_LETTERS},
            "required": list(OPTION_LETTERS),
            "description": "选择题选项的简体中文翻译"
        },
        "cloze_answers_translation": {
            "type": "array",
            "items": {"type": "string"},
            "description": "填空题答案的简体中文翻译"
        },
    }

    # 解析字段
    analysis_property = {
        "analysis": {
            "type": "object",
            "additionalProperties": False,
            "description": "CRITICAL: Must be a JSON object (not a string). Contains structured analysis with domain, rationale, key_points array, and distractors array. Never serialize this object as a string.",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "简洁的学术或主题标签（中文）"
                },
                "rationale": {
                    "type": "string",
                    "description": "为什么正确答案正确的中文说明（可引用必要英文术语）"
                },
                "key_points": {
                    "type": "array",
                    "description": "MUST be an array of strings (not a string). 2-4条中文关键知识点",
                    "items": {"type": "string"}
                },
                "distractors": {
                    "type": "array",
                    "description": "MUST be an array of objects (not a string). 针对所有错误选项（A-Z）的分析",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "option": {
                                "type": "string",
                                "description": "错误选项的大写字母（A-Z）"
                            },
                            "reason": {
                                "type": "string",
                                "description": "为什么该选项错误的中文解释"
                            }
                        },
                        "required": ["option", "reason"]
                    }
                }
            },
            "required": ["domain", "rationale", "key_points", "distractors"]
        }
    }

    # 根据schema类型组装properties和required
    properties = copy.deepcopy(base_properties)
    required = ["qtype", "stem", "options", "answer", "cloze_answers"]

    if schema_type in ("full", "no_analysis"):
        # 包含翻译字段
        properties.update(translation_properties)
        required.extend([
            "stem_translation",
            "options_translation",
            "cloze_answers_translation"
        ])

    if schema_type in ("full", "no_translation"):
        # 包含解析字段
        properties.update(analysis_property)
        required.append("analysis")

    return {
        "name": "QuizQuestion",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": properties,
            "required": required
        }
    }
