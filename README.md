# Memosyne

<div align="center">

**基于 LLM 的术语处理和 Quiz 解析工具包**

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-0.7.1-orange.svg)]()

*专业、类型安全、易于扩展的 LLM 工作流工具*

[特性](#-特性) • [快速开始](#-快速开始) • [安装](#-安装) • [文档](#-文档) • [架构](#-架构)

</div>

---

## 📖 简介

Memosyne 是一个基于大语言模型（LLM）的术语处理和 Quiz 解析工具包，提供两个核心功能：

### 🔤 **术语处理 (Reanimater)**
将术语列表（英文单词 + 中文释义）扩展为完整的记忆卡片信息：
- 音标（IPA）
- 词性（POS）
- 英文定义（EnDef）
- 例句（Example）
- 词根词缀（PPfix/PPmeans）
- 领域标签（TagEN）

### 📝 **Quiz解析 (Lithoformer)**
将 Markdown 格式的 Quiz 文档解析为结构化的 ShouldBe.txt 格式，支持：
- 多选题（MCQ）
- 填空题（CLOZE）
- 排序题（ORDER）

---

## ✨ 特性

### 🏗️ **专业架构**
- ✅ **SOLID 原则**：单一职责、开放封闭、依赖倒置
- ✅ **分层架构**：Config → Core → Models → Prompts/Schemas → Providers → Services → CLI
- ✅ **依赖注入**：无全局状态，完全可测试
- ✅ **类型安全**：使用 Pydantic 2.x 进行运行时验证
- ✅ **统一日志系统**：使用 logging 模块，支持多种输出格式
- ✅ **Token 追踪**：完整的 Token 使用量统计和实时显示

### 🔌 **灵活扩展**
- ✅ 支持 **OpenAI** 和 **Anthropic** 双 Provider
- ✅ 统一的 LLM 接口，轻松添加新 Provider
- ✅ 可配置的模型、温度、重试策略

### 💻 **多种使用方式**
- ✅ **交互式 CLI** - 向导式操作
- ✅ **编程 API** - 在代码中直接调用
- ✅ **批量处理** - 支持大规模数据处理

### 📊 **完善的数据流**
- ✅ CSV 输入/输出（Reanimater）
- ✅ Markdown 输入 / TXT 输出（Lithoformer）
- ✅ 自动批次 ID 生成（格式：YYMMDD + RunLetter + Count）
- ✅ 防重名输出路径

---

## 🚀 快速开始

### 方式 1：交互式 CLI

```bash
# 术语重生 (Reanimate)
python src/memosyne/cli/reanimate.py

# Quiz重塑 (Lithoform)
python src/memosyne/cli/lithoform.py
```

### 方式 2：编程 API

```python
from memosyne import reanimate, lithoform

# 处理术语
result = reanimate(
    input_csv="221.csv",
    start_memo_index=221,
    model="gpt-4o-mini"
)
print(f"✅ 处理了 {result['processed_count']} 个术语")
print(f"📁 输出: {result['output_path']}")

# 解析 Quiz
result = lithoform(
    input_md="quiz.md",
    model="gpt-4o-mini"
)
print(f"✅ 解析了 {result['item_count']} 道题")
print(f"📁 输出: {result['output_path']}")
```

---

## 📦 安装

### 1. 克隆仓库

```bash
git clone <repository-url>
cd Memosyne
```

### 2. 创建虚拟环境

```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# 或
.venv\Scripts\activate     # Windows
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

复制 `.env.example` 文件并填入你的 API 密钥：

```bash
cp .env.example .env
# 编辑 .env 文件
```

`.env` 文件示例：

```env
# === LLM API 密钥（必填）===
OPENAI_API_KEY=your-openai-api-key-here
ANTHROPIC_API_KEY=your-anthropic-api-key-here  # 可选

# === 默认模型配置 ===
DEFAULT_LLM_PROVIDER=openai
DEFAULT_OPENAI_MODEL=gpt-4o-mini
DEFAULT_ANTHROPIC_MODEL=claude-sonnet-4-5
DEFAULT_TEMPERATURE=

# === 业务配置 ===
BATCH_TIMEZONE=America/New_York
MAX_BATCH_RUNS_PER_DAY=26
TERM_LIST_VERSION=v1

# === 日志配置 ===
LOG_LEVEL=INFO
LOG_FORMAT=console
```

---

## 📚 文档

- **[API 使用指南](API_GUIDE.md)** - 完整的 API 文档和示例
- **[架构说明](ARCHITECTURE.md)** - 系统架构和设计决策
- **[Git 使用指南](GIT_GUIDE.md)** - Git 项目管理完整教程

---

## 🏛️ 架构

### 项目结构

```
Memosyne/
├── src/memosyne/              # 主包
│   ├── api.py                 # ✨ 编程 API
│   ├── config/                # 配置管理
│   │   └── settings.py        # Pydantic Settings
│   ├── core/                  # 核心抽象
│   │   └── interfaces.py      # Protocol/ABC 定义
│   ├── models/                # 数据模型
│   │   ├── term.py            # 术语相关模型
│   │   ├── quiz.py            # Quiz 相关模型
│   │   └── result.py          # TokenUsage & ProcessResult
│   ├── prompts/               # LLM 提示词
│   │   ├── reanimater_prompts.py
│   │   └── lithoformer_prompts.py
│   ├── schemas/               # JSON Schema
│   │   ├── term_schema.py
│   │   └── quiz_schema.py
│   ├── providers/             # LLM 提供商
│   │   ├── openai_provider.py
│   │   └── anthropic_provider.py
│   ├── repositories/          # 数据访问层
│   │   ├── csv_repository.py
│   │   └── term_list_repository.py
│   ├── services/              # 业务逻辑
│   │   ├── reanimater.py
│   │   └── lithoformer.py
│   ├── utils/                 # 工具函数
│   │   ├── batch.py           # 批次ID生成
│   │   ├── path.py            # 路径工具
│   │   ├── quiz_formatter.py  # Quiz格式化
│   │   └── logger.py          # 日志配置
│   └── cli/                   # CLI 入口
│       ├── reanimate.py
│       └── lithoform.py
├── data/                      # 数据文件
│   ├── input/
│   │   ├── reanimater/        # Reanimater 输入
│   │   └── lithoformer/       # Lithoformer 输入
│   └── output/
│       ├── reanimater/        # Reanimater 输出
│       └── lithoformer/       # Lithoformer 输出
├── db/                        # 数据库/术语表
├── requirements.txt           # 依赖
└── .env                       # 环境变量
```

### 分层架构

```
┌─────────────────────────────────────┐
│          CLI / API Layer            │  用户接口
├─────────────────────────────────────┤
│         Service Layer               │  业务逻辑
├─────────────────────────────────────┤
│    Repository / Provider Layer      │  数据访问 / LLM 调用
├─────────────────────────────────────┤
│         Core / Models Layer         │  核心抽象 / 数据模型
├─────────────────────────────────────┤
│         Config Layer                │  配置管理
└─────────────────────────────────────┘
```

查看 [ARCHITECTURE.md](ARCHITECTURE.md) 了解详细的架构设计。

---

## 💡 使用示例

### Reanimater - 批量处理术语

```python
from memosyne import reanimate

files = ["221.csv", "222.csv", "223.csv"]

for i, filename in enumerate(files, start=221):
    result = reanimate(
        input_csv=filename,
        start_memo_index=i,
        model="gpt-4o-mini",
        batch_note=f"批次 {i}"
    )
    print(f"✅ {filename}: {result['batch_id']}")
```

### Lithoformer - 使用 Claude

```python
from memosyne import lithoform

result = lithoform(
    input_md="chapter3_quiz.md",
    model="claude-3-5-sonnet-20240620",
    provider="anthropic",
    temperature=0.5
)
print(f"✅ 解析了 {result['item_count']} 道题")
```

### 集成到 Web 服务

```python
from flask import Flask, request, jsonify
from memosyne import lithoform
import tempfile

app = Flask(__name__)

@app.route('/api/parse', methods=['POST'])
def api_parse():
    md_content = request.json['markdown']

    with tempfile.NamedTemporaryFile(mode='w', suffix='.md') as f:
        f.write(md_content)
        f.flush()

        result = lithoform(input_md=f.name, model="gpt-4o-mini")

        return jsonify({
            'success': result['success'],
            'item_count': result['item_count']
        })
```

---

## 🔧 开发

### 运行测试

```bash
# 测试 API
python test_api.py

# 测试组件
python test_lithoform.py
```

### 代码风格

项目遵循：
- **PEP 8** - Python 代码风格
- **Type Hints** - 完整的类型注解
- **Docstrings** - Google 风格文档字符串

### 添加新的 LLM Provider

1. 在 `providers/` 创建新文件
2. 继承 `BaseLLMProvider`
3. 实现 `complete_prompt()` 和 `complete_structured()` 方法
4. 在 `providers/__init__.py` 导出

示例：

```python
from ..core.interfaces import BaseLLMProvider, LLMError

class MyProvider(BaseLLMProvider):
    def __init__(self, model: str, api_key: str, temperature: float | None = None):
        self.client = MyClient(api_key=api_key)
        super().__init__(model=model, temperature=temperature)

    def complete_prompt(self, word: str, zh_def: str) -> tuple[dict, TokenUsage]:
        """用于 Reanimater 术语处理"""
        # 实现你的逻辑
        result = {...}
        tokens = TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        return result, tokens

    def complete_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: dict,
        schema_name: str = "Response"
    ) -> tuple[dict, TokenUsage]:
        """用于 Lithoformer Quiz 解析"""
        # 实现结构化输出逻辑
        result = {...}
        tokens = TokenUsage(prompt_tokens=15, completion_tokens=25, total_tokens=40)
        return result, tokens
```

---

## 📊 性能

### Reanimater 处理速度

| 术语数量 | 模型 | 耗时 |
|---------|------|------|
| 36 | gpt-4o-mini | ~2 分钟 |
| 36 | claude-3-5-sonnet | ~3 分钟 |
| 100 | gpt-4o-mini | ~5 分钟 |

### Lithoformer 解析速度

| 题目数量 | 模型 | 耗时 |
|---------|------|------|
| 15 | gpt-4o-mini | ~30 秒 |
| 50 | gpt-4o-mini | ~2 分钟 |

*注：速度取决于网络状况和 API 响应时间*

---

## 🐛 故障排除

### 问题：`ValidationError: Field required`

**原因**：`.env` 文件配置错误或 API Key 为空

**解决**：
1. 检查 `.env` 文件是否存在
2. 确保 `OPENAI_API_KEY` 已正确配置
3. 确保 API Key 长度 ≥ 20 字符

### 问题：`LLMError: OpenAI API 错误`

**原因**：API 调用失败（额度不足、网络问题等）

**解决**：
1. 检查 API Key 是否有效
2. 检查账户额度
3. 检查网络连接

### 问题：路径找不到

**原因**：输入文件路径错误

**解决**：
1. 使用相对路径时，文件应在 `data/input/reanimater/` 或 `data/input/lithoformer/`
2. 使用绝对路径确保路径正确
3. 检查文件名拼写

---

## 🤝 贡献

欢迎贡献！请遵循以下步骤：

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

## 📝 变更日志

### v0.7.1 (2025-10-11)

**深度重构：服务层统一与架构增强**

- ✨ **新增模块**：
  - `prompts/` - 集中管理 LLM 提示词（reanimater_prompts, lithoformer_prompts）
  - `schemas/` - 集中管理 JSON Schema（term_schema, quiz_schema）
  - `models/result.py` - TokenUsage 和 ProcessResult[T] 统一结果模型
- ✨ **服务层统一**：
  - Reanimater 和 Lithoformer 都添加 `from_settings()` 工厂方法
  - 统一方法名为 `process()`，返回 `ProcessResult[T]`
  - 进度条实时显示 Token 使用量（prompt/completion/total）
  - Lithoformer 支持文件路径输入（自动检测 Path vs 字符串）
  - 两个服务都支持 Logger 依赖注入
- ⚠️ **Breaking Changes**：
  - Provider 接口返回值改为 `tuple[dict, TokenUsage]`
  - OpenAIProvider 和 AnthropicProvider 都提取 token 使用量
  - 从新模块导入 prompts 和 schemas
  - 删除所有向后兼容别名（process_terms, parse_quiz）
- 📚 **文档更新**：
  - API_GUIDE.md - 删除向后兼容性章节，更新示例代码
  - ARCHITECTURE.md - 更新架构图、UML 类图、时序图
  - README.md - 更新项目结构和特性列表

### v0.6.2 (2025-10-10)

**架构增强与质量改进**

- ✨ 新增：统一日志系统（`utils/logger.py`），替换 print 为 logging
- ✨ 新增：Provider 抽象方法 `complete_structured()` 用于结构化输出
- ✨ 新增：`.env.example` 环境变量模板文件
- ✨ 新增：API_GUIDE.md 完整文档（40+ 示例）
- ✅ 改进：Lithoformer 添加结果校验，空题目列表会抛出错误
- ✅ 改进：Reanimater 添加告警日志（Example 与 EnDef 相同时）
- ✅ 改进：Reanimater 内存优化，避免强制转换迭代器为列表
- 🔧 修复：Lithoformer 破坏 Provider 抽象的问题，现使用统一接口
- 📚 文档：更新 CLAUDE.md、ARCHITECTURE.md、README.md

### v2.0.0 (2025-10-07)

**重大重构**

- ✨ 全新架构：采用 SOLID 原则和分层设计
- ✨ 编程 API：提供 `reanimate()` 和 `lithoform()` 函数
- ✨ 类型安全：使用 Pydantic 2.x 进行数据验证
- ✨ 双 Provider：支持 OpenAI 和 Anthropic
- 🔧 修复：项目根目录检测 bug
- 🔧 修复：Pydantic v2 兼容性问题
- 📚 文档：新增 API_GUIDE.md、ARCHITECTURE.md
- 🗑️ 移除：旧版代码（`src/mms_pipeline/`, `src/exparser/`）

### v1.0.0 (2024-09)

- 初始版本
- 基础 Reanimater 和 Lithoformer 功能

---

## 📄 许可证

本项目采用 [MIT 许可证](LICENSE)。

---

## 🙏 致谢

- OpenAI - 提供强大的 GPT 系列模型
- Anthropic - 提供 Claude 系列模型
- Pydantic - 提供出色的数据验证框架

---

<div align="center">

**Made with ❤️ by Memosyne Team**

⭐ 如果这个项目对你有帮助，请给个星标！

</div>
