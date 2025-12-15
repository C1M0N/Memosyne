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
                "description": "American IPA (slash-wrapped) or full expansion for abbr. Must be non-empty.",
                "minLength": 1
            },
            "POS": {
                "type": "string",
                "description": "Part of speech (MANDATORY, never empty)",
                "enum": ["n.", "vt.", "vi.", "adj.", "adv.", "P.", "O.", "abbr."]
            },
            "Rarity": {
                "type": "string",
                "description": "Empty or RARE. Can be empty.",
                "enum": ["", "RARE"]
            },
            "DefEn": {
                "type": "string",
                "description": "English definition (MANDATORY, never empty)",
                "minLength": 1
            },
            "Example": {
                "type": "string",
                "description": "Example sentence (MANDATORY, never empty)",
                "minLength": 1
            },
            "FieldEn": {
                "type": "string",
                "description": "Subject field tag in English. Should be non-empty lowercase ASCII.",
                "minLength": 1
            },
            "EtymoEn": {
                "type": "string",
                "description": "Etymology in English. Must be non-empty.",
                "minLength": 1
            },
            "EtymoZh": {
                "type": "string",
                "description": "Etymology in Chinese. Must be non-empty.",
                "minLength": 1
            },
            "Picture": {
                "type": "string",
                "description": "Picture description. Can be empty."
            }
        },
        "required": ["IPA", "POS", "Rarity", "DefEn", "Example", "FieldEn", "EtymoEn", "EtymoZh", "Picture"]
    }
}
