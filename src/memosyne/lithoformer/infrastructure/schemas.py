"""
Quiz Schema - Quiz 题目 JSON Schema

用于 Lithoformer 的 LLM 结构化输出

设计说明：
- 所有字段都是必需的（required），保持 strict: True
- 不同题型的不需要的字段设为空值（空数组、空字符串）
  - MCQ: options 必填，steps=[], cloze_answers=[], answer="A"-"F"
  - CLOZE: cloze_answers 必填，steps=[], options 可省略或填空字符串, answer=""
  - ORDER: steps 必填，options 可省略, cloze_answers=[], answer=""

动态Schema支持（v0.11+）：
- 根据功能配置动态生成schema（4种组合）
- full: 翻译 + 解析
- no_translation: 仅解析
- no_analysis: 仅翻译
- minimal: 基础字段
"""

QUESTION_SCHEMA = {
    "name": "QuizQuestion",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "qtype": {
                "type": "string",
                "enum": ["MCQ", "CLOZE", "ORDER"],
                "description": "题目类型：MCQ=选择题, CLOZE=填空题, ORDER=排序题"
            },
            "stem": {
                "type": "string",
                "description": "题干内容（需要保留原始换行，使用 <br> 表示）"
            },
            "stem_translation": {
                "type": "string",
                "description": "题干的简体中文翻译"
            },
            "steps": {
                "type": "array",
                "items": {"type": "string"},
                "description": "排序题步骤列表（ORDER 类型必填，其他类型填 []）"
            },
            "steps_translation": {
                "type": "array",
                "items": {"type": "string"},
                "description": "排序题步骤的中文翻译（与 steps 数量一致）"
            },
            "options": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "A": {"type": "string"},
                    "B": {"type": "string"},
                    "C": {"type": "string"},
                    "D": {"type": "string"},
                    "E": {"type": "string"},
                    "F": {"type": "string"}
                },
                "required": ["A", "B", "C", "D", "E", "F"],
                "description": "选择题选项（无选项则均为空字符串）"
            },
            "options_translation": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "A": {"type": "string"},
                    "B": {"type": "string"},
                    "C": {"type": "string"},
                    "D": {"type": "string"},
                    "E": {"type": "string"},
                    "F": {"type": "string"}
                },
                "required": ["A", "B", "C", "D", "E", "F"],
                "description": "选择题选项的简体中文翻译"
            },
            "answer": {
                "type": "string",
                "description": "正确答案：MCQ/ORDER 填 A-F，CLOZE 填空字符串"
            },
            "cloze_answers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "填空题答案列表（CLOZE 类型必填，其他类型填 []）"
            },
            "cloze_answers_translation": {
                "type": "array",
                "items": {"type": "string"},
                "description": "填空题答案的简体中文翻译"
            },
            "analysis": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "domain": {"type": "string"},
                    "rationale": {"type": "string"},
                    "key_points": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "distractors": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "option": {"type": "string"},
                                "reason": {"type": "string"}
                            },
                            "required": ["option", "reason"]
                        }
                    }
                },
                "required": ["domain", "rationale", "key_points", "distractors"],
                "description": "题目解析信息"
            }
        },
        "required": [
            "qtype",
            "stem",
            "stem_translation",
            "steps",
            "steps_translation",
            "options",
            "options_translation",
            "answer",
            "cloze_answers",
            "cloze_answers_translation",
            "analysis"
        ]
    }
}


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
            "enum": ["MCQ", "CLOZE", "ORDER"],
            "description": "题目类型：MCQ=选择题, CLOZE=填空题, ORDER=排序题"
        },
        "stem": {
            "type": "string",
            "description": "题干内容（需要保留原始换行，使用 <br> 表示）"
        },
        "steps": {
            "type": "array",
            "items": {"type": "string"},
            "description": "排序题步骤列表（ORDER 类型必填，其他类型填 []）"
        },
        "options": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "A": {"type": "string"},
                "B": {"type": "string"},
                "C": {"type": "string"},
                "D": {"type": "string"},
                "E": {"type": "string"},
                "F": {"type": "string"}
            },
            "required": ["A", "B", "C", "D", "E", "F"],
            "description": "选择题选项（无选项则均为空字符串）"
        },
        "answer": {
            "type": "string",
            "description": "正确答案：MCQ/ORDER 填 A-F，CLOZE 填空字符串"
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
        "steps_translation": {
            "type": "array",
            "items": {"type": "string"},
            "description": "排序题步骤的中文翻译（与 steps 数量一致）"
        },
        "options_translation": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "A": {"type": "string"},
                "B": {"type": "string"},
                "C": {"type": "string"},
                "D": {"type": "string"},
                "E": {"type": "string"},
                "F": {"type": "string"}
            },
            "required": ["A", "B", "C", "D", "E", "F"],
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
            "properties": {
                "domain": {"type": "string"},
                "rationale": {"type": "string"},
                "key_points": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "distractors": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "option": {"type": "string"},
                            "reason": {"type": "string"}
                        },
                        "required": ["option", "reason"]
                    }
                }
            },
            "required": ["domain", "rationale", "key_points", "distractors"],
            "description": "题目解析信息"
        }
    }

    # 根据schema类型组装properties和required
    properties = copy.deepcopy(base_properties)
    required = ["qtype", "stem", "steps", "options", "answer", "cloze_answers"]

    if schema_type in ("full", "no_analysis"):
        # 包含翻译字段
        properties.update(translation_properties)
        required.extend([
            "stem_translation",
            "steps_translation",
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
