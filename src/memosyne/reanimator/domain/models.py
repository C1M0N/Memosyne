"""
Reanimator Domain Models - 领域模型（纯业务实体）

依赖原则：
- ✅ 零外部依赖（仅依赖 Python 标准库和 Pydantic）
- ✅ 无基础设施逻辑（不涉及数据库、文件、API）
- ✅ 纯业务概念（术语、Memo ID、词性等）

重构改进：
- ✅ 运行时验证：自动检查字段类型和约束
- ✅ 序列化：JSON/dict 互转零成本
- ✅ 文档生成：字段描述自动生成 JSON Schema
- ✅ IDE 支持：完整的类型提示和自动补全
"""
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator


# ============================================================
# 输入模型
# ============================================================
class TermInput(BaseModel):
    """术语输入（从外部数据源读取）"""

    word: str = Field(
        ...,
        min_length=1,
        description="英文词条",
        examples=["neuroscience", "hippocampus"]
    )
    zh_def: str = Field(
        ...,
        min_length=1,
        description="中文释义",
        examples=["神经科学", "海马体"]
    )

    @field_validator("word", "zh_def")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        """去除首尾空白"""
        stripped = v.strip()
        if not stripped:
            raise ValueError("字段不能为空或仅包含空白")
        return stripped

    @model_validator(mode="after")
    def validate_word_not_chinese(self):
        """确保 word 不是纯中文"""
        if all('\u4e00' <= c <= '\u9fff' for c in self.word if not c.isspace()):
            raise ValueError(f"word 字段不应为中文：{self.word}")
        return self


# ============================================================
# LLM 响应模型
# ============================================================
class LLMResponse(BaseModel):
    """LLM 返回的术语信息"""

    model_config = {"populate_by_name": True}  # 允许使用别名或字段名

    ipa: str = Field(
        default="",
        pattern=r"^(\/[^\s\/].*\/|)$",
        description="美式 IPA 音标",
        alias="IPA"
    )
    pos: Literal["n.", "vt.", "vi.", "adj.", "adv.", "P.", "O.", "abbr."] = Field(
        ...,
        description="词性",
        alias="POS"
    )
    rarity: Literal["", "RARE"] = Field(
        default="",
        description="稀有度标记",
        alias="Rarity"
    )
    en_def: str = Field(
        ...,
        min_length=1,
        description="英文定义（必须包含目标词）",
        alias="EnDef"
    )
    example: str = Field(
        ...,
        min_length=1,
        description="例句（必须包含目标词）",
        alias="Example"
    )
    pp_fix: str = Field(
        default="",
        description="词根词缀（空格分隔）",
        examples=["psycho neuro"],
        alias="PPfix"
    )
    pp_means: str = Field(
        default="",
        pattern=r"^[\x20-\x7E]*$",  # 仅 ASCII
        description="词根词缀含义（空格分隔）",
        examples=["mind nerve"],
        alias="PPmeans"
    )
    tag_en: str = Field(
        default="",
        description="英文领域标签",
        examples=["psychology", "neuroscience"],
        alias="TagEN"
    )

    @model_validator(mode="after")
    def validate_abbr_no_ipa(self):
        """缩写词不应有 IPA"""
        if self.pos == "abbr." and self.ipa:
            self.ipa = ""
        return self


# ============================================================
# 输出模型
# ============================================================
class TermOutput(BaseModel):
    """术语输出（待写入外部存储）"""

    wm_pair: str = Field(..., description="词义对")
    memo_id: str = Field(..., pattern=r"^M\d{6}$", description="Memo ID")
    word: str = Field(..., min_length=1)
    zh_def: str = Field(..., min_length=1)
    ipa: str = Field(default="")
    pos: str = Field(...)
    tag: str = Field(default="", description="中文标签")
    rarity: str = Field(default="")
    en_def: str = Field(...)
    example: str = Field(...)
    pp_fix: str = Field(default="")
    pp_means: str = Field(default="")
    batch_id: str = Field(..., pattern=r"^\d{6}[A-Z]\d{3}$")
    batch_note: str = Field(default="")

    @classmethod
    def from_input_and_llm(
        cls,
        term_input: TermInput,
        llm_response: LLMResponse,
        memo_id: str,
        tag_cn: str,
        batch_id: str,
        batch_note: str = ""
    ) -> "TermOutput":
        """从输入和 LLM 响应构造输出（工厂方法）"""
        return cls(
            wm_pair=f"{term_input.word} - {term_input.zh_def}",
            memo_id=memo_id,
            word=term_input.word,
            zh_def=term_input.zh_def,
            ipa=llm_response.ipa,
            pos=llm_response.pos,
            tag=tag_cn,
            rarity=llm_response.rarity,
            en_def=llm_response.en_def,
            example=llm_response.example,
            pp_fix=llm_response.pp_fix,
            pp_means=llm_response.pp_means,
            batch_id=batch_id,
            batch_note=batch_note,
        )

    def to_csv_row(self) -> list[str]:
        """转换为 CSV 行（按固定顺序）"""
        return [
            self.wm_pair,
            self.memo_id,
            self.word,
            self.zh_def,
            self.ipa,
            self.pos,
            self.tag,
            self.rarity,
            self.en_def,
            self.example,
            self.pp_fix,
            self.pp_means,
            self.batch_id,
            self.batch_note,
        ]


# ============================================================
# MemoID 值对象
# ============================================================
class MemoID:
    """Memo ID 值对象（格式：M + 6位数字）"""

    def __init__(self, index: int):
        """
        从索引创建 Memo ID

        Args:
            index: Memo 编号（如 2700 表示 M002701）

        Example:
            >>> mid = MemoID(2700)
            >>> str(mid)
            'M002701'
        """
        if index < 0 or index > 999999:
            raise ValueError(f"Memo 索引必须在 0-999999 范围内：{index}")
        self.index = index

    def __str__(self) -> str:
        """返回格式化的 Memo ID"""
        return f"M{self.index + 1:06d}"

    def __repr__(self) -> str:
        return f"MemoID({self.index})"

    @classmethod
    def from_string(cls, memo_id: str) -> "MemoID":
        """
        从字符串解析 Memo ID

        Example:
            >>> mid = MemoID.from_string("M002701")
            >>> mid.index
            2700
        """
        if not memo_id.startswith("M") or len(memo_id) != 7:
            raise ValueError(f"无效的 Memo ID 格式：{memo_id}")
        try:
            number = int(memo_id[1:])
            return cls(number - 1)
        except ValueError as e:
            raise ValueError(f"无效的 Memo ID 格式：{memo_id}") from e


# ============================================================
# 使用示例
# ============================================================
if __name__ == "__main__":
    # 1. 创建输入
    term_in = TermInput(word="neuroscience", zh_def="神经科学")
    print(term_in.model_dump())

    # 2. 模拟 LLM 响应
    llm_resp = LLMResponse(
        IPA="/ˈnʊroʊˌsaɪəns/",
        POS="n.",
        EnDef="The scientific study of the nervous system.",
        Example="Neuroscience has made great advances in recent years.",
        TagEN="neuroscience"
    )

    # 3. 生成输出
    memo_id = MemoID(2700)
    output = TermOutput.from_input_and_llm(
        term_input=term_in,
        llm_response=llm_resp,
        memo_id=str(memo_id),
        tag_cn="神经",
        batch_id="251007A001",
        batch_note="测试批次"
    )

    print(f"✅ 创建术语输出：{output.wm_pair}")
    print(f"   Memo ID: {output.memo_id}")
    print(f"   词性: {output.pos}")
