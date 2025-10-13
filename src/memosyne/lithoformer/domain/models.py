"""
Lithoformer Domain Models - Domain entities

Dependency rules:
- Zero external dependencies (only Python stdlib and Pydantic)
- No infrastructure logic (no DB, files, APIs)
- Pure business concepts (Quiz, Question types, etc.)
"""
from typing import Literal
from pydantic import BaseModel, Field


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
    steps: list[str] = Field(
        default_factory=list,
        description="Step list (for ORDER type)"
    )
    options: QuizOptions = Field(
        default_factory=QuizOptions,
        description="Options A-F"
    )
    answer: str = Field(
        default="",
        pattern=r"^[A-F]?$",
        description="Answer letter (for MCQ/ORDER)"
    )
    cloze_answers: list[str] = Field(
        default_factory=list,
        description="Fill-in-blank answers (for CLOZE type)"
    )

    def is_valid(self) -> bool:
        """Check if quiz item is valid"""
        if not self.stem:
            return False

        if self.qtype == "MCQ":
            # MCQ needs options and answer
            return bool(self.options.to_dict() and self.answer)
        elif self.qtype == "CLOZE":
            # CLOZE needs cloze_answers
            return bool(self.cloze_answers)
        elif self.qtype == "ORDER":
            # ORDER needs steps and answer
            return bool(self.steps and self.answer)

        return False


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
