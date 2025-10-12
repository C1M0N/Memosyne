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

QUIZ_SCHEMA = {
    "name": "QuizItems",
    "strict": True,  # 严格模式，类型安全
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "items": {
                "type": "array",
                "items": {
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
                            "description": "题干（题目主要内容）"
                        },
                        "steps": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "排序题的步骤列表（ORDER 类型必填，其他类型给空数组 []）"
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
                            "description": "选择题的选项（MCQ 类型必填，其他类型填空字符串）"
                        },
                        "answer": {
                            "type": "string",
                            "description": "选择题的正确答案字母（MCQ 类型填 A-F，其他类型填空字符串）"
                        },
                        "cloze_answers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "填空题的答案列表（CLOZE 类型必填，其他类型给空数组 []）"
                        }
                    },
                    "required": ["qtype", "stem", "steps", "options", "answer", "cloze_answers"]
                }
            }
        },
        "required": ["items"]
    }
}
