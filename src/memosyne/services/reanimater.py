"""
术语处理服务（Reanimater） - 重构版本

重构改进：
- ✅ 依赖注入：LLM Provider 和配置通过构造函数传入
- ✅ 职责分离：批次 ID 生成委托给 BatchIDGenerator
- ✅ 使用 Pydantic 模型：类型安全的数据流
- ✅ 业务逻辑集中：_post_fixups 移到 LLMResponse 验证器
- ✅ 统一日志系统：使用 logging 而非 print
"""
from __future__ import annotations

import logging

from typing import Iterable
from tqdm import tqdm

from ..core.interfaces import LLMProvider, LLMError
from ..models.term import TermInput, LLMResponse, TermOutput
from ..models.result import ProcessResult, TokenUsage
from ..utils.logger import get_logger


class Reanimater:
    """
    Reanimater - 术语处理服务（重生器）

    负责：
    1. 调用 LLM 生成术语信息
    2. 映射英文标签到中文
    3. 生成 Memo ID 和 BatchID
    4. 组装输出数据

    Example:
        >>> from memosyne.providers import OpenAIProvider
        >>> from memosyne.config import get_settings
        >>>
        >>> settings = get_settings()
        >>> llm = OpenAIProvider.from_settings(settings)
        >>> processor = Reanimater(
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
        logger: logging.Logger | None = None,
    ):
        """
        Args:
            llm_provider: LLM 提供商（实现 complete_prompt 方法）
            term_list_mapping: 术语表映射（英文 -> 两字中文）
            start_memo_index: 起始 Memo 编号（如 2700 表示从 M002701 开始）
            batch_id: 批次 ID
            batch_note: 批次备注
            logger: 日志记录器（None 则使用默认）
        """
        self.llm = llm_provider
        self.term_mapping = term_list_mapping
        self.start_memo = start_memo_index
        self.batch_id = batch_id
        self.batch_note = f"「{batch_note.strip()}」" if batch_note else ""
        self.logger = logger or get_logger("memosyne.reanimater")

    @classmethod
    def from_settings(
        cls,
        settings,
        *,
        llm_provider: LLMProvider,
        start_memo_index: int,
        batch_id: str,
        batch_note: str = "",
        term_list_mapping: dict[str, str] | None = None,
    ) -> "Reanimater":
        """使用 ``Settings`` 对象快速构建 ``Reanimater`` 实例。

        兼容旧版调用方式：若未显式提供 ``term_list_mapping``，会根据
        ``settings.term_list_path`` 自动加载术语表。
        """

        mapping = term_list_mapping
        if mapping is None:
            from ..repositories import TermListRepo  # 延迟导入避免循环依赖

            repo = TermListRepo()
            repo.load(settings.term_list_path)
            mapping = repo.mapping

        return cls(
            llm_provider=llm_provider,
            term_list_mapping=mapping,
            start_memo_index=start_memo_index,
            batch_id=batch_id,
            batch_note=batch_note,
        )

    def process(
        self,
        terms: Iterable[TermInput],
        show_progress: bool = True,
        total: int | None = None
    ) -> ProcessResult[TermOutput]:
        """
        批量处理术语

        Args:
            terms: 术语输入（可以是列表或迭代器）
            show_progress: 是否显示进度条
            total: 术语总数（如果未提供且 terms 有 __len__，会自动获取）

        Returns:
            ProcessResult[TermOutput] - 包含结果列表和 token 统计

        Raises:
            LLMError: LLM 调用失败

        Note:
            为了优化内存使用，本方法不会强制将迭代器转换为列表。
            如果需要显示进度百分比，请传入 total 参数，或确保 terms 有 __len__ 方法。
        """
        results: list[TermOutput] = []
        total_tokens = TokenUsage()

        # 尝试获取总数（避免强制转换为列表）
        if total is None and hasattr(terms, '__len__'):
            try:
                total = len(terms)  # type: ignore[arg-type]
            except TypeError:
                total = None

        progress = None
        try:
            # 配置进度条（显示 Token 使用量）
            if show_progress:
                pbar_kwargs = {
                    "desc": "Processing [Tokens: 0]",
                    "ncols": 100,
                    "ascii": True,
                }
                if total is not None:
                    pbar_kwargs["total"] = total
                progress = tqdm(terms, **pbar_kwargs)
                iterator = enumerate(progress)
            else:
                iterator = enumerate(terms)

            # 处理每个术语
            for index, term_input in iterator:
                try:
                    # 1. 调用 LLM（返回 tuple[dict, TokenUsage]）
                    llm_dict, tokens = self.llm.complete_prompt(
                        word=term_input.word,
                        zh_def=term_input.zh_def
                    )

                    # 累加 Token
                    total_tokens = total_tokens + tokens

                    # 更新进度条显示
                    if show_progress:
                        progress.set_description(f"Processing [Tokens: {total_tokens.total_tokens:,}]")

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
                    self.logger.error(f"LLM 调用失败 [{term_input.word}]: {e}")
                    raise  # 重新抛出，让调用者决定如何处理

                except Exception as e:
                    self.logger.error(f"处理失败 [{term_input.word}]: {e}", exc_info=True)
                    raise
        finally:
            if progress is not None:
                progress.close()

        return ProcessResult(
            items=results,
            success_count=len(results),
            total_count=len(results),
            token_usage=total_tokens,
        )

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

        # 规则3：Example 与 EnDef 相同 → 清空 Example 并记录告警
        if llm_response.example.strip().lower() == llm_response.en_def.strip().lower():
            self.logger.warning(
                f"词条 [{word}] 的 Example 与 EnDef 相同，已清空。"
                f"EnDef: {llm_response.en_def[:50]}..."
            )
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
    from ..providers import OpenAIProvider
    from ..config import get_settings

    # 1. 准备依赖
    settings = get_settings()
    llm_provider = OpenAIProvider.from_settings(settings)

    term_mapping = {
        "psychology": "心理",
        "neuroscience": "神经",
        "biology": "生物",
    }

    # 2. 创建处理器
    processor = Reanimater(
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
