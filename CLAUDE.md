# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Memosyne 是一个基于 LLM（OpenAI/Anthropic）的术语处理和测验解析工具。

**版本信息**:
- **v2.0** (当前) - 重构版本，采用现代化架构，位于 `src/memosyne/`

主要功能：
1. **MMS Pipeline** - 术语记忆处理管道，用于生成结构化术语卡片
2. **ExParser** - 测验解析器，将 Markdown 格式的测验转换为标准化格式

## 常用命令

### 运行项目

```bash
# 方式 1: 交互式 CLI
python src/memosyne/cli/mms.py       # MMS - 术语处理
python src/memosyne/cli/exparser.py  # ExParser - Quiz 解析

# 方式 2: Python 模块
python -m memosyne.cli.mms
python -m memosyne.cli.exparser

# 方式 3: 编程 API
python -c "from memosyne import process_terms; help(process_terms)"
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

项目需要 `.env` 文件配置 API 密钥：
```bash
OPENAI_API_KEY=your-key-here
ANTHROPIC_API_KEY=your-key-here
MODEL_NAME=o4mini  # 可选：默认模型名
```

**注意**: `.env` 文件已在 `.gitignore` 中，绝不能提交到版本控制。

## 核心架构 (v2.0)

### 分层架构

```
src/memosyne/
├── config/          # 配置层：Pydantic Settings
├── core/            # 核心层：抽象接口、异常定义
├── models/          # 模型层：Pydantic 数据模型
├── providers/       # 提供商层：LLM Provider 实现
├── repositories/    # 仓储层：数据访问（CSV、术语表）
├── services/        # 服务层：业务逻辑
├── utils/           # 工具层：路径、批次ID生成等
└── cli/             # 界面层：命令行接口
```

### MMS Pipeline 处理流程

**入口**: `src/memosyne/cli/mms.py`

1. **配置加载** (`config/settings.py`):
   - `Settings` - Pydantic Settings 自动验证 API Key
   - `get_settings()` - 单例模式获取配置

2. **数据读取** (`repositories/csv_repository.py`):
   - `CSVTermRepository.read_input()` - 读取输入 CSV
   - 自动识别分隔符、BOM、多语言列名
   - 返回 `TermInput` Pydantic 模型列表

3. **术语表加载** (`repositories/term_list_repository.py`):
   - `TermListRepo.load()` - 加载术语表
   - `get_chinese_tag()` - 英文标签 → 中文映射

4. **LLM 处理** (`services/term_processor.py`):
   - `TermProcessor` - 依赖注入 LLM Provider
   - 调用 `process()` 批量处理术语
   - 使用 tqdm 显示进度条

5. **LLM Provider** (`providers/`):
   - `OpenAIProvider` - OpenAI 实现
   - `AnthropicProvider` - Anthropic 实现
   - 均继承 `BaseLLMProvider` 抽象基类
   - 接口一致，可互换

6. **数据写出** (`repositories/csv_repository.py`):
   - `CSVTermRepository.write_output()` - 写出到 `data/output/memo/`

**输出字段**: WMpair, MemoID, Word, ZhDef, IPA, POS, Tag, Rarity, EnDef, Example, PPfix, PPmeans, BatchID, BatchNote

### ExParser 架构 (v2.0)

**入口**: `src/memosyne/cli/exparser.py`

处理流程：
1. **Quiz 解析** (`services/quiz_parser.py`):
   - `QuizParser` - 使用依赖注入的 LLM Provider
   - 支持 OpenAI 和 Anthropic
   - 使用 JSON Schema 确保结构化输出
   - 返回 `QuizItem` Pydantic 模型列表

2. **格式化输出** (`utils/quiz_formatter.py`):
   - `QuizFormatter.format()` - 将 QuizItem 转换为 ShouldBe 格式
   - 支持题型：MCQ（选择题）、CLOZE（填空题）、ORDER（排序题）
   - 自动处理图片占位符（`§Pic.N§`）
   - 清理题干垃圾行、规范化选项文本

3. **编程 API** (`api.py`):
   - `parse_quiz(input_md, model, provider, ...)` - 直接调用
   - 返回包含成功状态、输出路径、题目数量的 dict

**输入**: `data/input/parser/*.md` - Markdown 格式测验文件
**输出**: `data/output/parser/ShouldBe.txt` - 标准化测验文本

## 数据目录结构

```
data/
├── input/
│   ├── memo/      # MMS Pipeline 输入 CSV（Word, ZhDef）
│   └── parser/    # ExParser 输入 Markdown 测验
├── output/
│   ├── memo/      # MMS Pipeline 输出 CSV
│   ├── parser/    # ExParser 输出 TXT
│   └── archived/  # 历史归档文件
db/
├── term_list_v1.csv  # 术语表（英文→两字中文）
└── mmsdb/            # 其他数据库文件
```

## 关键设计模式 (v2.0)

### 1. 依赖注入
所有组件通过构造函数注入依赖，而非全局状态：
```python
processor = TermProcessor(
    llm_provider=llm_provider,        # 可替换为任何实现
    term_list_mapping=repo.mapping,    # 可注入测试数据
    start_memo_index=2700,
    batch_id="251007A015"
)
```

### 2. 抽象接口 (Protocol/ABC)
LLM Provider 使用 Protocol 定义接口：
```python
class LLMProvider(Protocol):
    def complete_prompt(self, word: str, zh_def: str) -> dict: ...
```
任何实现了此方法的类都可作为 Provider，无需显式继承。

### 3. Pydantic 数据验证
所有数据模型使用 Pydantic，自动验证：
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
使用 Pydantic Settings 自动加载和验证配置：
```python
from memosyne.config import get_settings

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
- `CSVTermRepository` - CSV 读写
- `TermListRepo` - 术语表管理

## 开发约定 (v2.0)

- **类型提示**: 所有函数/方法必须有完整的类型提示
- **数据验证**: 使用 Pydantic 模型，而非 dict 或 dataclass
- **依赖注入**: 避免全局状态，通过构造函数传递依赖
- **抽象优于具体**: 依赖抽象接口（Protocol/ABC），而非具体实现
- **进度显示**: 使用 tqdm 显示进度条
- **错误处理**: 使用自定义异常（`LLMError`, `ConfigError` 等）
- **编码**: 统一使用 UTF-8

## 文档维护规范

**IMPORTANT**: 每次代码更改后，必须同时更新以下文档：

1. **CLAUDE.md** (本文件) - 更新命令、架构、流程说明
2. **README.md** - 更新功能列表、使用示例、安装步骤
3. **ARCHITECTURE.md** - 更新架构图、设计决策、UML 图

### 更新检查清单

修改代码后，检查：
- [ ] 是否有新的依赖？→ 更新 `requirements.txt`
- [ ] 是否有新的 CLI 命令？→ 更新所有文档的"快速开始"部分
- [ ] 是否修改了架构？→ 更新 `ARCHITECTURE.md` 中的图表
- [ ] 是否添加了新功能？→ 更新 `README.md` 的特性列表
- [ ] 是否修改了 API？→ 更新 `API_GUIDE.md`

## Git 工作流程

详见 `GIT_GUIDE.md`。关键点：

- **提交前**: 确保代码能运行，测试通过
- **提交信息**: 使用清晰的描述（如 "添加批量处理 API"）
- **频繁提交**: 小步快走，每完成一个小功能就提交
- **同步文档**: 代码和文档同时提交
- **及时推送**: 每天至少 Push 一次

## 版本发布流程

1. **更新版本号**: 修改 `src/memosyne/__init__.py` 中的 `__version__`
2. **更新 CHANGELOG**: 在 `README.md` 中添加版本变更记录
3. **创建 Git 标签**: `git tag -a v2.x.x -m "Release v2.x.x"`
4. **推送标签**: `git push origin v2.x.x`
5. **GitHub Release**: 在 GitHub 上创建正式 Release

## ExParser 架构 (v2.0 已重构)

**入口**: `src/memosyne/cli/exparser.py`

处理流程：
1. **Quiz 解析** (`services/quiz_parser.py`):
   - `QuizParser` - 使用 LLM Provider 解析 Markdown
   - 支持 OpenAI 和 Anthropic
   - 返回 `QuizItem` Pydantic 模型列表

2. **格式化输出** (`utils/quiz_formatter.py`):
   - `QuizFormatter` - 将 QuizItem 转换为 ShouldBe 格式
   - 支持题型：MCQ（选择题）、CLOZE（填空题）、ORDER（排序题）
   - 自动清理题干、规范化选项

3. **编程 API** (`api.py`):
   - `parse_quiz()` - 可在代码中直接调用
   - 返回详细结果 dict

**输入**: `data/input/parser/*.md` - Markdown 格式测验文件
**输出**: `data/output/parser/ShouldBe.txt` - 标准化测验文本

## 项目文档结构

```
Memosyne/
├── README.md              # 项目主文档
├── CLAUDE.md              # Claude Code 工作指南 (本文件)
├── ARCHITECTURE.md        # 架构设计文档（含所有图表）
├── API_GUIDE.md           # API 使用指南
├── GIT_GUIDE.md           # Git 项目管理指南
└── refactor_examples/     # 重构示例代码
```