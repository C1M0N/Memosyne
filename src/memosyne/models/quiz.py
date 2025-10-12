"""
Quiz 数据模型

用于 Lithoformer：解析 Quiz Markdown 文档
"""
from typing import Literal
from pydantic import BaseModel, Field


class QuizOptions(BaseModel):
    """Quiz 选项"""
    A: str = ""
    B: str = ""
    C: str = ""
    D: str = ""
    E: str = ""
    F: str = ""


class QuizItem(BaseModel):
    """单个 Quiz 题目"""

    model_config = {"populate_by_name": True}

    qtype: Literal["MCQ", "CLOZE", "ORDER"] = Field(
        ...,
        description="题型：MCQ=多选题, CLOZE=填空题, ORDER=排序题"
    )
    stem: str = Field(
        ...,
        min_length=1,
        description="题干"
    )
    steps: list[str] = Field(
        default_factory=list,
        description="步骤列表（ORDER 类型使用）"
    )
    options: QuizOptions = Field(
        default_factory=QuizOptions,
        description="选项 A-F"
    )
    answer: str = Field(
        default="",
        pattern=r"^[A-F]?$",
        description="答案字母（MCQ/ORDER）"
    )
    cloze_answers: list[str] = Field(
        default_factory=list,
        description="填空答案列表（CLOZE 类型使用）"
    )


class QuizResponse(BaseModel):
    """LLM 返回的 Quiz 解析结果"""
    items: list[QuizItem] = Field(
        default_factory=list,
        description="解析出的题目列表"
    )
