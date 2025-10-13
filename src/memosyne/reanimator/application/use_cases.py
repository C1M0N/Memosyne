"""
Reanimator Application Use Cases - 应用用例（业务协调）

用例 = 业务流程的协调者，编排 Domain 层的业务逻辑。

职责：
- 协调多个领域服务
- 调用端口接口（Infrastructure）
- 处理事务边界
- 返回结果

依赖规则：
- 依赖 Domain 层（models, services）
- 依赖端口接口（Protocol）
- 不依赖具体实现（Adapter）
"""
from typing import Iterable
from tqdm import tqdm

from ..domain.models import TermInput, LLMResponse, TermOutput
from ..domain.services import (
    apply_business_rules,
    get_chinese_tag,
    generate_memo_id,
)
from .ports import LLMPort, TermListPort

# 导入核心模型
from ...core.models import ProcessResult, TokenUsage


class ProcessTermsUseCase:
    """
    处理术语用例（主要业务流程）

    业务流程：
    1. 接收术语输入列表
    2. 对每个术语：
       a. 调用 LLM 生成术语信息
       b. 应用业务规则（POS 修正等）
       c. 映射英文标签到中文
       d. 生成 Memo ID
       e. 组装输出
    3. 返回处理结果

    依赖注入：
    - llm: LLMPort（LLM 调用能力）
    - term_list: TermListPort（术语表查询能力）
    - start_memo_index: 起始 Memo 编号
    - batch_id: 批次 ID
    - batch_note: 批次备注
    """

    def __init__(
        self,
        llm: LLMPort,
        term_list: TermListPort,
        start_memo_index: int,
        batch_id: str,
        batch_note: str = "",
    ):
        """
        Args:
            llm: LLM 端口（由 Infrastructure 层注入）
            term_list: 术语表端口（由 Infrastructure 层注入）
            start_memo_index: 起始 Memo 编号（如 2700 表示从 M002701 开始）
            batch_id: 批次 ID（如 "251007A015"）
            batch_note: 批次备注（可选）
        """
        self.llm = llm
        self.term_list = term_list
        self.start_memo = start_memo_index
        self.batch_id = batch_id
        self.batch_note = f"「{batch_note.strip()}」" if batch_note else ""

    def execute(
        self,
        terms: Iterable[TermInput],
        show_progress: bool = True,
    ) -> ProcessResult[TermOutput]:
        """
        执行用例：处理术语列表

        Args:
            terms: 术语输入（可迭代对象）
            show_progress: 是否显示进度条

        Returns:
            ProcessResult[TermOutput] - 包含结果列表和 token 统计

        Raises:
            LLMError: LLM 调用失败
            ValidationError: 数据验证失败

        Example:
            >>> use_case = ProcessTermsUseCase(
            ...     llm=llm_adapter,
            ...     term_list=term_list_adapter,
            ...     start_memo_index=2700,
            ...     batch_id="251007A015"
            ... )
            >>> result = use_case.execute(terms)
            >>> print(f"Processed {result.success_count} terms")
        """
        results: list[TermOutput] = []
        total_tokens = TokenUsage()

        # 尝试获取总数（避免强制转换为列表）
        total = len(terms) if hasattr(terms, '__len__') else None

        # 配置进度条
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
            progress = None

        try:
            # 处理每个术语
            for index, term_input in iterator:
                # 1. 调用 LLM（通过端口）
                llm_dict, token_dict = self.llm.process_term(
                    word=term_input.word,
                    zh_def=term_input.zh_def
                )

                # 2. 累加 Token
                tokens = TokenUsage(**token_dict)
                total_tokens = total_tokens + tokens

                # 3. 更新进度条
                if show_progress and progress:
                    progress.set_description(
                        f"Processing [Tokens: {total_tokens.total_tokens:,}]"
                    )

                # 4. 转换为领域模型（自动验证）
                llm_response = LLMResponse(**llm_dict)

                # 5. 应用业务规则（领域服务）
                llm_response = apply_business_rules(term_input.word, llm_response)

                # 6. 映射英文标签到中文（领域服务）
                tag_cn = get_chinese_tag(llm_response.tag_en, self.term_list.mapping)

                # 7. 生成 Memo ID（领域服务）
                memo_id = generate_memo_id(self.start_memo, index)

                # 8. 组装输出（领域模型工厂方法）
                output = TermOutput.from_input_and_llm(
                    term_input=term_input,
                    llm_response=llm_response,
                    memo_id=memo_id,
                    tag_cn=tag_cn,
                    batch_id=self.batch_id,
                    batch_note=self.batch_note,
                )

                results.append(output)

        finally:
            if progress is not None:
                progress.close()

        # 返回处理结果
        return ProcessResult(
            items=results,
            success_count=len(results),
            total_count=len(results),
            token_usage=total_tokens,
        )


# ============================================================
# 使用示例（需要 Infrastructure 层提供适配器）
# ============================================================
if __name__ == "__main__":
    print("""
    ProcessTermsUseCase 使用示例：

    # 1. 准备适配器（由 Infrastructure 层提供）
    llm_adapter = ReanimatorLLMAdapter(...)
    term_list_adapter = TermListAdapter(...)

    # 2. 创建用例
    use_case = ProcessTermsUseCase(
        llm=llm_adapter,
        term_list=term_list_adapter,
        start_memo_index=2700,
        batch_id="251007A015",
        batch_note="测试批次"
    )

    # 3. 准备输入
    terms = [
        TermInput(word="neuron", zh_def="神经元"),
        TermInput(word="synapse", zh_def="突触"),
    ]

    # 4. 执行用例
    result = use_case.execute(terms)

    # 5. 输出结果
    print(f"成功处理 {result.success_count} 个术语")
    print(f"Token 使用: {result.token_usage}")
    """)
