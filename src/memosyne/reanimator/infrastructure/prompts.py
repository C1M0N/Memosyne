"""Reanimator prompt management (dynamic, versioned)."""
from __future__ import annotations

from functools import lru_cache
from typing import Dict, Iterable

from ...shared.config import get_settings
from ...shared.infrastructure.config_db import get_stats_repository

DEFAULT_PROMPT_VERSION = "0001"
DEFAULT_PROMPT_SECTIONS = {
    "reanimator_system": """You are a bilingual terminologist. Produce a single JSON object with the following keys: IPA, POS, Rarity, DefEn, Example, FieldEn, EtymoEn, EtymoZh, Picture.\n\nRules:\n1. DefEn and Example must be ONE sentence each, literally containing the target word, consistent with MeanZh, and never identical.\n2. IPA is American IPA slash-wrapped; empty only when POS=\"abbr.\".\n3. POS must be exactly one of [\"n.\", \"vt.\", \"vi.\", \"adj.\", \"adv.\", \"P.\", \"O.\", \"abbr.\"]. P. indicates multi-word phrases.\n4. Rarity is either \"\" or \"RARE\" (only when reputable sources mark it as uncommon/technical).\n5. FieldEn is a concise lowercase ASCII domain label.\n6. EtymoEn/EtymoZh are space-separated morphemes and their glosses. Use underscores inside a token for multi-word glosses.\n7. Picture is a short English description suitable for an illustration prompt; leave empty when imagery is irrelevant.\n8. JSON must not contain markdown, code fences, comments, or extra keys.\n""",
    "reanimator_guardrails": """Validation reminders:\n- Escape quotes so the JSON parses without post-processing.\n- Keep sentences concise (<= 25 English words).\n- Any field not requested should be returned as an empty string.""",
}

REANIMATOR_USER_TEMPLATE = """Word: {word_en}\nMeanZh: {mean_zh}\nBatchNote: {batch_note}\nRequested Optional Fields: {requested}\n\nIf the list is empty, only fill the mandatory fields (IPA, POS, FieldEn, Etymo*, Picture). For each optional field NOT listed, return an empty string (we already have user-provided data). Output JSON only."""


@lru_cache(maxsize=1)
def _load_sections() -> Dict[str, str]:
    settings = get_settings()
    stats_repo = get_stats_repository(settings.db_dir / "stat.db")
    return stats_repo.get_prompt_sections(domain="reanimator")


def get_reanimator_system_prompt() -> str:
    sections = _load_sections()
    ordered = [sections.get("reanimator_system", ""), sections.get("reanimator_guardrails", "")]
    return "\n".join(part for part in ordered if part)


def get_reanimator_user_prompt(
    word_en: str,
    mean_zh: str,
    batch_note: str = "",
    requested_fields: Iterable[str] = (),
) -> str:
    requested = ", ".join(requested_fields) if requested_fields else "(none)"
    return REANIMATOR_USER_TEMPLATE.format(
        word_en=word_en,
        mean_zh=mean_zh,
        batch_note=batch_note or "(无备注)",
        requested=requested,
    )
