# Memosyne API 使用指南

本指南介绍如何在 Python 程序中使用 Memosyne 的编程 API。

## 目录

- [快速开始](#快速开始)
- [API 函数详解](#api-函数详解)
  - [reanimate()](#reanimate)
  - [lithoform()](#lithoform)
- [返回值说明](#返回值说明)
- [错误处理](#错误处理)
- [高级用法](#高级用法)
- [最佳实践](#最佳实践)
- [常见问题](#常见问题)

---

## 快速开始

### 安装与配置

1. **安装依赖**：
   ```bash
   pip install -r requirements.txt
   ```

2. **配置环境变量**：
   ```bash
   cp .env.example .env
   # 编辑 .env 文件，填入你的 API 密钥
   ```

3. **导入 API**：
   ```python
   from memosyne.api import reanimate, lithoform
   ```

### 示例 1：重生术语列表 (Reanimater)

```python
from memosyne.api import reanimate

# 处理术语（使用默认的 OpenAI gpt-4o-mini 模型）
result = reanimate(
    input_csv="data/input/reanimater/terms.csv",  # 输入 CSV 文件
    start_memo_index=2700,                         # 起始 Memo 编号（M002701）
    batch_note="心理学术语"                        # 批次备注
)

print(f"✓ 成功处理 {result['processed_count']} 个术语")
print(f"✓ 批次ID: {result['batch_id']}")
print(f"✓ 输出文件: {result['output_path']}")
```

### 示例 2：石化测验文档 (Lithoformer)

```python
from memosyne.api import lithoform

# 解析 Quiz Markdown 文档
result = lithoform(
    input_md="data/input/lithoformer/chapter3.md",  # 输入 Markdown 文件
    title_main="Chapter 3 Quiz",                    # 主标题
    title_sub="Assessment and Classification"       # 副标题
)

print(f"✓ 成功解析 {result['item_count']} 道题")
print(f"✓ 输出文件: {result['output_path']}")
```

---

## API 函数详解

### reanimate()

处理术语列表，生成结构化术语卡片（Reanimater Pipeline）。

#### 函数签名

```python
def reanimate(
    input_csv: str | Path,
    start_memo_index: int,
    output_csv: str | Path | None = None,
    model: str = "gpt-4o-mini",
    provider: Literal["openai", "anthropic"] = "openai",
    batch_note: str = "",
    temperature: float | None = None,
    show_progress: bool = True,
) -> dict:
```

#### 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `input_csv` | str \| Path | ✓ | 输入 CSV 文件路径，包含 `word` 和 `zh_def` 列 |
| `start_memo_index` | int | ✓ | 起始 Memo 编号（如 `2700` 表示从 M002701 开始） |
| `output_csv` | str \| Path \| None | ✗ | 输出 CSV 文件路径（默认自动生成到 `data/output/reanimater/`） |
| `model` | str | ✗ | 模型 ID，默认 `"gpt-4o-mini"` |
| `provider` | "openai" \| "anthropic" | ✗ | LLM 提供商，默认 `"openai"` |
| `batch_note` | str | ✗ | 批次备注（会出现在输出 CSV 的 BatchNote 列） |
| `temperature` | float \| None | ✗ | LLM 温度参数（0.0-2.0），`None` 使用模型默认值 |
| `show_progress` | bool | ✗ | 是否显示进度条，默认 `True` |

#### 返回值

返回一个字典，包含以下字段：

```python
{
    "success": True,                  # 是否成功
    "output_path": "data/output/reanimater/251010A015.csv",  # 输出文件路径
    "batch_id": "251010A015",         # 批次 ID（格式：YYMMDD + 批次字母 + 词条数）
    "processed_count": 15,            # 成功处理的术语数量
    "total_count": 15,                # 总术语数量
    "results": [TermOutput(...), ...],  # 处理结果列表（Pydantic 模型）
    "token_usage": {                  # Token 使用统计
        "prompt_tokens": 1234,
        "completion_tokens": 5678,
        "total_tokens": 6912
    }
}
```

#### 输入 CSV 格式

输入文件需包含以下列（列名不区分大小写）：

| 列名 | 必填 | 说明 |
|------|------|------|
| `word` | ✓ | 英文词条（如 "neuron"） |
| `zh_def` | ✓ | 中文释义（如 "神经元"） |

示例 CSV：
```csv
word,zh_def
neuron,神经元
synapse,突触
hippocampus,海马体
```

#### 输出 CSV 格式

输出文件包含以下列：

| 列名 | 说明 |
|------|------|
| `WMpair` | Word + ZhDef 组合 |
| `MemoID` | Memo ID（如 M002701） |
| `Word` | 英文词条 |
| `ZhDef` | 中文释义 |
| `IPA` | 国际音标（如 /ˈnjʊɹɑn/） |
| `POS` | 词性（n., vt., vi., adj., adv., P., O., abbr.） |
| `Tag` | 中文标签（两字，如 "心理"） |
| `Rarity` | 稀有度（"" 或 "RARE"） |
| `EnDef` | 英文定义 |
| `Example` | 例句 |
| `PPfix` | 词根/词缀（空格分隔） |
| `PPmeans` | 词根/词缀含义（空格分隔） |
| `BatchID` | 批次 ID |
| `BatchNote` | 批次备注 |

#### 使用示例

**示例 1：基础用法（使用 OpenAI）**

```python
from memosyne.api import reanimate

result = reanimate(
    input_csv="terms.csv",
    start_memo_index=2700
)
```

**示例 2：使用 Anthropic Claude**

```python
result = reanimate(
    input_csv="terms.csv",
    start_memo_index=2700,
    provider="anthropic",
    model="claude-3-5-sonnet-20241022"
)
```

**示例 3：自定义输出路径**

```python
result = reanimate(
    input_csv="terms.csv",
    start_memo_index=2700,
    output_csv="my_output.csv",  # 将保存到 data/output/reanimater/my_output.csv
    batch_note="测试批次"
)
```

**示例 4：调整 LLM 参数并查看 Token 使用**

```python
result = reanimate(
    input_csv="terms.csv",
    start_memo_index=2700,
    model="gpt-4o",             # 使用更强大的模型
    temperature=0.3,             # 降低随机性
    show_progress=True           # 进度条会显示实时 Token 使用量
)

# 查看 Token 使用统计
print(f"Prompt Tokens: {result['token_usage']['prompt_tokens']}")
print(f"Completion Tokens: {result['token_usage']['completion_tokens']}")
print(f"Total Tokens: {result['token_usage']['total_tokens']}")
```

---

### lithoform()

解析 Markdown 格式的测验文档，转换为标准化格式（Lithoformer）。

#### 函数签名

```python
def lithoform(
    input_md: str | Path,
    output_txt: str | Path | None = None,
    model: str = "gpt-4o-mini",
    provider: Literal["openai", "anthropic"] = "openai",
    title_main: str | None = None,
    title_sub: str | None = None,
    temperature: float | None = None,
    show_progress: bool = True,
) -> dict:
```

#### 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `input_md` | str \| Path | ✓ | 输入 Markdown 文件路径 |
| `output_txt` | str \| Path \| None | ✗ | 输出 TXT 文件路径（默认自动生成到 `data/output/lithoformer/`） |
| `model` | str | ✗ | 模型 ID，默认 `"gpt-4o-mini"` |
| `provider` | "openai" \| "anthropic" | ✗ | LLM 提供商，默认 `"openai"` |
| `title_main` | str \| None | ✗ | 主标题（`None` 自动从文件名推断） |
| `title_sub` | str \| None | ✗ | 副标题（`None` 自动从文件名推断） |
| `temperature` | float \| None | ✗ | LLM 温度参数（0.0-2.0），`None` 使用模型默认值 |
| `show_progress` | bool | ✗ | 是否显示进度条（含 Token 使用量），默认 `True` |

#### 返回值

返回一个字典，包含以下字段：

```python
{
    "success": True,                  # 是否成功
    "output_path": "data/output/lithoformer/ShouldBe.txt",  # 输出文件路径
    "item_count": 25,                 # 成功解析的题目数量
    "total_count": 25,                # 总题目数量
    "title_main": "Chapter 3 Quiz",   # 主标题
    "title_sub": "Assessment and Classification",  # 副标题
    "token_usage": {                  # Token 使用统计
        "prompt_tokens": 2345,
        "completion_tokens": 3456,
        "total_tokens": 5801
    }
}
```

#### 输入 Markdown 格式

输入文件应为标准的 Markdown 测验文档，包含题目、选项和答案。示例：

```markdown
1. What is a neuron?
   A. A type of cell in the nervous system
   B. A hormone
   C. A brain structure
   D. A chemical messenger

Correct answer: A

2. Which of the following is NOT a neurotransmitter?
   A. Dopamine
   B. Serotonin
   C. Insulin
   D. GABA

Correct answer: C
```

#### 支持的题型

- **MCQ（选择题）**：包含字母选项（A/B/C/D/E/F）
- **CLOZE（填空题）**：包含下划线 `____` 且无字母选项
- **ORDER（排序题）**：要求排列步骤顺序

#### 使用示例

**示例 1：基础用法（自动推断标题）**

```python
from memosyne.api import lithoform

# 文件名：Chapter 3 Quiz- Assessment and Classification.md
# 自动推断标题
result = lithoform(input_md="chapter3.md")
print(result['title_main'])  # "Chapter 3 Quiz"
print(result['title_sub'])   # "Assessment and Classification"
```

**示例 2：手动指定标题**

```python
result = lithoform(
    input_md="quiz.md",
    title_main="Midterm Exam",
    title_sub="Chapters 1-5"
)
```

**示例 3：使用 Claude 模型**

```python
result = lithoform(
    input_md="quiz.md",
    provider="anthropic",
    model="claude-3-5-sonnet-20241022"
)
```

**示例 4：自定义输出路径并查看 Token 使用**

```python
result = lithoform(
    input_md="quiz.md",
    output_txt="chapter3_output.txt",  # 保存到 data/output/lithoformer/chapter3_output.txt
    title_main="Chapter 3 Quiz",
    show_progress=True  # 进度条会显示实时 Token 使用量
)

# 查看 Token 使用统计
print(f"Total Tokens: {result['token_usage']['total_tokens']}")
```

---

## 返回值说明

两个 API 函数都返回字典，包含 `success` 字段指示是否成功。

### 成功返回

```python
{
    "success": True,
    # ... 其他字段
}
```

### 异常情况

如果发生错误，会抛出以下异常（不会返回 `{"success": False}`）：

| 异常类型 | 说明 |
|---------|------|
| `FileNotFoundError` | 输入文件不存在 |
| `ValueError` | 参数错误（如不支持的 provider） |
| `LLMError` | LLM 调用失败（API 错误、响应格式错误等） |
| `ConfigError` | 配置错误（如 API 密钥未设置） |

---

## 错误处理

### 基础错误处理

```python
from memosyne.api import reanimate
from memosyne.core.interfaces import LLMError, ConfigError

try:
    result = reanimate(
        input_csv="terms.csv",
        start_memo_index=2700
    )
    print(f"✓ 成功处理 {result['processed_count']} 个术语")

except FileNotFoundError as e:
    print(f"✗ 文件不存在: {e}")

except ValueError as e:
    print(f"✗ 参数错误: {e}")

except ConfigError as e:
    print(f"✗ 配置错误: {e}")

except LLMError as e:
    print(f"✗ LLM 调用失败: {e}")

except Exception as e:
    print(f"✗ 未知错误: {e}")
```

### 重试机制

```python
import time
from memosyne.api import reanimate
from memosyne.core.interfaces import LLMError

MAX_RETRIES = 3

for attempt in range(MAX_RETRIES):
    try:
        result = reanimate(
            input_csv="terms.csv",
            start_memo_index=2700
        )
        print(f"✓ 成功（尝试 {attempt + 1}/{MAX_RETRIES}）")
        break

    except LLMError as e:
        if attempt < MAX_RETRIES - 1:
            wait_time = 2 ** attempt  # 指数退避：1s, 2s, 4s
            print(f"✗ 失败（尝试 {attempt + 1}/{MAX_RETRIES}），{wait_time}秒后重试...")
            time.sleep(wait_time)
        else:
            print(f"✗ 所有尝试均失败: {e}")
            raise
```

---

## 高级用法

### 示例 1：批量处理多个文件

```python
from pathlib import Path
from memosyne.api import reanimate

input_dir = Path("data/input/reanimater")
start_index = 2700

for csv_file in input_dir.glob("*.csv"):
    print(f"\n处理文件: {csv_file.name}")

    result = reanimate(
        input_csv=csv_file,
        start_memo_index=start_index,
        batch_note=f"批量处理 {csv_file.stem}"
    )

    print(f"✓ {result['batch_id']}: {result['processed_count']} 个术语")

    # 更新下一个文件的起始索引
    start_index += result['processed_count']
```

### 示例 2：自定义日志记录

```python
import logging
from memosyne.api import reanimate
from memosyne.utils.logger import setup_logger

# 配置日志
logger = setup_logger(
    name="my_app",
    level="DEBUG",
    log_file="logs/processing.log",
    format_type="detailed"
)

logger.info("开始处理术语")

try:
    result = reanimate(
        input_csv="terms.csv",
        start_memo_index=2700
    )
    logger.info(f"成功处理 {result['processed_count']} 个术语")

except Exception as e:
    logger.error("处理失败", exc_info=True)
    raise
```

### 示例 3：处理大型数据集（流式处理）

```python
from memosyne.api import reanimate
from memosyne.models import TermInput

def term_generator():
    """生成器，逐行读取大型 CSV 文件"""
    import csv
    with open("large_terms.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield TermInput(word=row["word"], zh_def=row["zh_def"])

# 注意：当前 API 会在内部转换为列表
# 如果需要真正的流式处理，需要直接使用 Reanimater 服务
```

### 示例 4：访问详细结果

```python
from memosyne.api import reanimate

result = reanimate(
    input_csv="terms.csv",
    start_memo_index=2700
)

# 遍历每个术语的结果
for term_output in result['results']:
    print(f"\n{term_output.memo_id}: {term_output.word}")
    print(f"  IPA: {term_output.ipa}")
    print(f"  POS: {term_output.pos}")
    print(f"  EnDef: {term_output.en_def}")
    print(f"  Tag: {term_output.tag}")

    # 检查是否为稀有词
    if term_output.rarity == "RARE":
        print(f"  ⚠️  标记为稀有词")
```

### 示例 5：并发处理多个文件（谨慎使用）

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from memosyne.api import reanimate

def process_file(csv_file, start_index):
    """处理单个文件"""
    result = reanimate(
        input_csv=csv_file,
        start_memo_index=start_index,
        show_progress=False  # 并发时关闭进度条
    )
    return csv_file.name, result

# 准备任务
input_dir = Path("data/input/reanimater")
tasks = [
    (csv_file, 2700 + i * 100)
    for i, csv_file in enumerate(input_dir.glob("*.csv"))
]

# 并发执行（注意 API 速率限制！）
with ThreadPoolExecutor(max_workers=3) as executor:
    futures = {
        executor.submit(process_file, file, idx): file
        for file, idx in tasks
    }

    for future in as_completed(futures):
        filename, result = future.result()
        print(f"✓ {filename}: {result['batch_id']}")
```

**⚠️ 警告**：并发请求可能触发 LLM API 的速率限制，建议：
- 限制并发数（`max_workers=3`）
- 添加速率限制逻辑
- 监控 API 使用量

---

## 最佳实践

### 1. 环境变量管理

**推荐做法**：
```python
# ✓ 使用 .env 文件管理 API 密钥
from memosyne.api import reanimate

result = reanimate(...)  # 自动从 .env 读取密钥
```

**不推荐做法**：
```python
# ✗ 硬编码 API 密钥
import os
os.environ["OPENAI_API_KEY"] = "sk-..."  # 容易泄露
```

### 2. 错误处理

- 总是捕获异常，特别是 `LLMError`
- 对关键任务实现重试机制
- 记录错误日志便于调试

### 3. 性能优化

- 对大批量任务，使用 `show_progress=True` 监控进度
- 考虑使用更快的模型（如 `gpt-4o-mini`）
- 避免频繁的小批量请求，合并为大批量

### 4. 成本控制

- 使用 `gpt-4o-mini` 而非 `gpt-4o`（成本降低约 10 倍）
- 监控 API 使用量
- 对非关键任务降低 `temperature`

### 5. 数据管理

- 定期备份 `data/output/` 目录
- 使用有意义的 `batch_note` 便于追溯
- 保留输入文件用于审计

---

## 常见问题

### Q1: 如何更换 LLM 提供商？

**A**: 设置 `provider` 参数：

```python
# 使用 OpenAI（默认）
result = reanimate(..., provider="openai", model="gpt-4o-mini")

# 使用 Anthropic
result = reanimate(..., provider="anthropic", model="claude-3-5-sonnet-20241022")
```

确保 `.env` 中配置了相应的 API 密钥。

### Q2: 如何处理 API 速率限制？

**A**: 实现指数退避重试：

```python
import time
from memosyne.core.interfaces import LLMError

for attempt in range(3):
    try:
        result = reanimate(...)
        break
    except LLMError as e:
        if "rate" in str(e).lower():
            wait_time = 2 ** attempt
            time.sleep(wait_time)
        else:
            raise
```

### Q3: 输入 CSV 列名不匹配怎么办？

**A**: API 自动识别以下列名变体（不区分大小写）：
- `word`, `Word`, `WORD`, `term`, `英文`
- `zh_def`, `ZhDef`, `chinese`, `中文释义`

如果列名完全不同，需要预处理 CSV 文件。

### Q4: 如何获取更详细的日志？

**A**: 配置日志级别：

```python
from memosyne.utils.logger import setup_logger

logger = setup_logger(name="memosyne", level="DEBUG")

# 现在会输出详细的调试信息
result = reanimate(...)
```

### Q5: 支持哪些模型？

**A**:

**OpenAI**：
- `gpt-4o-mini` （推荐，快速且便宜）
- `gpt-4o` （更强大，但成本更高）
- `o1-mini` （如需深度推理）

**Anthropic**：
- `claude-3-5-sonnet-20241022` （推荐）
- `claude-3-5-haiku-20241022` （更快，但能力稍弱）

### Q6: 如何在 Web 服务中使用 API？

**A**: FastAPI 示例：

```python
from fastapi import FastAPI, UploadFile
from memosyne.api import reanimate
import tempfile

app = FastAPI()

@app.post("/reanimate")
async def upload_terms(file: UploadFile, start_index: int):
    # 保存上传的文件
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    # 处理术语
    result = reanimate(
        input_csv=tmp_path,
        start_memo_index=start_index
    )

    return {
        "batch_id": result['batch_id'],
        "count": result['processed_count']
    }
```

### Q7: 如何处理非 UTF-8 编码的输入文件？

**A**: 预先转换编码：

```python
import pandas as pd

# 读取非 UTF-8 文件
df = pd.read_csv("input.csv", encoding="gbk")

# 保存为 UTF-8
df.to_csv("input_utf8.csv", encoding="utf-8", index=False)

# 使用 API 处理
result = reanimate(input_csv="input_utf8.csv", ...)
```

---

## 相关文档

- [README.md](README.md) - 项目概览
- [ARCHITECTURE.md](ARCHITECTURE.md) - 架构设计
- [GIT_GUIDE.md](GIT_GUIDE.md) - Git 工作流程
- [CLAUDE.md](CLAUDE.md) - Claude Code 工作指南

---

**版本**: v0.7.1
**最后更新**: 2025-10-11
