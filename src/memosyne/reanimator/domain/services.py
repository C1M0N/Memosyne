"""Reanimator domain services (v2)."""
from __future__ import annotations

from .models import LLMResponse, WordID


def apply_business_rules(word_en: str, response: LLMResponse) -> LLMResponse:
    if " " in word_en and response.pos != "abbr.":
        response.pos = "P."
    if response.pos == "abbr." and response.ipa:
        response.ipa = ""
    if response.example.strip().lower() == response.def_en.strip().lower():
        response.example = ""
    response.etymo_en = " ".join(response.etymo_en.lower().split())
    response.etymo_zh = " ".join(response.etymo_zh.split())
    return response


def map_field_label(field_en: str, mapping: dict[str, str]) -> str:
    tag = (field_en or "").strip().lower()
    if not tag:
        return ""
    if tag in mapping:
        return mapping[tag]
    for key, value in mapping.items():
        if key and key in tag:
            return value
    return ""


def generate_word_id(start_index: int, offset: int) -> str:
    return str(WordID(start_index + offset))


def parse_word_index_from_filename(filename: str) -> int:
    stem = filename.split('.')[0]
    try:
        return int(stem)
    except ValueError as exc:
        raise ValueError("Reanimator 输入文件名必须为纯数字") from exc
