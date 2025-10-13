"""
Reanimator Domain Exceptions - 领域异常

依赖原则：
- ✅ 零外部依赖（仅依赖 Python 标准库）
- ✅ 表达业务错误（而非技术错误）

异常层次：
- ReanimatorDomainError (基类) - 所有领域异常的基类
  ├── InvalidTermError - 无效的术语输入
  ├── InvalidMemoIDError - 无效的 Memo ID
  └── ValidationError - 业务验证失败
"""


class ReanimatorDomainError(Exception):
    """Reanimator 领域异常基类"""
    pass


class InvalidTermError(ReanimatorDomainError):
    """无效的术语输入"""

    def __init__(self, word: str, reason: str):
        self.word = word
        self.reason = reason
        super().__init__(f"无效的术语 '{word}': {reason}")


class InvalidMemoIDError(ReanimatorDomainError):
    """无效的 Memo ID"""

    def __init__(self, memo_id: str, reason: str = ""):
        self.memo_id = memo_id
        self.reason = reason
        msg = f"无效的 Memo ID '{memo_id}'"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)


class TermValidationError(ReanimatorDomainError):
    """术语业务验证失败"""

    def __init__(self, field: str, value: str, constraint: str):
        self.field = field
        self.value = value
        self.constraint = constraint
        super().__init__(
            f"字段 '{field}' 验证失败：值 '{value}' 不符合约束 '{constraint}'"
        )


class POSCorrectionError(ReanimatorDomainError):
    """POS 修正失败"""

    def __init__(self, word: str, detected_pos: str, reason: str):
        self.word = word
        self.detected_pos = detected_pos
        self.reason = reason
        super().__init__(
            f"词性修正失败 '{word}' (检测到 {detected_pos}): {reason}"
        )
