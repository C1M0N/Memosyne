# Phase 4: Ports & Adapters 架构设计

**版本**: v0.8.0
**日期**: 2025-10-13
**目标**: 重构为六边形架构（Hexagonal Architecture），实现依赖倒置和高度模块化

---

## 1. 新目录结构

```
src/memosyne/
├── reanimator/              # Reanimator 子域（术语处理）
│   ├── __init__.py
│   ├── domain/              # 领域层（纯业务逻辑，零依赖）
│   │   ├── __init__.py
│   │   ├── models.py        # TermInput, TermOutput, MemoID
│   │   ├── services.py      # 领域服务：POS修正、标签映射
│   │   └── exceptions.py    # 领域异常：InvalidTermError
│   ├── application/         # 应用层（用例协调）
│   │   ├── __init__.py
│   │   ├── ports.py         # 端口接口（Protocol）
│   │   │                    # - LLMPort, TermRepositoryPort, TermListPort
│   │   └── use_cases.py     # ProcessTermsUseCase（主要用例）
│   ├── infrastructure/      # 基础设施层（适配器实现）
│   │   ├── __init__.py
│   │   ├── llm_adapter.py   # LLM 适配器（调用 shared.llm）
│   │   ├── csv_adapter.py   # CSV 读写适配器
│   │   └── term_list_adapter.py  # 术语表适配器
│   └── cli/                 # CLI 入口（薄适配器）
│       ├── __init__.py
│       └── main.py          # reanimator_cli.py 迁移到这里
│
├── lithoformer/             # Lithoformer 子域（Quiz 解析）
│   ├── __init__.py
│   ├── domain/              # 领域层
│   │   ├── __init__.py
│   │   ├── models.py        # QuizItem, QuizType
│   │   ├── services.py      # Quiz 格式化服务
│   │   └── exceptions.py    # 领域异常：InvalidQuizError
│   ├── application/         # 应用层
│   │   ├── __init__.py
│   │   ├── ports.py         # 端口接口
│   │   │                    # - LLMPort, FileRepositoryPort
│   │   └── use_cases.py     # ParseQuizUseCase
│   ├── infrastructure/      # 基础设施层
│   │   ├── __init__.py
│   │   ├── llm_adapter.py   # LLM 适配器
│   │   └── file_adapter.py  # 文件读写适配器
│   └── cli/                 # CLI 入口
│       ├── __init__.py
│       └── main.py          # lithoformer_cli.py 迁移到这里
│
├── shared/                  # 共享基础设施（可重用组件）
│   ├── __init__.py
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   ├── llm/             # LLM 提供商
│   │   │   ├── __init__.py
│   │   │   ├── interfaces.py    # BaseLLMProvider Protocol
│   │   │   ├── openai_provider.py
│   │   │   ├── anthropic_provider.py
│   │   │   └── factory.py       # create_provider() 工厂函数
│   │   ├── storage/         # 存储层
│   │   │   ├── __init__.py
│   │   │   ├── csv_repository.py
│   │   │   └── file_repository.py
│   │   └── logging/         # 日志系统
│   │       ├── __init__.py
│   │       └── logger.py
│   ├── config/              # 配置管理
│   │   ├── __init__.py
│   │   └── settings.py
│   └── utils/               # 工具类
│       ├── __init__.py
│       ├── batch.py         # BatchIDGenerator
│       ├── filename.py      # 文件命名工具
│       ├── model_codes.py   # 模型代码映射
│       └── path.py          # 路径工具
│
├── api.py                   # 顶层 API 入口（Facade 模式）
└── __init__.py              # 包初始化，导出公共接口
```

---

## 2. 端口接口定义（Ports）

### 2.1 Reanimator 端口

**`reanimator/application/ports.py`**:

```python
from typing import Protocol
from ..domain.models import TermInput, TermOutput

class LLMPort(Protocol):
    """LLM 调用端口"""
    def process_term(self, word: str, zh_def: str) -> dict:
        """处理单个术语，返回 LLM 响应"""
        ...

class TermRepositoryPort(Protocol):
    """术语存储端口"""
    def read_input(self, path: Path) -> list[TermInput]:
        """读取输入术语"""
        ...

    def write_output(self, path: Path, terms: list[TermOutput]) -> None:
        """写出处理结果"""
        ...

class TermListPort(Protocol):
    """术语表端口"""
    def get_chinese_tag(self, english_tag: str) -> str:
        """英文标签 → 中文标签"""
        ...
```

### 2.2 Lithoformer 端口

**`lithoformer/application/ports.py`**:

```python
from typing import Protocol
from ..domain.models import QuizItem

class LLMPort(Protocol):
    """LLM 调用端口"""
    def parse_quiz(self, markdown: str) -> dict:
        """解析 Quiz Markdown，返回结构化数据"""
        ...

class FileRepositoryPort(Protocol):
    """文件存储端口"""
    def read_markdown(self, path: Path) -> str:
        """读取 Markdown 文件"""
        ...

    def write_text(self, path: Path, content: str) -> None:
        """写出文本文件"""
        ...
```

---

## 3. 依赖关系图

```
┌─────────────────────────────────────────────────────┐
│                      CLI 层                          │
│  (reanimator/cli, lithoformer/cli)                  │
└──────────────────┬──────────────────────────────────┘
                   │ 依赖
                   ↓
┌─────────────────────────────────────────────────────┐
│                   应用层 (Application)                │
│              use_cases.py (用例协调)                 │
└──────────────────┬──────────────────────────────────┘
                   │ 依赖
                   ↓
┌─────────────────────────────────────────────────────┐
│                  领域层 (Domain)                     │
│         models.py, services.py (纯业务逻辑)          │
└─────────────────────────────────────────────────────┘
         ↑                                  ↑
         │ 实现端口                          │ 实现端口
         │                                  │
┌────────┴────────┐                ┌───────┴─────────┐
│  Infrastructure  │                │  Shared Infra   │
│  (domain-specific│                │  (reusable)     │
│   adapters)      │                │                 │
└──────────────────┘                └─────────────────┘
```

**依赖规则**:
1. **Domain** 层：零外部依赖，只依赖 Python 标准库和 Pydantic
2. **Application** 层：依赖 Domain，定义端口接口（Protocol）
3. **Infrastructure** 层：依赖 Application 和 Domain，实现端口接口
4. **CLI** 层：依赖 Application 和 Infrastructure，负责依赖注入

**关键原则**: 依赖箭头永远指向内层（Domain ← Application ← Infrastructure ← CLI）

---

## 4. 迁移路径（Migration Path）

### 4.1 第一阶段：创建新结构（不破坏现有功能）

1. **创建目录和 `__init__.py`**
   - 创建所有新目录
   - 创建空的 `__init__.py` 文件

2. **迁移 Domain 层**（最内层，零依赖）
   - `reanimator/domain/models.py` ← `models/term.py`
   - `reanimator/domain/services.py` ← 从 `services/reanimator.py` 提取业务逻辑
   - `lithoformer/domain/models.py` ← `models/quiz.py`
   - `lithoformer/domain/services.py` ← 从 `services/lithoformer.py` 提取格式化逻辑

3. **定义 Application 层**（端口和用例）
   - `reanimator/application/ports.py` - 定义接口
   - `reanimator/application/use_cases.py` - ProcessTermsUseCase
   - `lithoformer/application/ports.py` - 定义接口
   - `lithoformer/application/use_cases.py` - ParseQuizUseCase

4. **实现 Infrastructure 层**（适配器）
   - `reanimator/infrastructure/llm_adapter.py` - 实现 LLMPort
   - `reanimator/infrastructure/csv_adapter.py` - 实现 TermRepositoryPort
   - `reanimator/infrastructure/term_list_adapter.py` - 实现 TermListPort
   - `lithoformer/infrastructure/llm_adapter.py` - 实现 LLMPort
   - `lithoformer/infrastructure/file_adapter.py` - 实现 FileRepositoryPort

5. **迁移 Shared 层**
   - `shared/infrastructure/llm/` ← `providers/`
   - `shared/infrastructure/storage/` ← `repositories/`
   - `shared/infrastructure/logging/` ← `utils/logger.py`
   - `shared/config/` ← `config/`
   - `shared/utils/` ← `utils/`

6. **迁移 CLI 层**
   - `reanimator/cli/main.py` ← `cli/reanimator_cli.py`
   - `lithoformer/cli/main.py` ← `cli/lithoformer_cli.py`

7. **更新顶层 API**
   - 重构 `api.py` 使用新的 Use Case
   - 更新 `__init__.py` 导出接口

### 4.2 第二阶段：验证和清理

1. **验证功能**
   - 运行 Reanimator CLI 测试
   - 运行 Lithoformer CLI 测试
   - 验证 API 接口

2. **删除旧代码**
   - 删除 `services/` 目录
   - 删除 `repositories/` 目录（已迁移到 shared）
   - 删除 `providers/` 目录（已迁移到 shared）
   - 删除 `models/` 目录（已迁移到各子域）
   - 删除 `core/` 目录（如果已迁移完）
   - 删除旧的 `cli/` 目录（CLI 已迁移到各子域）

3. **更新文档**
   - 更新 `CLAUDE.md` 说明新架构
   - 更新 `README.md`
   - 更新 `ARCHITECTURE.md`

---

## 5. 关键设计决策

### 5.1 为什么使用 Protocol 而不是 ABC？

- Protocol 支持鸭子类型（structural subtyping）
- 不需要显式继承，更灵活
- 更符合 Python 的风格

### 5.2 为什么两个子域各有自己的 LLM Adapter？

- 虽然都调用 LLM，但业务语义不同：
  - Reanimator: `process_term(word, zh_def)` - 术语处理
  - Lithoformer: `parse_quiz(markdown)` - Quiz 解析
- 各自的 Adapter 可以封装特定的 Prompt 和错误处理
- 保持子域的独立性

### 5.3 为什么 Shared 层可以被重用？

- 这些是纯技术组件，无业务含义：
  - LLM Provider: 只负责 HTTP 调用
  - Storage: 只负责文件读写
  - Logger: 只负责日志记录
- 不同子域可以根据需要选择使用

---

## 6. 测试策略

### 6.1 Domain 层测试
- 纯单元测试，无 Mock
- 测试业务规则（POS 修正、标签映射等）

### 6.2 Application 层测试
- Mock 所有端口（LLMPort, RepositoryPort 等）
- 测试用例协调逻辑

### 6.3 Infrastructure 层测试
- 集成测试，测试真实的适配器实现
- 可以 Mock 外部服务（如 LLM API）

### 6.4 CLI 层测试
- 端到端测试
- 测试完整的依赖注入流程

---

## 7. 下一步行动

1. ✅ 创建此文档
2. [ ] 创建所有新目录结构
3. [ ] 迁移 Reanimator Domain 层
4. [ ] 迁移 Lithoformer Domain 层
5. [ ] 实现 Application 层（端口和用例）
6. [ ] 实现 Infrastructure 层（适配器）
7. [ ] 迁移 Shared 层
8. [ ] 迁移 CLI 层
9. [ ] 更新顶层 API
10. [ ] 验证功能完整性
11. [ ] 删除旧代码
12. [ ] 更新文档

---

**状态**: 📋 规划完成，准备开始实施
