"""Reanimator Domain Models (v2)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class TermInput(BaseModel):
    word_en: str = Field(..., min_length=1, description="英文词条")
    mean_zh: str = Field(..., min_length=1, description="中文释义")
    def_en: str = Field(default="", description="英文定义")
    example: str = Field(default="", description="例句")
    rarity: str = Field(default="", description="稀有度")
    field: str = Field(default="", description="中文领域标签")
    batch_note: str = Field(default="", description="批次备注")
    ipa: str = Field(default="", description="音标")
    pos: str = Field(default="", description="词性")
    etymo_en: str = Field(default="", description="词根（英文）")
    etymo_zh: str = Field(default="", description="词根含义（中文）")
    picture: str = Field(default="", description="插图提示")
    word_id: str | None = Field(default=None, description="词号（R000001）")

    @field_validator(
        "word_en",
        "mean_zh",
        "def_en",
        "example",
        "rarity",
        "field",
        "batch_note",
        "ipa",
        "pos",
        "etymo_en",
        "etymo_zh",
        "picture",
        mode="before",
    )
    @classmethod
    def _strip(cls, value: str | None) -> str:
        return (value or "").strip()

    @model_validator(mode="after")
    def validate_required(self):
        word = self.word_en.strip()
        if not word:
            raise ValueError("WordEn 不能为空")
        if all('\u4e00' <= c <= '\u9fff' for c in word if not c.isspace()):
            raise ValueError("WordEn 不应为纯中文")
        if not self.mean_zh.strip():
            raise ValueError("MeanZh 不能为空")
        return self

    @property
    def wm_pair(self) -> str:
        return f"{self.word_en} - {self.mean_zh}"

    def has_manual_payload(self) -> bool:
        return bool(self.def_en and self.example)

    def requested_optional_fields(self) -> tuple[str, ...]:
        fields = []
        if not self.def_en:
            fields.append("DefEn")
        if not self.example:
            fields.append("Example")
        if not self.rarity:
            fields.append("Rarity")
        if not self.field:
            fields.append("FieldEn")
        return tuple(fields)


class LLMResponse(BaseModel):
    model_config = {"populate_by_name": True}

    ipa: str = Field(default="", alias="IPA")
    pos: Literal["n.", "vt.", "vi.", "adj.", "adv.", "P.", "O.", "abbr."] = Field(..., alias="POS")
    rarity: Literal["", "RARE"] = Field(default="", alias="Rarity")
    def_en: str = Field(default="", alias="DefEn")
    example: str = Field(default="", alias="Example")
    field_en: str = Field(default="", alias="FieldEn")
    etymo_en: str = Field(default="", alias="EtymoEn")
    etymo_zh: str = Field(default="", alias="EtymoZh")
    picture: str = Field(default="", alias="Picture")

    @model_validator(mode="after")
    def sanitize(self):
        if self.pos == "abbr." and self.ipa:
            self.ipa = ""
        self.field_en = self.field_en.strip().lower()
        return self


class TermOutput(BaseModel):
    wm_pair: str
    word_en: str
    mean_zh: str
    def_en: str
    example: str
    rarity: str
    field: str
    batch_note: str
    ipa: str
    pos: str
    etymo_en: str
    etymo_zh: str
    batch_id: str
    picture: str
    word_id: str

    @classmethod
    def compose(
        cls,
        *,
        term_input: TermInput,
        llm_response: LLMResponse | None,
        field_zh: str,
        batch_id: str,
        word_id: str,
        batch_note: str,
    ) -> "TermOutput":
        def pick(existing: str, generated: str) -> str:
            return existing if existing else generated

        if llm_response:
            ipa = llm_response.ipa
            pos = llm_response.pos
            rarity = pick(term_input.rarity, llm_response.rarity)
            def_en = pick(term_input.def_en, llm_response.def_en)
            example = pick(term_input.example, llm_response.example)
            etymo_en = llm_response.etymo_en
            etymo_zh = llm_response.etymo_zh
            picture = llm_response.picture
        else:
            ipa = term_input.ipa
            pos = term_input.pos
            rarity = term_input.rarity
            def_en = term_input.def_en
            example = term_input.example
            etymo_en = term_input.etymo_en
            etymo_zh = term_input.etymo_zh
            picture = term_input.picture

        resolved_field = term_input.field or field_zh

        missing_required = [
            name
            for name, value in {
                "DefEn": def_en,
                "Example": example,
                "IPA": ipa,
                "POS": pos,
            }.items()
            if not value.strip()
        ]
        if missing_required:
            raise ValueError(
                f"{word_id} 缺少必填字段：{', '.join(missing_required)}；"
                "请检查输入或 LLM 输出。"
            )

        return cls(
            wm_pair=term_input.wm_pair,
            word_en=term_input.word_en,
            mean_zh=term_input.mean_zh,
            def_en=def_en,
            example=example,
            rarity=rarity,
            field=resolved_field,
            batch_note=batch_note,
            ipa=ipa,
            pos=pos,
            etymo_en=etymo_en,
            etymo_zh=etymo_zh,
            batch_id=batch_id,
            picture=picture,
            word_id=word_id,
        )

    def to_csv_row(self) -> list[str]:
        return [
            self.wm_pair,
            self.word_en,
            self.mean_zh,
            self.def_en,
            self.example,
            self.rarity,
            self.field,
            self.batch_note,
            self.ipa,
            self.pos,
            self.etymo_en,
            self.etymo_zh,
            self.batch_id,
            self.picture,
            self.word_id,
        ]


class WordID:
    def __init__(self, index: int):
        if index < 0 or index > 999999:
            raise ValueError("Word 索引必须在 0-999999 范围内")
        self.index = index

    def __str__(self) -> str:
        return f"R{self.index + 1:06d}"

    def __repr__(self) -> str:
        return f"WordID({self.index})"

    @classmethod
    def from_string(cls, word_id: str) -> "WordID":
        if not word_id.startswith("R") or len(word_id) != 7:
            raise ValueError(f"无效的 Word ID 格式：{word_id}")
        return cls(int(word_id[1:]) - 1)
