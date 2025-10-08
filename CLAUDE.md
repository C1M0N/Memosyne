# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Memosyne 是一个基于 LLM（OpenAI/Anthropic）的术语处理和测验解析工具。

**版本信息**:
- **v2.0** (推荐) - 重构版本，采用现代化架构，位于 `src/memosyne/`
- **v1.0** (遗留) - 原始版本，位于 `src/mms_pipeline/` 和 `src/exparser/`

主要功能：
1. **MMS Pipeline** - 术语记忆处理管道，用于生成结构化术语卡片
2. **ExParser** - 测验解析器，将 Markdown 格式的测验转换为标准化格式

## 常用命令

### 运行项目 (v2.0 - 推荐)

```bash
# MMS Pipeline - 术语处理
python -m memosyne.cli.mms

# ExParser - 测验解析 (即将推出)
# python -m memosyne.cli.parser
```

### 运行项目 (v1.0 - 遗留)

```bash
# 1. MMS Pipeline - 术语处理
python src/mms_pipeline/main.py

# 2. ExParser - 测验解析
python src/exparser/main.py
```

### 依赖管理

```bash
# v2.0 依赖（推荐）
pip install -r requirements-v2.txt

# v1.0 依赖
pip install -r requirements.txt

# 创建虚拟环境（如需要）
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
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

### ExParser 架构

**入口**: `src/exparser/main.py`

处理流程：
1. **Markdown 解析** (`openai_quiz_helper.py`):
   - `OpenAIQuizHelper` - 使用 LLM 解析 Markdown 测验文本为结构化 JSON

2. **格式化输出** (`formatter.py`):
   - `format_items_to_shouldbe()` - 将解析结果转换为 ShouldBe 格式
   - 支持题型：MCQ（选择题）、CLOZE（填空题）、ORDER（排序题）
   - 处理图片占位符（`§Pic.N§`）、选项标准化、题干清理

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

## 从 v1.0 迁移到 v2.0

详见 `MIGRATION_GUIDE.md`。简要步骤：

1. 安装新依赖：`pip install -r requirements-v2.txt`
2. 运行新版本：`python -m memosyne.cli.mms`
3. 无需修改 `.env` 文件或数据格式

v1.0 版本仍可继续使用，两者可并行运行。
