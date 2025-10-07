# Memosyne 代码评估与重构方案

## 📊 代码库现状

- **文件数量**: 10 个 Python 文件
- **总代码行数**: ~1,253 行
- **主要模块**: MMS Pipeline (术语处理) + ExParser (测验解析)

---

## ✅ 现有优点

### 1. 架构层面
- ✅ **功能分离清晰**: MMS 和 ExParser 两个管道职责明确
- ✅ **多引擎支持**: 支持 OpenAI 和 Anthropic 两种 LLM
- ✅ **智能路径处理**: 自动识别项目根目录，防文件覆盖

### 2. 代码质量
- ✅ **类型提示**: 使用了 Python 类型注解（虽不完整）
- ✅ **数据类**: 使用 `@dataclass` 定义数据结构
- ✅ **进度显示**: 使用 tqdm 提供用户反馈
- ✅ **容错处理**: CSV 解析支持多分隔符、BOM、多语言列名

### 3. 用户体验
- ✅ **交互式引导**: 清晰的命令行提示
- ✅ **批次管理**: 自动生成 BatchID（日期 + 字母 + 数量）
- ✅ **错误提示**: 友好的错误信息

---

## ⚠️ 存在问题（按严重程度排序）

### 🔴 严重问题

#### 1. **配置管理混乱**
**问题**:
```python
# main.py:48-55 - 手写 .env 解析器
def _load_dotenv_simple(path: Path):
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())
```
**影响**:
- 没有类型验证（API Key 可能是空字符串）
- 没有必填项检查
- 不支持多环境配置
- 难以测试

#### 2. **缺少抽象层/接口定义**
**问题**:
```python
# term_processor.py:22 - 依赖具体实现而非抽象
class TermProcessor:
    def __init__(self, openai_helper: OpenAIHelper, ...):  # 应该是抽象接口
        self.llm = openai_helper
```
**影响**:
- OpenAIHelper 和 AnthropicHelper 没有共同基类
- 无法利用多态
- 测试时必须依赖真实 API

#### 3. **重复代码严重**
**问题**: 两个 `main.py` 包含相同的工具函数：
- `_find_project_root()` - 出现 2 次
- `_unique_path()` - 出现 2 次
- `_load_dotenv_simple()` - 出现 2 次
- `ask()` - 出现 2 次

**影响**: 维护成本翻倍，修改需同步两处

#### 4. **全局状态泛滥**
**问题**:
```python
# main.py:30-33
ROOT = _find_project_root()           # 全局变量
DATA_IN = ROOT / "data" / "input" / "memo"
DATA_OUT = ROOT / "data" / "output" / "memo"
TERMLIST_PATH = ROOT / "db" / "term_list_v1.csv"
```
**影响**:
- 测试困难（无法注入测试路径）
- 并发不安全
- 违反依赖倒置原则

### 🟡 中等问题

#### 5. **缺少数据验证**
**问题**: 输入输出数据没有运行时验证
```python
@dataclass
class InRow:
    Word: str      # 可能是空字符串
    ZhDef: str     # 可能包含非法字符
```
**建议**: 使用 Pydantic BaseModel 替代 dataclass

#### 6. **职责过于集中**
**问题**: `main.py` 承担了过多职责：
- ✗ 用户交互（ask 函数）
- ✗ 路径解析（_resolve_input_and_memo）
- ✗ 批次ID生成（_make_batch_id）
- ✗ 模型名解析（_resolve_model）
- ✗ 流程编排（main 函数）

**违反**: 单一职责原则（SRP）

#### 7. **缺少结构化日志**
**问题**: 只有 `print()` 语句，没有：
- 日志级别（INFO/WARNING/ERROR）
- 时间戳
- 上下文信息（BatchID、模型名等）

#### 8. **硬编码魔法值**
**问题**: 散落各处的常量
```python
# 魔法数字
if len(cn) == 2:  # 为什么是2？
k = 2             # 为什么从2开始？

# 魔法字符串
if u == "4":      # 应该用枚举
    return "gpt-4o-mini", "4oMini"
```

### 🟢 轻微问题

#### 9. **文档不足**
- 缺少函数 docstring
- 复杂逻辑没有注释
- 没有 API 文档

#### 10. **异常处理粗糙**
```python
try:
    entries = read_input_csv(str(input_path))
except Exception as e:  # 捕获范围太宽
    print(f"读取输入失败：{e}")
    return
```

---

## 🎯 重构方案

### 阶段一：基础设施改进（优先级：🔴 高）

#### 1.1 引入配置管理系统
**目标**: 类型安全、环境分离、验证
```python
# config/settings.py
from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    openai_api_key: str
    anthropic_api_key: str | None = None
    default_model: str = "gpt-4o-mini"

    # 路径配置
    data_dir: Path = Path("data")
    db_dir: Path = Path("db")

    # 业务配置
    batch_timezone: str = "America/New_York"
    max_batch_runs_per_day: int = 26

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
```

#### 1.2 定义抽象接口
```python
# core/interfaces.py
from abc import ABC, abstractmethod
from typing import Protocol

class LLMProvider(Protocol):
    """LLM 提供商协议（鸭子类型）"""
    def complete_prompt(self, word: str, zh_def: str) -> dict: ...

# 或者使用 ABC
class BaseLLMProvider(ABC):
    @abstractmethod
    def complete_prompt(self, word: str, zh_def: str) -> dict:
        pass
```

#### 1.3 提取公共工具模块
```python
# utils/
#   __init__.py
#   path.py          - find_project_root, unique_path
#   io.py            - ask, load_env
#   batch.py         - BatchIDGenerator
#   validation.py    - 数据验证工具
```

### 阶段二：架构优化（优先级：🟡 中）

#### 2.1 引入依赖注入
```python
# core/container.py
from dataclasses import dataclass
from config.settings import Settings

@dataclass
class AppContext:
    """应用上下文（依赖容器）"""
    settings: Settings
    llm_provider: LLMProvider
    term_list: TermList
    batch_id_generator: BatchIDGenerator
```

#### 2.2 使用 Pydantic 数据模型
```python
# models/term.py
from pydantic import BaseModel, Field, validator

class TermInput(BaseModel):
    word: str = Field(..., min_length=1)
    zh_def: str = Field(..., min_length=1)

    @validator('word')
    def validate_word(cls, v):
        if not v.strip():
            raise ValueError('Word cannot be empty')
        return v.strip()

class TermOutput(BaseModel):
    memo_id: str
    word: str
    zh_def: str
    ipa: str = Field(default="", regex=r"^(\/[^\s\/].*\/|)$")
    pos: str = Field(..., regex=r"^(n\.|vt\.|vi\.|adj\.|adv\.|P\.|O\.|abbr\.)$")
    # ... 其他字段
```

#### 2.3 添加结构化日志
```python
# utils/logging.py
import structlog

logger = structlog.get_logger()

# 使用
logger.info("processing_term",
            word=word,
            batch_id=batch_id,
            model=model_name)
```

### 阶段三：代码质量提升（优先级：🟢 低）

#### 3.1 添加单元测试
```python
# tests/
#   test_term_processor.py
#   test_llm_providers.py
#   test_batch_generator.py
#   conftest.py  # pytest fixtures
```

#### 3.2 添加类型检查
```bash
# pyproject.toml
[tool.mypy]
python_version = "3.11"
strict = true
```

#### 3.3 添加代码格式化
```bash
# 使用 ruff 替代 black + isort + flake8
ruff check .
ruff format .
```

---

## 📁 重构后的项目结构

```
memosyne/
├── src/
│   ├── memosyne/                    # 主包名
│   │   ├── __init__.py
│   │   ├── config/                  # 配置模块
│   │   │   ├── __init__.py
│   │   │   └── settings.py          # Pydantic Settings
│   │   ├── core/                    # 核心抽象
│   │   │   ├── __init__.py
│   │   │   ├── interfaces.py        # Protocol/ABC 定义
│   │   │   ├── container.py         # 依赖注入容器
│   │   │   └── exceptions.py        # 自定义异常
│   │   ├── models/                  # 数据模型
│   │   │   ├── __init__.py
│   │   │   ├── term.py              # 术语相关模型
│   │   │   └── quiz.py              # 测验相关模型
│   │   ├── providers/               # LLM 提供商（原 helpers）
│   │   │   ├── __init__.py
│   │   │   ├── base.py              # BaseLLMProvider
│   │   │   ├── openai.py            # OpenAI 实现
│   │   │   └── anthropic.py         # Anthropic 实现
│   │   ├── services/                # 业务逻辑
│   │   │   ├── __init__.py
│   │   │   ├── term_processor.py    # 术语处理服务
│   │   │   ├── quiz_parser.py       # 测验解析服务
│   │   │   └── batch_manager.py     # 批次管理服务
│   │   ├── repositories/            # 数据访问层
│   │   │   ├── __init__.py
│   │   │   ├── csv_repository.py    # CSV 读写
│   │   │   └── term_list_repo.py    # 术语表仓储
│   │   ├── cli/                     # 命令行接口
│   │   │   ├── __init__.py
│   │   │   ├── mms.py               # MMS CLI
│   │   │   ├── parser.py            # Parser CLI
│   │   │   └── prompts.py           # 交互提示
│   │   └── utils/                   # 工具函数
│   │       ├── __init__.py
│   │       ├── path.py
│   │       ├── io.py
│   │       └── logging.py
├── tests/                           # 测试
│   ├── unit/
│   ├── integration/
│   └── conftest.py
├── data/                            # 数据目录（不变）
├── db/                              # 数据库目录（不变）
├── .env.example                     # 环境变量示例
├── pyproject.toml                   # 现代 Python 项目配置
├── requirements.txt                 # 保留向后兼容
└── README.md
```

---

## 🔧 新增依赖建议

```toml
# pyproject.toml
[project]
dependencies = [
    "openai>=1.30.0",
    "anthropic>=0.31.0",
    "pydantic>=2.5.0",           # 数据验证
    "pydantic-settings>=2.0.0",  # 配置管理
    "structlog>=23.2.0",         # 结构化日志
    "click>=8.1.0",              # CLI 框架（可选，替代手写 ask）
    "rich>=13.7.0",              # 美化终端输出（可选）
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "mypy>=1.7.0",
    "ruff>=0.1.0",
]
```

---

## 📋 实施计划

### Sprint 1: 基础设施（1-2天）
- [ ] 创建新项目结构
- [ ] 迁移现有代码到新目录
- [ ] 实现 `Settings` 配置类
- [ ] 提取公共工具到 `utils/`
- [ ] 定义 `LLMProvider` 接口

### Sprint 2: 重构核心（2-3天）
- [ ] 重构 LLM Providers 继承 `BaseLLMProvider`
- [ ] 使用 Pydantic 替换 dataclass
- [ ] 实现依赖注入容器
- [ ] 重构 `TermProcessor` 和 `QuizParser`
- [ ] 添加结构化日志

### Sprint 3: 测试和文档（1-2天）
- [ ] 编写单元测试（目标覆盖率 >80%）
- [ ] 添加集成测试
- [ ] 完善 docstring
- [ ] 更新 README.md
- [ ] 配置 mypy + ruff

---

## 🎓 代码质量对比

| 指标 | 重构前 | 重构后 |
|------|--------|--------|
| 代码重复率 | ~15% | <3% |
| 类型覆盖率 | ~40% | >90% |
| 测试覆盖率 | 0% | >80% |
| 配置管理 | 手写解析 | Pydantic Settings |
| 日志系统 | print() | structlog |
| 接口抽象 | ❌ | ✅ Protocol/ABC |
| 依赖注入 | ❌ | ✅ Container |
| 文档完整度 | 低 | 高 |

---

## 💡 重构收益

### 可维护性
- ✅ 单一职责：每个模块职责清晰
- ✅ 开闭原则：新增 LLM 提供商无需修改现有代码
- ✅ 依赖倒置：依赖抽象而非具体实现

### 可测试性
- ✅ Mock 友好：可注入假 LLM Provider
- ✅ 隔离测试：路径、配置可独立控制
- ✅ 快速测试：无需真实 API 调用

### 可扩展性
- ✅ 新增 LLM：实现 `LLMProvider` 接口即可
- ✅ 新增命令：在 `cli/` 下添加模块
- ✅ 新增格式：在 `repositories/` 添加新仓储

### 开发体验
- ✅ IDE 提示：完整类型提示
- ✅ 错误提前：配置验证在启动时完成
- ✅ 调试容易：结构化日志包含上下文

---

## ⚡ 快速开始重构

选择以下方案之一：

### 方案 A: 渐进式重构（推荐）
1. 保留现有代码
2. 在新分支创建新结构
3. 逐步迁移模块
4. 使用 Adapter 模式过渡

### 方案 B: 重写式重构
1. 创建 `v2/` 目录
2. 按新架构实现
3. 并行运行，逐步切换
4. 弃用旧代码

### 方案 C: 增量改进（最低风险）
1. 先提取公共工具（`utils/`）
2. 再添加配置系统（`config/`）
3. 逐个重构服务（`services/`）
4. 最后添加测试和文档
