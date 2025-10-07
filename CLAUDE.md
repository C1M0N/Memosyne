# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Memosyne 是一个基于 LLM（OpenAI/Anthropic）的术语处理和测验解析工具，包含两个主要管道：
1. **MMS Pipeline** (`src/mms_pipeline/`) - 术语记忆处理管道，用于生成结构化术语卡片
2. **ExParser** (`src/exparser/`) - 测验解析器，将 Markdown 格式的测验转换为标准化格式

## 常用命令

### 运行项目

```bash
# 1. MMS Pipeline - 术语处理
python src/mms_pipeline/main.py

# 2. ExParser - 测验解析
python src/exparser/main.py
```

### 依赖管理

```bash
# 安装依赖
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

## 核心架构

### MMS Pipeline 架构

**入口**: `src/mms_pipeline/main.py`

处理流程：
1. **数据读取** (`term_data.py`):
   - `read_input_csv()` - 宽松解析 CSV（自动识别分隔符、BOM、多语言列名）
   - `TermList` - 加载术语表映射（英文→两字中文）

2. **LLM 处理** (`term_processor.py`):
   - `TermProcessor` - 批量处理术语，调用 LLM 生成结构化字段
   - 使用 tqdm 显示进度条

3. **LLM 引擎** (可切换):
   - `openai_helper.py` - OpenAI API（支持 JSON Schema 强制输出）
   - `anthropic_helper.py` - Anthropic Claude API（使用 tools + tool_choice 强制结构化）
   - 两者输出接口一致，可互换

4. **数据写出** (`term_data.py`):
   - `write_output_csv()` - 输出到 `data/output/memo/` 目录

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

## 关键设计模式

### 1. 路径自动解析
两个管道均使用 `_find_project_root()` 自动定位项目根目录（通过查找 `data/` 目录）。所有路径计算基于项目根，无需手动配置。

### 2. BatchID 生成（MMS Pipeline）
格式：`YYMMDD + RunLetter + NNN`
- `YYMMDD`: 纽约时区当日日期
- `RunLetter`: 当日批次字母（A-Z）
- `NNN`: 本批词条数（3 位零填充）

示例：`251007A015` = 2025-10-07 的首批（A），包含 15 个词条

### 3. LLM 统一接口
`OpenAIHelper` 和 `AnthropicHelper` 均实现 `complete_prompt(word, zh_def) -> dict` 接口：
- 使用相同的 `SYSTEM_PROMPT` 和 `TERM_RESULT_SCHEMA`
- 返回严格符合 schema 的 JSON（8 个字段）
- 自动处理 API 错误（如不支持的参数）

### 4. 容错输入处理
- CSV 读取支持：BOM 清除、多分隔符嗅探（`,` `;` `\t`）、大小写不敏感列名、中英文同义词映射
- 路径解析支持：绝对路径、相对路径、纯文件名、数字快捷方式
- 防覆盖：输出文件若存在，自动添加 `_2`, `_3` 后缀

## 开发约定

- **提示词**: 所有 LLM 提示词和 Schema 定义集中在 `openai_helper.py`，由两个引擎共享
- **进度显示**: 必须使用 tqdm 显示进度条（项目要求）
- **错误处理**: 初始化失败时抛出 `RuntimeError` 并提供清晰错误信息
- **编码**: 统一使用 UTF-8（读写文件时指定 `encoding="utf-8"` 或 `utf-8-sig`）
