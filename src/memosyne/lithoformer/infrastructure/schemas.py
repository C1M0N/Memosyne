"""
Quiz Schema - Quiz 题目 JSON Schema

用于 Lithoformer 的 LLM 结构化输出

设计说明：
- 所有字段都是必需的（required），保持 strict: True
- 不同题型的不需要的字段设为空值（空数组、空字符串）
  - MCQ: options 必填，steps=[], cloze_answers=[], answer="A"-"F"
  - CLOZE: cloze_answers 必填，steps=[], options 可省略或填空字符串, answer=""
  - ORDER: steps 必填，options 可省略, cloze_answers=[], answer=""
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
