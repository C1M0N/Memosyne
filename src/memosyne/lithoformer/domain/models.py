"""
Lithoformer Domain Models - Domain entities

Dependency rules:
- Zero external dependencies (only Python stdlib and Pydantic)
- No infrastructure logic (no DB, files, APIs)
- Pure business concepts (Quiz, Question types, etc.)
"""
from typing import Literal
from pydantic import BaseModel, Field, model_validator
import re


OPTION_LETTERS: tuple[str, ...] = tuple(chr(code) for code in range(ord("A"), ord("Z") + 1))


class QuizOptions(BaseModel):
    """Quiz options (A-Z)"""
    A: str = ""
    B: str = ""
    C: str = ""
    D: str = ""
    E: str = ""
    F: str = ""
    G: str = ""
    H: str = ""
    I: str = ""
    J: str = ""
    K: str = ""
    L: str = ""
    M: str = ""
    N: str = ""
    O: str = ""
    P: str = ""
    Q: str = ""
    R: str = ""
    S: str = ""
    T: str = ""
    U: str = ""
    V: str = ""
    W: str = ""
    X: str = ""
    Y: str = ""
    Z: str = ""

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary (filter empty options)"""
        return {k: v for k, v in self.model_dump().items() if v}


class DistractorAnalysis(BaseModel):
    """解析单个错误选项的原因"""
    option: str = Field(..., description="错误选项字母，如 'A'")
    reason: str = Field(..., description="该选项不正确的原因说明")


class QuizAnalysis(BaseModel):
    """题目解析信息"""
    domain: str = Field(..., description="知识领域标签")
    rationale: str = Field(..., description="为什么正确答案正确的核心解释")
    key_points: list[str] = Field(default_factory=list, description="相关知识点列表")
    distractors: list[DistractorAnalysis] = Field(
        default_factory=list,
        description="每个错误选项的说明"
    )


class QuizItem(BaseModel):
    """Single quiz question (domain entity)"""

    model_config = {"populate_by_name": True}

    qtype: Literal["MCQ", "CLOZE"] = Field(
        ...,
        description="Question type: MCQ=Multiple Choice, CLOZE=Fill-in-blank"
    )
    stem: str = Field(
        ...,
        min_length=1,
        description="Question stem"
    )
    stem_translation: str = Field(
        default="",
        description="Stem rendered in Simplified Chinese"
    )
    options: QuizOptions = Field(
        default_factory=QuizOptions,
        description="Options A-Z"
    )
    options_translation: QuizOptions = Field(
        default_factory=QuizOptions,
        description="Options A-Z translated into Simplified Chinese"
    )
    answer: str = Field(
        default="",
        min_length=0,
        description="Answer (MCQ letter or empty string for CLOZE)"
    )
    cloze_answers: list[str] = Field(
        default_factory=list,
        description="Fill-in-blank answers (for CLOZE type)"
    )
    cloze_answers_translation: list[str] = Field(
        default_factory=list,
        description="Translations for cloze answers"
    )
    analysis: QuizAnalysis | None = Field(
        default=None,
        description="题目解析与知识点"
    )

    def is_valid(self, feature_config: "FeatureConfig | None" = None) -> bool:
        """
        Check if quiz item is valid

        Args:
            feature_config: 功能配置，用于决定是否验证translation/analysis字段
        """
        # 基础验证
        if not self.stem:
            return False

        if self.qtype == "MCQ":
            if not (self.options.to_dict() and self.answer):
                return False
        elif self.qtype == "CLOZE":
            if not self.cloze_answers:
                return False
        else:
            return False

        # 根据feature_config决定是否验证analysis
        if feature_config is None or feature_config.enable_parsing:
            if not self.analysis or not self.analysis.domain.strip():
                return False
            if not self.analysis.rationale.strip():
                return False

        # 根据feature_config决定是否验证translation
        if feature_config is None or feature_config.enable_translation:
            if not self.stem_translation.strip():
                return False

            if self.qtype == "MCQ":
                if not any((self.options_translation.model_dump().get(letter) or "").strip() for letter in OPTION_LETTERS):
                    return False
            elif self.qtype == "CLOZE":
                if len(self.cloze_answers) != len(self.cloze_answers_translation):
                    return False

        return True

    @model_validator(mode="after")
    def validate_answer_format(self):
        if self.qtype == "MCQ":
            if not self.answer or not re.fullmatch(r"[A-Z]+", self.answer):
                raise ValueError("MCQ 答案必须为 A-Z 大写字母组合（可多选，连续写，如 ACD）")
        else:  # CLOZE
            # 可为空，或任意字符串
            pass
        return self


class QuizResponse(BaseModel):
    """LLM response containing parsed quiz items"""
    items: list[QuizItem] = Field(
        default_factory=list,
        description="Parsed quiz items"
    )

    @property
    def valid_items(self) -> list[QuizItem]:
        """Get only valid items"""
        return [item for item in self.items if item.is_valid()]


class FeatureConfig(BaseModel):
    """
    功能配置值对象

    控制解析过程中的各项功能开关
    """
    enable_translation: bool = Field(
        default=True,
        description="是否启用翻译功能"
    )
    enable_parsing: bool = Field(
        default=True,
        description="是否启用解析功能（analysis字段）"
    )
    enable_concurrent: bool = Field(
        default=False,
        description="是否启用并发处理"
    )
    max_concurrent: int = Field(
        default=10,
        ge=1,
        le=100,
        description="最大并发数"
    )
    max_retries: int = Field(
        default=1,
        ge=0,
        le=10,
        description="失败重试次数"
    )

    def get_schema_type(self) -> str:
        """
        根据功能配置返回schema类型标识

        Returns:
            schema类型：full/no_translation/no_analysis/minimal
        """
        if self.enable_translation and self.enable_parsing:
            return "full"
        elif not self.enable_translation and self.enable_parsing:
            return "no_translation"
        elif self.enable_translation and not self.enable_parsing:
            return "no_analysis"
        else:
            return "minimal"


# ============================================================
# Usage examples
# ============================================================
if __name__ == "__main__":
    # 1. Create MCQ
    mcq = QuizItem(
        qtype="MCQ",
        stem="What is the capital of France?",
        options=QuizOptions(
            A="London",
            B="Paris",
            C="Berlin",
            D="Madrid"
        ),
        answer="B"
    )
    print(f"✅ MCQ created: {mcq.stem[:30]}...")
    print(f"   Valid: {mcq.is_valid()}")
    print(f"   Answer: {mcq.answer}")

    # 2. Create CLOZE
    cloze = QuizItem(
        qtype="CLOZE",
        stem="The capital of France is ___.",
        cloze_answers=["Paris"]
    )
    print(f"\n✅ CLOZE created: {cloze.stem}")
    print(f"   Answers: {cloze.cloze_answers}")

    # 3. Create Quiz Response
    response = QuizResponse(items=[mcq, cloze])
    print(f"\n✅ Quiz Response: {len(response.items)} items")
    print(f"   Valid items: {len(response.valid_items)}")
