"""
术语处理服务 - 重构版本

重构改进：
- ✅ 依赖注入：LLM Provider 和配置通过构造函数传入
- ✅ 职责分离：批次 ID 生成委托给 BatchIDGenerator
- ✅ 使用 Pydantic 模型：类型安全的数据流
- ✅ 业务逻辑集中：_post_fixups 移到 LLMResponse 验证器
"""
from typing import Iterable
from tqdm import tqdm

from ..core.interfaces import LLMProvider, LLMError
from ..models.term import TermInput, LLMResponse, TermOutput
from ..utils.batch import BatchIDGenerator


class TermProcessor:
    """
    术语处理服务

    负责：
    1. 调用 LLM 生成术语信息
    2. 映射英文标签到中文
    3. 生成 Memo ID 和 BatchID
    4. 组装输出数据

    Example:
        >>> from providers.openai import OpenAIProvider
        >>> from config.settings import get_settings
        >>>
        >>> settings = get_settings()
        >>> llm = OpenAIProvider.from_settings(settings)
        >>> processor = TermProcessor(
        ...     llm_provider=llm,
        ...     term_list_mapping={"psychology": "心理"},
        ...     start_memo_index=2700,
        ...     batch_id="251007A015",
        ...     batch_note="测试批次"
        ... )
        >>> terms = [TermInput(word="neuron", zh_def="神经元")]
        >>> results = processor.process(terms)
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        term_list_mapping: dict[str, str],
        start_memo_index: int,
        batch_id: str,
        batch_note: str = "",
    ):
        """
        Args:
            llm_provider: LLM 提供商（实现 complete_prompt 方法）
            term_list_mapping: 术语表映射（英文 -> 两字中文）
            start_memo_index: 起始 Memo 编号（如 2700 表示从 M002701 开始）
            batch_id: 批次 ID
            batch_note: 批次备注
        """
        self.llm = llm_provider
        self.term_mapping = term_list_mapping
        self.start_memo = start_memo_index
        self.batch_id = batch_id
        self.batch_note = f"「{batch_note.strip()}」" if batch_note else ""

    def process(
        self,
        terms: Iterable[TermInput],
        show_progress: bool = True
    ) -> list[TermOutput]:
        """
        批量处理术语

        Args:
            terms: 术语输入列表
            show_progress: 是否显示进度条

        Returns:
            术语输出列表

        Raises:
            LLMError: LLM 调用失败
        """
        results: list[TermOutput] = []
        term_list = list(terms)  # 转为列表以便计算总数

        # 配置进度条
        iterator = enumerate(term_list)
        if show_progress:
            iterator = enumerate(
                tqdm(
                    term_list,
                    desc="LLM Processing",
                    total=len(term_list),
                    ncols=80,
                    ascii=True,
                    bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]"
                )
            )

        # 处理每个术语
        for index, term_input in iterator:
            try:
                # 1. 调用 LLM
                llm_dict = self.llm.complete_prompt(
                    word=term_input.word,
                    zh_def=term_input.zh_def
                )

                # 2. 转换为 Pydantic 模型（自动验证）
                llm_response = LLMResponse(**llm_dict)

                # 3. 后处理：词组强制标记为 P.
                llm_response = self._apply_business_rules(term_input.word, llm_response)

                # 4. 映射英文标签到中文
                tag_cn = self._get_chinese_tag(llm_response.tag_en)

                # 5. 生成 Memo ID
                memo_id = self._generate_memo_id(index)

                # 6. 组装输出
                output = TermOutput.from_input_and_llm(
                    term_input=term_input,
                    llm_response=llm_response,
                    memo_id=memo_id,
                    tag_cn=tag_cn,
                    batch_id=self.batch_id,
                    batch_note=self.batch_note,
                )

                results.append(output)

            except LLMError as e:
                print(f"❌ LLM 调用失败 [{term_input.word}]: {e}")
                raise  # 重新抛出，让调用者决定如何处理

            except Exception as e:
                print(f"❌ 处理失败 [{term_input.word}]: {e}")
                raise

        return results

    def _apply_business_rules(
        self,
        word: str,
        llm_response: LLMResponse
    ) -> LLMResponse:
        """
        应用业务规则（仅保留与 schema 无重叠的逻辑）

        Args:
            word: 原始词条
            llm_response: LLM 响应

        Returns:
            修正后的响应
        """
        # 规则1：词组（含空格）→ 强制 POS='P.'（但 abbr. 例外）
        if " " in word and llm_response.pos != "abbr.":
            llm_response.pos = "P."

        # 规则2：缩写词 → IPA 必须为空（已在 LLMResponse 验证器处理）

        # 规则3：Example 与 EnDef 相同 → 清空 Example
        if llm_response.example.strip().lower() == llm_response.en_def.strip().lower():
            llm_response.example = ""

        # 规则4：PPfix/PPmeans 规范化（小写、空白折叠）
        llm_response.pp_fix = " ".join(llm_response.pp_fix.lower().split())
        llm_response.pp_means = " ".join(llm_response.pp_means.lower().split())

        return llm_response

    def _get_chinese_tag(self, tag_en: str) -> str:
        """
        获取中文标签（精确匹配或宽松包含匹配）

        Args:
            tag_en: 英文标签

        Returns:
            两字中文标签（找不到返回空字符串）
        """
        tag_lower = tag_en.strip().lower()

        if not tag_lower:
            return ""

        # 1. 精确匹配
        if tag_lower in self.term_mapping:
            return self.term_mapping[tag_lower]

        # 2. 宽松包含匹配（如 "neurobiology" 匹配 "biology"）
        for en_key, cn_value in self.term_mapping.items():
            if en_key and en_key in tag_lower:
                return cn_value

        return ""

    def _generate_memo_id(self, index: int) -> str:
        """
        生成 Memo ID（格式：M + 6位数字）

        Args:
            index: 当前词条索引（从0开始）

        Returns:
            Memo ID（如 "M002701"）
        """
        # start_memo=2700, index=0 → M002701
        memo_num = self.start_memo + index + 1
        return f"M{memo_num:06d}"


# ============================================================
# 使用示例
# ============================================================
if __name__ == "__main__":
    from ..providers.openai import OpenAIProvider
    from ..config.settings import get_settings

    # 1. 准备依赖
    settings = get_settings()
    llm_provider = OpenAIProvider.from_settings(settings)

    term_mapping = {
        "psychology": "心理",
        "neuroscience": "神经",
        "biology": "生物",
    }

    # 2. 创建处理器
    processor = TermProcessor(
        llm_provider=llm_provider,
        term_list_mapping=term_mapping,
        start_memo_index=2700,
        batch_id="251007A003",
        batch_note="示例批次"
    )

    # 3. 准备输入
    terms = [
        TermInput(word="neuron", zh_def="神经元"),
        TermInput(word="synapse", zh_def="突触"),
        TermInput(word="hippocampus", zh_def="海马体"),
    ]

    # 4. 处理
    results = processor.process(terms)

    # 5. 输出
    for result in results:
        print(f"{result.memo_id}: {result.word} - {result.zh_def}")
        print(f"  IPA: {result.ipa}, POS: {result.pos}")
        print(f"  EnDef: {result.en_def}")
        print()
