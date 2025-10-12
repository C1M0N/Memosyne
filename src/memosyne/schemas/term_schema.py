"""
Term Schema - 术语结果 JSON Schema

用于 Reanimater 的 LLM 结构化输出
"""

TERM_RESULT_SCHEMA = {
    "name": "TermResult",
    "description": "Terminology fields for a single headword.",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "IPA": {
                "type": "string",
                "description": "American IPA between slashes; empty only if POS is abbr.",
                "pattern": r"^(\/[^\s\/].*\/|)$"
            },
            "POS": {
                "type": "string",
                "enum": ["n.", "vt.", "vi.", "adj.", "adv.", "P.", "O.", "abbr."]
            },
            "Rarity": {
                "type": "string",
                "enum": ["", "RARE"]
            },
            "EnDef": {
                "type": "string",
                "minLength": 1
            },
            "Example": {
                "type": "string",
                "minLength": 1
            },
            "PPfix": {
                "type": "string"
            },
            "PPmeans": {
                "type": "string",
                "description": "ASCII only; use underscores inside a token for multi-word gloss.",
                "pattern": r"^[\x20-\x7E]*$"
            },
            "TagEN": {
                "type": "string"
            }
        },
        "required": ["IPA", "POS", "Rarity", "EnDef", "Example", "PPfix", "PPmeans", "TagEN"]
    }
}
