"""
Quiz Schema - Quiz 题目 JSON Schema

用于 Lithoformer 的 LLM 结构化输出
"""

QUIZ_SCHEMA = {
    "name": "QuizItems",
    "strict": True,
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
                        "qtype": {"type": "string", "enum": ["MCQ", "CLOZE", "ORDER"]},
                        "stem": {"type": "string", "minLength": 1},
                        "steps": {
                            "type": "array",
                            "items": {"type": "string"}
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
                            "required": ["A", "B", "C", "D", "E", "F"]
                        },
                        "answer": {"type": "string", "pattern": "^[A-F]?$"},
                        "cloze_answers": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["qtype", "stem", "steps", "options", "answer", "cloze_answers"]
                }
            }
        },
        "required": ["items"]
    }
}
