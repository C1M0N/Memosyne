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


class QuizOptions(BaseModel):
    """Quiz options (A-F)"""
    A: str = ""
    B: str = ""
    C: str = ""
    D: str = ""
    E: str = ""
    F: str = ""

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

    qtype: Literal["MCQ", "CLOZE", "ORDER"] = Field(
        ...,
        description="Question type: MCQ=Multiple Choice, CLOZE=Fill-in-blank, ORDER=Ordering"
    )
    stem: str = Field(
        ...,
        min_length=1,
        description="Question stem"
    )
    stem_translation: str = Field(
        ...,
        min_length=1,
        description="Stem rendered in Simplified Chinese"
    )
    steps: list[str] = Field(
        default_factory=list,
        description="Step list (for ORDER type)"
    )
    steps_translation: list[str] = Field(
        default_factory=list,
        description="Steps translated into Simplified Chinese"
    )
    options: QuizOptions = Field(
        default_factory=QuizOptions,
        description="Options A-F"
    )
    options_translation: QuizOptions = Field(
        default_factory=QuizOptions,
        description="Options A-F translated into Simplified Chinese"
    )
    answer: str = Field(
        default="",
        min_length=0,
        description="Answer (MCQ/ORDER/CLOZE)"
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

    def is_valid(self) -> bool:
        """Check if quiz item is valid"""
        if not self.stem:
            return False

        if self.qtype == "MCQ":
            if not (self.options.to_dict() and self.answer):
                return False
        elif self.qtype == "CLOZE":
            if not self.cloze_answers:
                return False
        elif self.qtype == "ORDER":
            if not (self.steps and self.answer):
                return False
        else:
            return False

        if not self.analysis or not self.analysis.domain.strip():
            return False
        if not self.analysis.rationale.strip():
            return False

        if not self.stem_translation.strip():
            return False

        if self.qtype == "MCQ":
            if not any((self.options_translation.model_dump().get(letter) or "").strip() for letter in ["A", "B", "C", "D", "E", "F"]):
                return False
        elif self.qtype == "ORDER":
            if len(self.steps) != len(self.steps_translation):
                return False
        elif self.qtype == "CLOZE":
            if len(self.cloze_answers) != len(self.cloze_answers_translation):
                return False

        return True

    @model_validator(mode="after")
    def validate_answer_format(self):
        if self.qtype == "MCQ":
            if not self.answer or not re.fullmatch(r"[A-F]+", self.answer):
                raise ValueError("MCQ 答案必须为 A-F 字母组合（可多选，连续写，如 ACD）")
        elif self.qtype == "ORDER":
            if not self.answer or not re.fullmatch(r"[A-F](,[A-F])*", self.answer):
                raise ValueError("ORDER 答案必须为以逗号分隔的 A-F 字母序列")
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
