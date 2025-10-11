# Memosyne 架构文档

**版本**: v0.7.1
**日期**: 2025-10-11

本文档详细描述 Memosyne 项目的架构设计、设计决策和各种架构图表。

---

## 目录

- [架构概览](#架构概览)
- [分层架构图](#分层架构图)
- [系统架构图](#系统架构图)
- [UML 类图](#uml-类图)
- [时序图](#时序图)
- [数据流图](#数据流图)
- [设计决策](#设计决策)

---

## 架构概览

Memosyne 采用经典的**分层架构**（Layered Architecture）和 **SOLID 原则**，确保代码的可维护性、可测试性和可扩展性。

### 核心设计原则

1. **单一职责原则** (SRP) - 每个模块只负责一个功能
2. **开放封闭原则** (OCP) - 对扩展开放，对修改封闭
3. **里氏替换原则** (LSP) - 子类可以替换父类
4. **接口隔离原则** (ISP) - 使用细粒度接口
5. **依赖倒置原则** (DIP) - 依赖抽象而非具体实现

### 架构特点

- ✅ **无全局状态** - 所有依赖通过构造函数注入
- ✅ **类型安全** - 使用 Pydantic 进行运行时验证
- ✅ **可测试** - 每个组件都可以独立测试
- ✅ **可扩展** - 轻松添加新的 LLM Provider
- ✅ **模块化配置** - Prompts 和 Schemas 独立管理
- ✅ **Token 追踪** - 完整的 Token 使用量统计

---

## 分层架构图

```mermaid
graph TB
    subgraph "用户接口层 (User Interface Layer)"
        CLI[CLI 工具]
        API[编程 API]
    end

    subgraph "服务层 (Service Layer)"
        Reanimater[Reanimater<br/>术语处理服务]
        Lithoformer[Lithoformer<br/>Quiz 解析服务]
    end

    subgraph "提供商层 (Provider Layer)"
        OpenAI[OpenAIProvider]
        Anthropic[AnthropicProvider]
    end

    subgraph "数据访问层 (Repository Layer)"
        CSVRepo[CSVTermRepository<br/>CSV 读写]
        TermList[TermListRepo<br/>术语表管理]
    end

    subgraph "核心层 (Core Layer)"
        Models[Pydantic 模型<br/>TermInput/Output<br/>QuizItem<br/>TokenUsage/ProcessResult]
        Interfaces[抽象接口<br/>LLMProvider<br/>Protocol/ABC]
        Prompts[Prompts<br/>LLM 提示词]
        Schemas[Schemas<br/>JSON Schema]
    end

    subgraph "配置层 (Config Layer)"
        Settings[Settings<br/>Pydantic Settings]
    end

    CLI --> Reanimater
    CLI --> Lithoformer
    API --> Reanimater
    API --> Lithoformer

    Reanimater --> OpenAI
    Reanimater --> Anthropic
    Reanimater --> CSVRepo
    Reanimater --> TermList

    Lithoformer --> OpenAI
    Lithoformer --> Anthropic

    OpenAI -.implements.-> Interfaces
    Anthropic -.implements.-> Interfaces

    Reanimater --> Models
    Lithoformer --> Models
    CSVRepo --> Models

    OpenAI --> Prompts
    OpenAI --> Schemas
    Anthropic --> Prompts
    Anthropic --> Schemas

    Reanimater --> Settings
    Lithoformer --> Settings
    OpenAI --> Settings
    Anthropic --> Settings

    style CLI fill:#e1f5ff
    style API fill:#e1f5ff
    style Reanimater fill:#fff4e1
    style Lithoformer fill:#fff4e1
    style OpenAI fill:#f0e1ff
    style Anthropic fill:#f0e1ff
    style Settings fill:#e1ffe1
```

---

## 系统架构图

### Reanimater Pipeline 架构

```mermaid
flowchart LR
    User[用户] --> CLI[Reanimater CLI]
    User --> API[reanimate API]

    CLI --> Reanimater
    API --> Reanimater

    Reanimater --> LLM[LLM Provider<br/>OpenAI/Anthropic]
    Reanimater --> CSVRepo[CSV Repository]
    Reanimater --> TermList[Term List Repo]
    Reanimater --> BatchGen[Batch ID Generator]

    CSVRepo --> InputCSV[(输入 CSV<br/>word, zh_def)]
    CSVRepo --> OutputCSV[(输出 CSV<br/>完整记忆卡片)]

    TermList --> TermDB[(术语表<br/>term_list_v1.csv)]

    LLM -.生成.-> LLMResp[LLM Response<br/>IPA, POS, EnDef, etc.]

    LLMResp --> Validation[Pydantic 验证]
    Validation --> BusinessRules[业务规则处理<br/>词组标记/缩写处理]
    BusinessRules --> TermOutput[TermOutput 模型]

    TermOutput --> OutputCSV

    style Reanimater fill:#ffd700
    style LLM fill:#87ceeb
    style Validation fill:#90ee90
```

### Lithoformer Pipeline 架构

```mermaid
flowchart LR
    User[用户] --> CLI[Lithoformer CLI]
    User --> API[lithoform API]

    CLI --> Lithoformer
    API --> Lithoformer

    Lithoformer --> LLM[LLM Provider<br/>OpenAI/Anthropic]
    Lithoformer --> Formatter[Quiz Formatter]

    InputMD[(Markdown<br/>Quiz 文档)] --> Lithoformer

    LLM -.解析.-> QuizResp[Quiz Response<br/>MCQ/CLOZE/ORDER]

    QuizResp --> Validation[Pydantic 验证]
    Validation --> QuizItems[QuizItem 列表]

    QuizItems --> Formatter
    Formatter --> Sanitize[文本清理<br/>垃圾行移除]
    Sanitize --> Format[格式化<br/>ShouldBe 格式]
    Format --> OutputTXT[(输出 TXT<br/>ShouldBe.txt)]

    style Lithoformer fill:#ffd700
    style LLM fill:#87ceeb
    style Formatter fill:#ff6b6b
```

---

## UML 类图

### 核心接口和抽象类

```mermaid
classDiagram
    class LLMProvider {
        <<Protocol>>
        +model: str
        +temperature: float | None
        +complete_prompt(word, zh_def) tuple[dict, TokenUsage]
        +complete_structured(sys, user, schema, name) tuple[dict, TokenUsage]
    }

    class BaseLLMProvider {
        <<Abstract>>
        #model: str
        #temperature: float | None
        +__init__(model, temperature)
        +complete_prompt(word, zh_def)* tuple[dict, TokenUsage]
        +complete_structured(...)* tuple[dict, TokenUsage]
        #_validate_config()* void
    }

    class OpenAIProvider {
        -client: OpenAI
        +__init__(model, api_key, temperature, max_retries)
        +from_settings(settings)$ OpenAIProvider
        +complete_prompt(word, zh_def) tuple[dict, TokenUsage]
        +complete_structured(...) tuple[dict, TokenUsage]
        #_validate_config() void
    }

    class AnthropicProvider {
        -client: Anthropic
        -max_tokens: int
        +__init__(model, api_key, temperature, max_tokens)
        +from_settings(settings)$ AnthropicProvider
        +complete_prompt(word, zh_def) tuple[dict, TokenUsage]
        +complete_structured(...) tuple[dict, TokenUsage]
        #_validate_config() void
    }

    LLMProvider <|.. BaseLLMProvider : implements
    BaseLLMProvider <|-- OpenAIProvider : extends
    BaseLLMProvider <|-- AnthropicProvider : extends
```

### Pydantic 数据模型

```mermaid
classDiagram
    class TermInput {
        +word: str
        +zh_def: str
        +strip_whitespace()$ str
        +validate_word_not_chinese() self
    }

    class LLMResponse {
        +ipa: str
        +pos: Literal
        +rarity: Literal
        +en_def: str
        +example: str
        +pp_fix: str
        +pp_means: str
        +tag_en: str
        +validate_abbr_no_ipa() self
        +validate_en_def_contains_word() self
    }

    class TermOutput {
        +memo_id: str
        +word: str
        +zh_def: str
        +ipa: str
        +pos: str
        +rarity: str
        +en_def: str
        +example: str
        +pp_fix: str
        +pp_means: str
        +tag_en: str
        +tag_cn: str
        +batch_id: str
        +batch_note: str
        +from_input_and_llm()$ TermOutput
        +to_csv_row() list
    }

    class QuizItem {
        +qtype: Literal["MCQ", "CLOZE", "ORDER"]
        +stem: str
        +steps: list~str~
        +options: QuizOptions
        +answer: str
        +cloze_answers: list~str~
    }

    class QuizOptions {
        +A: str
        +B: str
        +C: str
        +D: str
        +E: str
        +F: str
    }

    class TokenUsage {
        +prompt_tokens: int
        +completion_tokens: int
        +total_tokens: int
        +__add__(other) TokenUsage
    }

    class ProcessResult~T~ {
        +items: list~T~
        +success_count: int
        +total_count: int
        +token_usage: TokenUsage
    }

    TermOutput ..> TermInput : uses
    TermOutput ..> LLMResponse : uses
    QuizItem *-- QuizOptions : contains
    ProcessResult *-- TokenUsage : contains
```

### 服务层类图

```mermaid
classDiagram
    class Reanimater {
        -llm: LLMProvider
        -term_mapping: dict
        -start_memo: int
        -batch_id: str
        -batch_note: str
        -logger: Logger
        +__init__(llm_provider, term_list_mapping, start_memo_index, batch_id, batch_note, logger)
        +from_settings(...)$ Reanimater
        +process(terms, show_progress) ProcessResult~TermOutput~
        -_apply_business_rules(word, llm_response) LLMResponse
        -_get_chinese_tag(tag_en) str
        -_generate_memo_id(index) str
    }

    class Lithoformer {
        -llm: LLMProvider
        -logger: Logger
        +__init__(llm_provider, logger)
        +from_settings(...)$ Lithoformer
        +process(markdown_source, show_progress) ProcessResult~QuizItem~
    }

    class QuizFormatter {
        +format(items, title_main, title_sub) str
    }

    Reanimater ..> LLMProvider : uses
    Reanimater ..> TermInput : processes
    Reanimater ..> TermOutput : produces

    Lithoformer ..> LLMProvider : uses
    Lithoformer ..> QuizItem : produces

    QuizFormatter ..> QuizItem : formats
```

---

## 时序图

### Reanimater 处理流程时序图

```mermaid
sequenceDiagram
    actor User
    participant CLI as Reanimater CLI
    participant API as reanimate()
    participant RA as Reanimater
    participant LLM as LLM Provider
    participant CSV as CSVRepository
    participant TL as TermListRepo

    User->>CLI: 启动 CLI
    CLI->>User: 请求输入参数
    User->>CLI: 输入 model, file, index

    CLI->>CSV: 读取输入 CSV
    CSV-->>CLI: list[TermInput]

    CLI->>TL: 加载术语表
    TL-->>CLI: term_mapping dict

    CLI->>RA: 创建 Reanimater

    loop 每个术语
        RA->>LLM: complete_prompt(word, zh_def)
        LLM->>LLM: 调用 API (OpenAI/Anthropic)
        LLM-->>RA: tuple[dict, TokenUsage]

        RA->>RA: 验证 (Pydantic)
        RA->>RA: 应用业务规则
        RA->>RA: 生成 Memo ID
        RA->>RA: 映射中文标签
        RA->>RA: 累加 Token

        RA->>RA: 创建 TermOutput
    end

    RA-->>CLI: ProcessResult[TermOutput]

    CLI->>CSV: 写出结果 CSV
    CSV-->>CLI: 成功

    CLI-->>User: 显示成功信息
```

### Lithoformer 解析流程时序图

```mermaid
sequenceDiagram
    actor User
    participant CLI as Lithoformer CLI
    participant LF as Lithoformer
    participant LLM as LLM Provider
    participant QF as QuizFormatter
    participant File as File System

    User->>CLI: 启动 CLI
    CLI->>User: 请求输入参数
    User->>CLI: 输入 model, input_md

    CLI->>File: 读取 Markdown 文件
    File-->>CLI: markdown_text

    CLI->>LF: 创建 Lithoformer
    CLI->>LF: process(markdown_text, show_progress)

    LF->>LLM: 发送 Markdown + Prompt (structured)
    LLM->>LLM: 调用 API (JSON Schema)
    LLM-->>LF: tuple[dict, TokenUsage]

    LF->>LF: 验证 (Pydantic)
    LF->>LF: 创建 QuizItem 列表
    LF-->>CLI: ProcessResult[QuizItem]

    CLI->>QF: 创建 QuizFormatter
    CLI->>QF: format(items, title_main, title_sub)

    loop 每个 QuizItem
        QF->>QF: 清理题干
        QF->>QF: 规范化选项
        alt MCQ
            QF->>QF: 渲染多选题
        else CLOZE
            QF->>QF: 替换填空答案
        else ORDER
            QF->>QF: 渲染排序题
        end
    end

    QF-->>CLI: formatted_text

    CLI->>File: 写出 TXT 文件
    File-->>CLI: 成功

    CLI-->>User: 显示成功信息
```

### API 调用时序图

```mermaid
sequenceDiagram
    actor Developer
    participant App as 第三方应用
    participant API as memosyne.api
    participant RA as Reanimater
    participant Settings as Settings
    participant LLM as LLMProvider

    Developer->>App: import memosyne.api

    App->>API: reanimate(input_csv, start_index, model)

    API->>Settings: get_settings()
    Settings-->>API: settings instance

    API->>API: 解析输入路径
    API->>API: 读取输入 CSV
    API->>API: 加载术语表
    API->>API: 生成批次 ID

    alt provider == "openai"
        API->>LLM: 创建 OpenAIProvider
    else provider == "anthropic"
        API->>LLM: 创建 AnthropicProvider
    end

    API->>RA: 创建 Reanimater
    API->>RA: process(terms, show_progress)

    RA->>LLM: complete_prompt() (多次)
    LLM-->>RA: tuple[dict, TokenUsage] (多次)

    RA-->>API: ProcessResult[TermOutput]

    API->>API: 写出 CSV

    API-->>App: result dict {success, output_path, ...}

    App-->>Developer: 返回结果
```

---

## 数据流图

### Reanimater 数据流

```mermaid
flowchart TD
    Start([开始]) --> InputCSV[/输入 CSV<br/>word, zh_def/]

    InputCSV --> ReadCSV{CSV 读取}
    ReadCSV --> TermInputs[TermInput 列表]

    TermInputs --> LoadTermList[加载术语表]
    LoadTermList --> TermMapping[term_mapping dict]

    TermInputs --> Loop{遍历每个术语}

    Loop --> LLMCall[LLM API 调用]
    LLMCall --> LLMJson[JSON 响应]

    LLMJson --> PydanticVal{Pydantic 验证}
    PydanticVal -->|失败| Error1[ValidationError]
    PydanticVal -->|成功| LLMResp[LLMResponse 模型]

    LLMResp --> BizRules[应用业务规则<br/>词组标记/缩写处理]
    BizRules --> GenMemoID[生成 Memo ID]
    GenMemoID --> MapTag[映射中文标签]

    MapTag --> TermOutput[TermOutput 模型]
    TermOutput --> Collect[收集结果]

    Collect --> More{还有术语?}
    More -->|是| Loop
    More -->|否| WriteCSV[/写出 CSV/]

    WriteCSV --> OutputCSV[/输出 CSV<br/>完整记忆卡片/]
    OutputCSV --> End([结束])

    Error1 --> End

    style InputCSV fill:#e1f5ff
    style OutputCSV fill:#e1ffe1
    style LLMCall fill:#ffe1e1
    style PydanticVal fill:#fff4e1
```

### Lithoformer 数据流

```mermaid
flowchart TD
    Start([开始]) --> InputMD[/输入 Markdown<br/>Quiz 文档/]

    InputMD --> ReadMD{读取文件}
    ReadMD --> MDText[markdown_text]

    MDText --> LLMCall[LLM API 调用<br/>JSON Schema]
    LLMCall --> LLMJson[JSON 响应]

    LLMJson --> PydanticVal{Pydantic 验证}
    PydanticVal -->|失败| Error1[ValidationError]
    PydanticVal -->|成功| QuizItems[QuizItem 列表]

    QuizItems --> Formatter[QuizFormatter]

    Formatter --> LoopItems{遍历每个题目}

    LoopItems --> Sanitize[清理题干<br/>移除垃圾行]
    Sanitize --> CheckType{题型}

    CheckType -->|MCQ| FormatMCQ[格式化多选题]
    CheckType -->|CLOZE| FormatCloze[替换填空答案]
    CheckType -->|ORDER| FormatOrder[格式化排序题]

    FormatMCQ --> Collect[收集格式化文本]
    FormatCloze --> Collect
    FormatOrder --> Collect

    Collect --> More{还有题目?}
    More -->|是| LoopItems
    More -->|否| JoinBlocks[拼接所有题目]

    JoinBlocks --> OutputTXT[/输出 TXT<br/>ShouldBe.txt/]
    OutputTXT --> End([结束])

    Error1 --> End

    style InputMD fill:#e1f5ff
    style OutputTXT fill:#e1ffe1
    style LLMCall fill:#ffe1e1
    style Formatter fill:#fff4e1
```

---

## 设计决策

### 1. 为什么使用 Pydantic？

**问题**：如何确保数据的类型安全和运行时验证？

**决策**：使用 Pydantic 2.x

**理由**：
- ✅ 运行时类型验证
- ✅ 自动数据转换（如字符串 → 枚举）
- ✅ 清晰的错误信息
- ✅ IDE 类型提示支持
- ✅ JSON Schema 生成（用于 LLM）

### 2. 为什么使用 Protocol 和 ABC？

**问题**：如何定义 LLM Provider 接口？

**决策**：同时使用 Protocol（duck typing）和 ABC（显式继承）

**理由**：
- Protocol：支持鸭子类型，无需显式继承
- ABC：提供模板方法模式和共享代码
- 两者结合：既灵活又有代码复用

### 3. 为什么使用依赖注入？

**问题**：如何避免全局状态和硬编码依赖？

**决策**：通过构造函数注入所有依赖

**理由**：
- ✅ 可测试性：轻松 mock 依赖
- ✅ 灵活性：运行时选择不同实现
- ✅ 清晰性：依赖关系显式声明

示例：

```python
# ❌ 不好：全局状态
llm = OpenAI()  # 全局变量

def reanimate(word):
    return llm.call(word)  # 隐式依赖

# ✅ 好：依赖注入
class Reanimater:
    def __init__(self, llm: LLMProvider):
        self.llm = llm  # 显式依赖

    def reanimate(self, word):
        return self.llm.call(word)
```

### 4. 为什么分离 Repository 和 Service？

**问题**：如何组织数据访问和业务逻辑？

**决策**：Repository 负责 I/O，Service 负责业务逻辑

**理由**：
- ✅ 单一职责：每层只负责一件事
- ✅ 可测试：可以 mock Repository 测试 Service
- ✅ 可替换：轻松替换数据源（CSV → DB）

### 5. 为什么使用 Pydantic Settings？

**问题**：如何管理配置？

**决策**：使用 pydantic-settings 从 .env 加载配置

**理由**：
- ✅ 类型验证：配置项类型安全
- ✅ 环境变量支持：12-factor app 兼容
- ✅ 默认值管理：集中在一处
- ✅ IDE 提示：完整的类型提示

### 6. 为什么提供 CLI 和 API 两种接口？

**问题**：如何满足不同用户需求？

**决策**：同时提供交互式 CLI 和编程 API

**理由**：
- CLI：适合手动操作、测试、快速验证
- API：适合自动化、集成、批量处理
- 两者共享底层逻辑，避免重复

---

## 扩展性

### 添加新的 LLM Provider

步骤：

1. 创建新文件 `providers/new_provider.py`
2. 继承 `BaseLLMProvider`
3. 实现 `complete_prompt()` 方法
4. 在 `providers/__init__.py` 导出

无需修改其他代码！

### 添加新的数据源

步骤：

1. 创建新 Repository 类
2. 实现读写方法
3. 在 Service 中注入新 Repository

无需修改 Service 业务逻辑！

### 添加新的输出格式

步骤：

1. 创建新 Formatter 类
2. 实现 `format()` 方法
3. 在 CLI/API 中调用

无需修改解析逻辑！

---

## 性能优化

### 当前瓶颈

1. **LLM API 调用** - 网络延迟占主要时间
2. **顺序处理** - 目前是同步逐个处理

### 未来优化方向

1. **并发处理** - 使用 `asyncio` 并发调用 LLM API
2. **批量请求** - 合并多个术语到一次 API 调用
3. **缓存** - 缓存相同术语的结果
4. **重试策略** - 智能重试失败的请求

---

## 总结

Memosyne v2.0 采用现代化的 Python 架构设计，遵循 SOLID 原则和最佳实践，实现了：

✅ **高内聚低耦合** - 每层职责清晰
✅ **易于测试** - 依赖注入，可 mock
✅ **易于扩展** - 新增 Provider 无需修改现有代码
✅ **类型安全** - Pydantic 运行时验证
✅ **文档完善** - 代码即文档

这是一个**生产级别**的架构，可以支撑长期维护和功能扩展。

---

**文档版本**: 1.1
**作者**: Memosyne Team
**最后更新**: 2025-10-11
