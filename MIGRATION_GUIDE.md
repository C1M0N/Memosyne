# Memosyne v2.0 迁移指南

## 🎉 欢迎使用重构版本！

Memosyne v2.0 是完全重构的版本，采用了现代化的 Python 架构模式。**好消息**：你的数据、配置文件和工作流程**完全兼容**，无需任何修改。

---

## ⚡ 快速开始

### 1. 安装新依赖

```bash
# 安装 v2 依赖
pip install -r requirements-v2.txt

# 或使用原有依赖文件（会自动安装额外包）
pip install pydantic>=2.5.0 pydantic-settings>=2.0.0
```

### 2. 运行 MMS（新方式）

```bash
# v2.0 方式（推荐）
python -m memosyne.cli.mms

# 或直接运行
python src/memosyne/cli/mms.py
```

### 3. 运行 MMS（旧方式仍可用）

```bash
# v1.0 方式（仍然可用）
python src/mms_pipeline/main.py
```

---

## 📂 文件结构对比

### v1.0 结构
```
src/
├── mms_pipeline/
│   ├── main.py           # 260 行，职责过多
│   ├── openai_helper.py
│   ├── anthropic_helper.py
│   ├── term_processor.py
│   └── term_data.py
└── exparser/
    ├── main.py           # 166 行
    └── ...
```

### v2.0 结构
```
src/memosyne/
├── config/               # ✨ 新增：配置管理
│   └── settings.py
├── core/                 # ✨ 新增：抽象接口
│   └── interfaces.py
├── models/               # ✨ 新增：Pydantic 数据模型
│   └── term.py
├── providers/            # 🔄 重构：LLM 提供商
│   ├── openai_provider.py
│   └── anthropic_provider.py
├── repositories/         # ✨ 新增：数据访问层
│   ├── csv_repository.py
│   └── term_list_repository.py
├── services/             # 🔄 重构：业务逻辑
│   └── term_processor.py
├── utils/                # ✨ 新增：工具模块
│   ├── path.py
│   └── batch.py
└── cli/                  # 🔄 重构：CLI 接口
    ├── mms.py            # 仅 ~100 行！
    └── prompts.py
```

---

## 🔄 迁移检查清单

### ✅ 无需修改（自动兼容）

- [x] **.env 文件** - 完全兼容，无需修改
- [x] **data/ 目录** - 数据格式保持一致
- [x] **db/term_list_v1.csv** - 术语表格式不变
- [x] **CSV 输入/输出格式** - 完全一致
- [x] **批次 ID 格式** - 与 v1.0 相同
- [x] **交互流程** - 命令行提示保持一致

### 🆕 可选配置（新增功能）

如果你想使用新功能，可以在 `.env` 中添加：

```bash
# 新增配置项（可选）
DEFAULT_LLM_PROVIDER=openai        # 设置默认提供商
DEFAULT_TEMPERATURE=0.7            # 设置默认温度
LOG_LEVEL=INFO                     # 设置日志级别
```

---

## 📋 功能对比

| 功能 | v1.0 | v2.0 | 说明 |
|------|------|------|------|
| **OpenAI 支持** | ✅ | ✅ | 完全兼容 |
| **Anthropic 支持** | ✅ | ✅ | 完全兼容 |
| **CSV 读写** | ✅ | ✅ | 格式一致 |
| **批次 ID 生成** | ✅ | ✅ | 逻辑相同 |
| **术语表映射** | ✅ | ✅ | 功能相同 |
| **类型验证** | ❌ | ✅ | 新增：Pydantic 自动验证 |
| **配置验证** | ❌ | ✅ | 新增：启动时检查 API Key |
| **依赖注入** | ❌ | ✅ | 新增：可测试性提升 |
| **结构化日志** | ❌ | 🔜 | 计划中 |

---

## 🧪 验证迁移成功

### 测试步骤

1. **安装依赖**
   ```bash
   pip install -r requirements-v2.txt
   ```

2. **运行 v2.0**
   ```bash
   python -m memosyne.cli.mms
   ```

3. **输入相同参数**
   - 模型选择：`4`（或你常用的）
   - 输入文件：留空或你常用的路径
   - 批注：留空

4. **检查输出**
   - 输出文件应该在 `data/output/memo/` 目录
   - 文件名格式：`YYMMDDANNN.csv`（如 `251007A015.csv`）
   - CSV 内容格式与 v1.0 完全一致

### 预期结果

```
=== MMS | 术语处理工具（重构版 v2.0）===
引擎（4 = gpt-4o-mini，5 = gpt-5-mini，claude = Claude，或输入完整模型ID）：4
输入CSV路径（纯数字=按 {num}.csv；含 .csv/路径=直接使用；留空=使用 short.csv）：
起始Memo编号（整数，例：2700 表示从 M002701 开始）：2700
批注（BatchNote，可空）：测试v2
[Provider] openai
[Model   ] gpt-4o-mini (4oMini)
[Input   ] /path/to/data/input/memo/short.csv
[Start   ] Memo = 2700
[TermList] /path/to/db/term_list_v1.csv
读取到 15 个词条
加载术语表：42 条
[BatchID ] 251007A015
[Output  ] /path/to/data/output/memo/251007A015.csv
LLM Processing: 100%|███████| 15/15 [00:45<00:00]

✅ 完成：/path/to/data/output/memo/251007A015.csv
   共处理 15 个词条
```

---

## 🆘 常见问题

### Q1: 我需要重新配置 .env 吗？
**A**: 不需要。现有的 `.env` 文件完全兼容。v2.0 只是增加了可选的配置项。

### Q2: 我的旧数据还能用吗？
**A**: 能。所有数据格式（CSV、术语表）保持不变。

### Q3: v1.0 和 v2.0 可以同时使用吗？
**A**: 可以。两个版本独立运行，互不影响。

### Q4: 如果 v2.0 有问题怎么办？
**A**: 随时可以切回 v1.0：
```bash
python src/mms_pipeline/main.py  # 运行 v1.0
```

### Q5: 我需要学习新的命令吗？
**A**: 不需要。交互流程完全一致，只是运行方式变了：
```bash
# v1.0
python src/mms_pipeline/main.py

# v2.0
python -m memosyne.cli.mms
```

### Q6: 安装依赖时报错怎么办？
**A**: 确保 Python 版本 >= 3.11：
```bash
python --version  # 应该显示 3.11 或更高

# 如果版本过低，升级 Python
```

### Q7: 出现 "pydantic" 相关错误怎么办？
**A**: 重新安装依赖：
```bash
pip install --upgrade pydantic pydantic-settings
```

---

## 🎯 推荐工作流

### 渐进式迁移（推荐）

**第1周：并行使用**
- 继续使用 v1.0 处理日常任务
- 用 v2.0 处理小批量任务，验证功能

**第2周：逐步切换**
- 主要使用 v2.0
- v1.0 作为备份

**第3周：完全切换**
- 完全使用 v2.0
- 如需要，保留 v1.0 代码作为参考

---

## 🚀 v2.0 新功能

### 1. 更好的错误提示

**v1.0**:
```
读取输入失败：...（没有详细信息）
```

**v2.0**:
```
读取输入失败：...
检测到的表头：['Word', 'ZhDef']
支持的列名：word/term/headword（英文）或 中文/释义（中文）
```

### 2. 启动时配置验证

**v2.0** 会在启动时检查：
- API Key 是否存在且有效长度
- 必需的目录是否存在
- 术语表文件是否可访问

如果配置有问题，会立即报错，而不是等到调用 LLM 时才发现。

### 3. 灵活的模型选择

**v1.0**: 只支持预设的快捷方式
**v2.0**: 支持任何模型名
```
引擎：claude                    # 使用 Claude
引擎：gpt-4o                    # 使用 GPT-4o
引擎：claude-3-opus-20240229    # 使用完整模型名
```

---

## 📞 获取帮助

如果遇到问题：

1. **检查错误信息** - v2.0 提供了详细的错误提示
2. **查看日志** - 运行时的详细信息
3. **回退到 v1.0** - 随时可以切回旧版本
4. **提交 Issue** - 在代码库中报告问题

---

## 🎁 总结

- ✅ **无缝迁移** - 数据和配置完全兼容
- ✅ **向后兼容** - v1.0 仍可继续使用
- ✅ **渐进式升级** - 可以慢慢切换到 v2.0
- ✅ **更好的体验** - 错误提示更清晰，启动更快
- ✅ **未来保障** - 更易维护和扩展

**立即开始使用 v2.0 吧！** 🚀
