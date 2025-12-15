"""Reanimator prompt management (dynamic, versioned)."""
from __future__ import annotations

from functools import lru_cache
from typing import Dict, Iterable

from ...shared.config import get_settings
from ...shared.infrastructure.config_db import get_stats_repository
from .prompt_defaults import DEFAULT_PROMPT_VERSION, DEFAULT_PROMPTS

REANIMATOR_USER_TEMPLATE = """Word: {word_en}
MeanZh: {mean_zh}
BatchNote: {batch_note}
Requested fields (need fresh generation): {requested}

Instructions:
- Copy any user-provided values verbatim.
- For every empty field, generate a complete value. IPA, POS, DefEn, Example, EtymoEn, and EtymoZh MUST be non-empty.
- Keep IPA slash-wrapped (abbr. -> full expansion), POS from the allowed list, FieldEn lowercase ASCII, Rarity either \"\" or \"RARE\".
- EtymoEn/EtymoZh must have matching token counts; use space-separated morphemes and aligned Chinese glosses.
- Output STRICT JSON only (no prose, no markdown)."""


@lru_cache(maxsize=1)
def _load_sections() -> Dict[str, str]:
    settings = get_settings()
    stats_repo = get_stats_repository(settings.db_dir / "stat.db")
    # Upsert the current prompt version without touching existing ones.
    stats_repo.upsert_prompt_sections(
        domain="reanimator",
        version=DEFAULT_PROMPT_VERSION,
        sections=DEFAULT_PROMPTS,
    )
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
