# AGENTS.md

This document captures shared memory and working agreements for AI coding agents collaborating on the Memosyne project (e.g., Claude Code, ChatGPT / OpenAI Code Interpreter, or other assistants invoked by the team).

## 项目概述

Memosyne 是一个基于 LLM（OpenAI/Anthropic）的术语处理和测验解析工具。

**版本信息**:
- **v0.9.1a** (当前) - 数据更新，新增测验文件
- **v0.9.1** - 生产就绪版本
- **v0.9.0** - DDD + Hexagonal 架构，Lithoformer 支持逐题中文解析

**核心架构模式**：
- **Domain-Driven Design (DDD)** - 领域驱动设计
- **Hexagonal Architecture** - 六边形架构（端口适配器模式）
- **Bounded Contexts** - Reanimator 和 Lithoformer 作为独立子域
- **Shared Kernel** - 业务无关的基础设施

主要功能：
1. **Reanimator（术语重生器）** - 术语记忆处理管道，生成结构化术语卡片
2. **Lithoformer（Quiz 重塑器）** - 测验解析器，将 Markdown 测验转换为标准化格式（输入使用 ```Question``` / ```Answer``` 配对代码块，并为每题生成详细解析）

---

## 常用命令

### 运行项目

```bash
# 方式 1: 模块执行（推荐）
python -m memosyne.reanimator.cli.main    # Reanimator - 术语重生
python -m memosyne.lithoformer.cli.main   # Lithoformer - Quiz 重塑

# 方式 2: 便捷脚本
./run_reanimate.sh     # Reanimator
./run_lithoform.sh     # Lithoformer

# 方式 3: 编程 API
python -c "from memosyne.api import reanimate; help(reanimate)"
python -c "from memosyne.api import lithoform; help(lithoform)"
```

### 依赖管理

```bash
# 安装依赖
pip install -r requirements.txt

# 创建虚拟环境（推荐）
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows
```

### 环境配置

项目提供 `.env.example` 模板文件，首次使用时复制并配置：
```bash
cp .env.example .env
# 编辑 .env 文件，填入真实的 API 密钥
```

`.env` 文件示例：
```bash
OPENAI_API_KEY=your-key-here
ANTHROPIC_API_KEY=your-key-here  # 可选
DEFAULT_OPENAI_MODEL=gpt-4o-mini
DEFAULT_ANTHROPIC_MODEL=claude-sonnet-4-5
LOG_LEVEL=INFO

# 配置项示例：
# BATCH_TIMEZONE=America/New_York
# REANIMATOR_TERM_LIST_VERSION=1
```

**注意**: `.env` 文件已在 `.gitignore` 中，绝不能提交到版本控制。

### 集中配置管理

模型名称现已集中配置，**只需在一处修改**即可全局生效：

1. **修改 `.env` 文件**（推荐）：
   ```bash
   DEFAULT_OPENAI_MODEL=gpt-4o-mini
   DEFAULT_ANTHROPIC_MODEL=claude-sonnet-4-5
   ```

2. **或修改 `settings.py`**（作为代码默认值）：
   ```python
   # src/memosyne/shared/config/settings.py
   default_openai_model: str = "gpt-4o-mini"
   default_anthropic_model: str = "claude-sonnet-4-5"
   ```

**CLI 快捷方式自动使用配置**：
- 输入 `4` → 使用 `DEFAULT_OPENAI_MODEL`（通常是 gpt-4o-mini）
- 输入 `claude` → 使用 `DEFAULT_ANTHROPIC_MODEL`（通常是 claude-sonnet-4-5）
- 输入完整模型ID → 直接使用该模型

**推荐的 Anthropic 模型别名**（官方推荐，自动使用最新版本）：
- `claude-sonnet-4-5` ✅ (推荐，最强大的 Claude 3.5 Sonnet)
- `claude-opus-4` ✅ (Claude 3 Opus)
- `claude-haiku-4` ✅ (Claude 3.5 Haiku，更快，成本更低)

**也可使用完整版本号**（固定版本）：
- `claude-3-5-sonnet-20240620`
- `claude-3-5-haiku-20241022`
- `claude-3-opus-20240229`

---

## 核心架构 (v0.9.1a - DDD + Hexagonal)

### DDD 分层架构

```
┌─────────────────────────────────────────────────────────┐
│                    CLI / API Layer                      │  用户接口
│              (reanimator/cli, lithoformer/cli, api.py)  │
├─────────────────────────────────────────────────────────┤
│              Infrastructure Layer (Adapters)            │  适配器实现
│    (llm_adapter, csv_adapter, file_adapter, ...)        │
├─────────────────────────────────────────────────────────┤
│           Application Layer (Use Cases + Ports)         │  业务协调
│  (ProcessTermsUseCase, ParseQuizUseCase, Ports)         │
├─────────────────────────────────────────────────────────┤
│           Domain Layer (Models + Services)              │  核心业务逻辑
│   (TermInput/Output, QuizItem, business rules)          │
├─────────────────────────────────────────────────────────┤
│        Shared Kernel (Core + Shared Infrastructure)    │  共享基础设施
│  (TokenUsage, ProcessResult, Config, LLM Providers)     │
└─────────────────────────────────────────────────────────┘
```

### 项目结构

```
src/memosyne/
├── core/                           # 核心层（抽象接口、核心模型）
│   ├── interfaces.py               # LLMProvider Protocol/ABC, 异常定义
│   └── models.py                   # TokenUsage, ProcessResult[T]
│
├── shared/                         # 共享内核（Shared Kernel）
│   ├── config/                     # Pydantic Settings
│   ├── utils/                      # 通用工具（batch, logger, progress, path, model_codes）
│   ├── cli/                        # CLI 提示工具
│   └── infrastructure/             # 业务无关的基础设施
│       ├── llm/                    # OpenAI/Anthropic Provider（通用）
│       ├── storage/                # CSV/TermList Repository
│       └── logging/                # 日志
│
├── reanimator/                     # Reanimator 子域（Bounded Context）
│   ├── domain/                     # 领域层
│   │   ├── models.py               # TermInput, LLMResponse, TermOutput
│   │   └── services.py             # apply_business_rules, get_chinese_tag, generate_memo_id
│   ├── application/                # 应用层
│   │   ├── ports.py                # LLMPort, TermListPort（端口接口）
│   │   └── use_cases.py            # ProcessTermsUseCase（用例）
│   ├── infrastructure/             # 基础设施层
│   │   ├── llm_adapter.py          # ReanimatorLLMAdapter（注入 prompts/schemas）
│   │   ├── prompts.py              # REANIMATER_SYSTEM_PROMPT
│   │   ├── schemas.py              # TERM_RESULT_SCHEMA
│   │   ├── csv_adapter.py          # CSVTermAdapter
│   │   └── term_list_adapter.py    # TermListAdapter
│   └── cli/main.py                 # Reanimator CLI
│
├── lithoformer/                    # Lithoformer 子域（Bounded Context）
│   ├── domain/                     # 领域层
│   │   ├── models.py               # QuizItem, QuizOptions
│   │   └── services.py             # split_markdown, infer_titles, is_quiz_item_valid
│   ├── application/                # 应用层
│   │   ├── ports.py                # LLMPort（端口接口）
│   │   └── use_cases.py            # ParseQuizUseCase（用例）
│   ├── infrastructure/             # 基础设施层
│   │   ├── llm_adapter.py          # LithoformerLLMAdapter（注入 prompts/schemas）
│   │   ├── prompts.py              # LITHOFORMER_SYSTEM_PROMPT
│   │   ├── schemas.py              # QUIZ_SCHEMA
│   │   ├── file_adapter.py         # FileAdapter
│   │   ├── formatter_adapter.py    # FormatterAdapter
│   │   └── formatters/             # QuizFormatter（依赖领域模型）
│   └── cli/main.py                 # Lithoformer CLI
│
└── api.py                          # 编程 API（reanimate(), lithoform()）
```

### 核心设计原则

1. **Bounded Contexts（限界上下文）**
   - Reanimator 和 Lithoformer 作为独立子域
   - 每个子域管理自己的 Domain、Application、Infrastructure
   - Prompts/Schemas 在各自子域的 Infrastructure 层

2. **Ports & Adapters（端口适配器）**
   - Application 层定义端口接口（Protocol）
   - Infrastructure 层实现适配器
   - Adapter 注入 Prompts/Schemas 到通用 Provider

3. **Dependency Inversion（依赖倒置）**
   - Domain 层不依赖任何层
   - Application 层依赖 Domain
   - Infrastructure 层实现 Application 的端口
   - CLI/API 层依赖所有层

4. **Shared Kernel（共享内核）**
   - 只包含业务无关的基础设施
   - TokenUsage, ProcessResult - 通用数据模型
   - OpenAI/Anthropic Provider - 通用 LLM 提供商（无业务逻辑）
   - Config, Utils - 通用基础设施

---

## Reanimator Pipeline 处理流程

**入口**: `src/memosyne/reanimator/cli/main.py`

**分层调用流程**：
1. **CLI** → 创建所有依赖（Provider, Adapters, Use Case）
2. **Use Case** (`ProcessTermsUseCase`) → 编排业务流程
3. **Adapter** (`ReanimatorLLMAdapter`) → 注入 prompts/schemas，调用 Provider
4. **Provider** (`OpenAIProvider/AnthropicProvider`) → 调用 LLM API
5. **Domain Services** → 应用业务规则（词组标记、缩写处理等）
6. **Domain Models** → 数据验证（Pydantic）

**关键文件**：
- `reanimator/cli/main.py` - CLI 入口，依赖注入
- `reanimator/application/use_cases.py` - `ProcessTermsUseCase`，业务流程编排
- `reanimator/application/ports.py` - `LLMPort`, `TermListPort`，端口接口
- `reanimator/infrastructure/llm_adapter.py` - `ReanimatorLLMAdapter`，注入 prompts/schemas
- `reanimator/infrastructure/prompts.py` - `REANIMATER_SYSTEM_PROMPT`，业务逻辑
- `reanimator/infrastructure/schemas.py` - `TERM_RESULT_SCHEMA`，JSON Schema
- `reanimator/domain/services.py` - 业务规则函数
- `reanimator/domain/models.py` - `TermInput`, `LLMResponse`, `TermOutput`

**输出字段**: WMpair, MemoID, Word, ZhDef, IPA, POS, Tag, Rarity, EnDef, Example, PPfix, PPmeans, BatchID, BatchNote

---

## Lithoformer 架构

**入口**: `src/memosyne/lithoformer/cli/main.py`

**分层调用流程**：
1. **CLI** → 创建所有依赖（Provider, Adapters, Use Case）
2. **Use Case** (`ParseQuizUseCase`) → 逐题解析，编排业务流程
3. **Adapter** (`LithoformerLLMAdapter`) → 注入 prompts/schemas，调用 Provider
4. **Provider** (`OpenAIProvider/AnthropicProvider`) → 调用 LLM API
5. **Domain Services** → split_markdown, infer_titles, is_quiz_item_valid
6. **Formatter** → 格式化输出（依赖领域模型 QuizItem）

**关键文件**：
- `lithoformer/cli/main.py` - CLI 入口，依赖注入
- `lithoformer/application/use_cases.py` - `ParseQuizUseCase`，业务流程编排
- `lithoformer/application/ports.py` - `LLMPort`，端口接口
- `lithoformer/infrastructure/llm_adapter.py` - `LithoformerLLMAdapter`，注入 prompts/schemas
- `lithoformer/infrastructure/prompts.py` - `LITHOFORMER_SYSTEM_PROMPT`，业务逻辑
- `lithoformer/infrastructure/schemas.py` - `QUIZ_SCHEMA`，JSON Schema
- `lithoformer/infrastructure/formatters/quiz_formatter.py` - `QuizFormatter`，格式化输出
- `lithoformer/domain/services.py` - 业务规则函数
- `lithoformer/domain/models.py` - `QuizItem`, `QuizOptions`

**输入**: `data/input/lithoformer/*.md` - Markdown 格式测验文件
**输出**: `data/output/lithoformer/ShouldBe.txt` - 标准化测验文本

---

## 数据目录结构

```
data/
├── input/
│   ├── reanimator/    # Reanimator 输入 CSV（Word, ZhDef）
│   └── lithoformer/   # Lithoformer 输入 Markdown 测验
└── output/
    ├── reanimator/    # Reanimator 输出 CSV
    └── lithoformer/   # Lithoformer 输出 TXT

db/
├── term_list_v1.csv   # 术语表（英文→两字中文）
└── reanimator_db/     # Reanimator 数据库文件
```

---

## 关键设计模式

### 1. 依赖注入

**原则**：所有组件通过构造函数注入依赖，避免全局状态。

**示例**：
```python
# CLI 层：创建所有依赖并注入
llm_adapter = ReanimatorLLMAdapter.from_provider(llm_provider)
term_list_adapter = TermListAdapter.from_settings(settings)

use_case = ProcessTermsUseCase(
    llm=llm_adapter,
    term_list=term_list_adapter,
    start_memo_index=2700,
    batch_id="251007A015"
)

result = use_case.execute(terms, show_progress=True)
```

### 2. 端口适配器模式

**原则**：Application 层定义端口接口，Infrastructure 层实现适配器。

**示例**：
```python
# Application 层：定义端口接口
class LLMPort(Protocol):
    def process_term(self, word: str, zh_def: str) -> tuple[dict, dict]:
        ...

# Infrastructure 层：实现适配器
class ReanimatorLLMAdapter:
    def process_term(self, word: str, zh_def: str) -> tuple[dict, dict]:
        # 注入 Reanimator 专用的 prompts/schemas
        system_prompt = REANIMATER_SYSTEM_PROMPT
        user_prompt = REANIMATER_USER_TEMPLATE.format(word=word, zh_def=zh_def)

        return self.provider.complete_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            schema=TERM_RESULT_SCHEMA["schema"],
            schema_name="TermResult"
        )
```

### 3. Pydantic 数据验证

**原则**：所有数据模型使用 Pydantic，自动验证。

**示例**：
```python
class TermInput(BaseModel):
    word: str = Field(..., min_length=1)
    zh_def: str = Field(..., min_length=1)

    @field_validator("word", "zh_def")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("字段不能为空")
        return v.strip()
```

### 4. 配置管理

**原则**：使用 Pydantic Settings 自动加载和验证配置。

**示例**：
```python
from memosyne.shared.config import get_settings

settings = get_settings()  # 自动从 .env 加载
# 如果 API Key 缺失或无效，会抛出 ValidationError
```

### 5. BatchID 生成

使用独立的 `BatchIDGenerator` 类：
- 格式：`YYMMDD + RunLetter + NNN`
- `YYMMDD`: 纽约时区当日日期
- `RunLetter`: 当日批次字母（A-Z）
- `NNN`: 本批词条数（3 位零填充）
- 示例：`251007A015` = 2025-10-07 的首批（A），包含 15 个词条

### 6. 仓储模式

数据访问通过 Repository 层隔离：
- `CSVRepository` - CSV 读写
- `TermListRepository` - 术语表管理

### 7. 统一日志系统

使用标准 `logging` 模块，提供灵活的日志配置：
```python
from memosyne.shared.utils.logger import setup_logger

logger = setup_logger(
    name="memosyne",
    level="INFO",         # DEBUG, INFO, WARNING, ERROR, CRITICAL
    log_file="logs/app.log",  # 可选的日志文件
    format_type="simple"   # simple 或 detailed
)

logger.info("开始处理术语")
logger.warning("Example 与 EnDef 相同")
logger.error("LLM 调用失败", exc_info=True)
```

---

## 开发约定

### 代码规范

- **类型提示**: 所有函数/方法必须有完整的类型提示
- **数据验证**: 使用 Pydantic 模型，而非 dict 或 dataclass
- **依赖注入**: 避免全局状态，通过构造函数传递依赖
- **抽象优于具体**: 依赖抽象接口（Protocol/ABC），而非具体实现
- **进度显示**: 使用 `Progress` 类显示进度条
- **错误处理**: 使用自定义异常（`LLMError`, `ConfigError` 等）
- **编码**: 统一使用 UTF-8

### DDD 规则

- **Shared Kernel 只包含业务无关的基础设施**
  - ✅ 允许：TokenUsage, ProcessResult, LLM Provider（无业务逻辑）
  - ❌ 不允许：Prompts, Schemas（包含业务逻辑）

- **Prompts/Schemas 属于子域**
  - 放在各自子域的 Infrastructure 层
  - Adapter 负责注入到通用 Provider

- **Domain 层不依赖任何层**
  - 只包含纯粹的业务逻辑
  - 不依赖 Infrastructure、Application、CLI

- **依赖方向**
  - CLI/API → Infrastructure → Application → Domain
  - Infrastructure 实现 Application 的端口接口

---

## 文档维护规范

**IMPORTANT**: 每次代码更改后，必须同时更新以下文档：

1. **AGENTS.md**（本文件）——同步通用记忆、常用命令、协作流程
2. **README.md** —— 更新特性、使用示例、安装步骤、架构图、API 示例

**注意**: README.md 现在是项目的唯一主文档，包含完整的架构说明、API 使用指南和设计决策。

### 更新检查清单

修改代码后，检查：
- [ ] 是否有新的依赖？→ 更新 `requirements.txt`
- [ ] 是否有新的 CLI 命令？→ 更新 README.md 和 AGENTS.md 的“快速开始”部分
- [ ] 是否修改了架构？→ 更新 README.md 中的"架构设计"章节和 Mermaid 图表
- [ ] 是否添加了新功能？→ 更新 README.md 的特性列表
- [ ] 是否修改了 API？→ 更新 README.md 的"API 使用指南"章节

---

## Git 工作流程

详见 `GIT_GUIDE.md`。关键点：

- **提交前**: 确保代码能运行，测试通过
- **提交信息**: 使用清晰的描述（如 "添加批量处理 API"）
- **频繁提交**: 小步快走，每完成一个小功能就提交
- **同步文档**: 代码和文档同时提交
- **及时推送**: 每天至少 Push 一次

---

## 版本发布流程

1. **更新版本号**: 修改 `src/memosyne/__init__.py` 中的 `__version__`
2. **更新 CHANGELOG**: 在 `README.md` 中添加版本变更记录
3. **创建 Git 标签**: `git tag -a v0.x.x -m "Release v0.x.x"`
4. **推送标签**: `git push origin v0.x.x`
5. **GitHub Release**: 在 GitHub 上创建正式 Release

---

## 项目文档结构

```
Memosyne/
├── README.md    # 项目主文档（架构、API、设计决策）
├── AGENTS.md    # AI 协作记忆（本文件）
└── GIT_GUIDE.md # Git 项目管理指南
```

**说明**：除了本文件和 `GIT_GUIDE.md` 外，其余架构、CLI、API 文档均已整合至 README.md。

---

## Lithoformer I/O Notes

- 输入格式：题目使用 ```Question``` / ```Answer``` 成对代码块，兼容旧的 ```Gezhi``` 格式。
- 标题推断：优先读取 Markdown 中的 `#` 标题；若缺失，可在 `src/memosyne/lithoformer/domain/services.py` 的 `TITLE_OVERRIDES` 中添加映射。
- 默认字典目前包含 `"23": ("Profiles in Psychopathology", "Anxiety Disorders")`。

## 常见任务

### 添加新的 LLM Provider

1. 在 `shared/infrastructure/llm/` 创建新 Provider 类
2. 继承 `BaseLLMProvider`
3. 实现 `complete_structured()` 方法
4. 在 `shared/infrastructure/llm/__init__.py` 导出

**无需修改子域代码**！

### 添加新的子域（Bounded Context）

1. 创建新子域目录：`src/memosyne/new_subdomain/`
2. 创建分层结构：
   - `domain/` - 领域模型和服务
   - `application/` - 用例和端口接口
   - `infrastructure/` - 适配器、Prompts、Schemas
   - `cli/` - CLI 入口
3. 在 `api.py` 添加新的 API 函数

**无需修改其他子域**！

### 修改业务逻辑

1. **修改领域模型** → `reanimator/domain/models.py` 或 `lithoformer/domain/models.py`
2. **修改业务规则** → `reanimator/domain/services.py` 或 `lithoformer/domain/services.py`
3. **修改 LLM Prompts** → `reanimator/infrastructure/prompts.py` 或 `lithoformer/infrastructure/prompts.py`
4. **修改 JSON Schema** → `reanimator/infrastructure/schemas.py` 或 `lithoformer/infrastructure/schemas.py`

**无需修改 Shared Kernel**！

---

## 故障排除

### 问题：ImportError

**原因**：直接运行 CLI 文件（如 `python src/memosyne/reanimator/cli/main.py`）

**解决**：使用模块执行方式：
```bash
python -m memosyne.reanimator.cli.main
# 或使用便捷脚本
./run_reanimate.sh
```

### 问题：ValidationError: Field required

**原因**：`.env` 文件配置错误或 API Key 为空

**解决**：
1. 检查 `.env` 文件是否存在
2. 确保 `OPENAI_API_KEY` 已正确配置
3. 确保 API Key 长度 ≥ 20 字符

### 问题：LLMError: OpenAI API 错误

**原因**：API 调用失败（额度不足、网络问题等）

**解决**：
1. 检查 API Key 是否有效
2. 检查账户额度
3. 检查网络连接

---

**最后更新**: 2025-10-14
**文档版本**: v0.9.1a
