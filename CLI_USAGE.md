# CLI 使用指南

## 快速开始

### 方式 1：使用快捷脚本（推荐）

```bash
# Reanimator - 术语处理
./run_reanimate.sh

# Lithoformer - Quiz 解析
./run_lithoform.sh
```

### 方式 2：使用 Python 模块方式

```bash
cd /path/to/Memosyne

# Reanimator
python -m memosyne.reanimator.cli.main

# Lithoformer
python -m memosyne.lithoformer.cli.main
```

### 方式 3：在 PyCharm/IDE 中运行

**配置 PyCharm Run Configuration：**

1. 打开 `Run` → `Edit Configurations`
2. 点击 `+` → `Python`
3. 配置如下：

**Reanimator:**
- **Name**: Reanimator CLI
- **Module name**: `memosyne.reanimator.cli.main` （选择 "Module name" 而不是 "Script path"）
- **Working directory**: `/path/to/Memosyne`
- **Environment variables**: `PYTHONPATH=src`
- **Python interpreter**: 选择项目的虚拟环境

**Lithoformer:**
- **Name**: Lithoformer CLI
- **Module name**: `memosyne.lithoformer.cli.main`
- **Working directory**: `/path/to/Memosyne`
- **Environment variables**: `PYTHONPATH=src`
- **Python interpreter**: 选择项目的虚拟环境

4. 点击 `OK` 保存
5. 在工具栏选择配置并点击运行按钮（绿色三角形）

### ~~方式 4：直接运行文件~~（已移除）

**注意**: 不再支持直接运行 CLI 文件。请使用上述方式 1、2 或 3。

## 常见问题

### Q: 运行时出现 "ImportError: attempted relative import with no known parent package"

**原因**: 直接运行文件但没有设置 PYTHONPATH

**解决方案**:
1. 使用方式 1 或方式 2（推荐）
2. 或者在运行前设置 `PYTHONPATH=src`

### Q: PyCharm 中运行失败

**解决方案**:
1. 确保使用 "Module name" 而不是 "Script path"
2. 设置 Working directory 为项目根目录
3. 添加环境变量 `PYTHONPATH=src`
4. 选择正确的 Python 解释器（虚拟环境）

### Q: 找不到 .env 文件

**解决方案**:
1. 复制 `.env.example` 为 `.env`
2. 填入真实的 API 密钥
3. 确保 .env 文件在项目根目录

## 编程 API 使用

如果您想在代码中调用，而不是使用 CLI：

```python
from memosyne import reanimate, lithoform

# Reanimator - 处理术语
result = reanimate(
    input_csv="data/input/reanimator/221.csv",
    start_memo_index=221,
    model="gpt-4o-mini"
)
print(f"处理了 {result['success_count']} 个术语")
print(f"Token 使用: {result['token_usage']}")

# Lithoformer - 解析 Quiz
result = lithoform(
    input_md="data/input/lithoformer/quiz.md",
    model="gpt-4o-mini"
)
print(f"解析了 {result['success_count']} 道题")
print(f"输出路径: {result['output_path']}")
```

## 项目结构

```
Memosyne/
├── run_reanimate.sh       # Reanimator 快捷脚本
├── run_lithoform.sh       # Lithoformer 快捷脚本
├── CLI_USAGE.md           # CLI 使用指南（本文件）
├── .env                   # 配置文件（需要自行创建）
├── .env.example           # 配置模板
└── src/
    └── memosyne/
        ├── reanimator/
        │   └── cli/
        │       └── main.py    # Reanimator CLI 入口
        └── lithoformer/
            └── cli/
                └── main.py    # Lithoformer CLI 入口
```

## 更多信息

- 完整文档：`README.md`
- 架构说明：`ARCHITECTURE.md`
- API 指南：`API_GUIDE.md`
