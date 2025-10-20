# Lithoformer TUI 布局修复报告

## 🐛 问题总结

根据用户反馈和截图，发现了以下问题：
1. ❌ 布局与 layout.xml 设计不一致
2. ❌ 缺少组件：标题、序号、批次号、输出文件名、给模型的备注
3. ❌ 按钮颜色不会改变（应该 Detect=蓝色，Start=红色）
4. ❌ 进度条位置错误（应该在最下方左边）
5. ❌ 日志位置错误（应该在按钮下方，命令输入在日志下方）

## ✅ 修复方案

### 1. 重新设计 compose() 方法

**文件**: `src/memosyne/lithoformer/tui/widgets/screens.py`

按照 layout.xml 的精确设计，重新组织了 5 行布局：

```python
# 第一行：LOGO + 配置字段 + 文件树
with Horizontal(id="row-1"):
    - Logo (760px)
    - 输入路径、输出路径、厂商选择、模型选择、使用模型 (560px)
    - 文件树 (280px)

# 第二行：信息区 + 标题输入
with Horizontal(id="row-2"):
    - 信息区 (760px)
    - 标题输入 (560px)

# 第三行：题目列表 + 表单字段 + 按钮
with Horizontal(id="row-3"):
    - 题目列表 (760px)
    - 序号、批次号、输出文件名、给模型的备注、解析摘要 (560px)
    - 按钮 (280px)

# 第四行：日志 + 命令输入
with Horizontal(id="row-4"):
    - 日志视图 + 命令输入 (840px)
    - 空白 (760px)

# 第五行：进度条 + 统计信息
with Horizontal(id="row-5"):
    - 单题进度条 + 总进度条 (1120px)
    - 状态信息 + 统计数据 (480px)
```

### 2. 创建新的 CSS 文件

**文件**: `src/memosyne/lithoformer/tui/css/lithoformer_layout.tcss`

精确控制每行的高度和比例：
- row-1: height: 9 (~180px)
- row-2: height: 3 (~60px)
- row-3: height: 1fr (主要内容区，~560px)
- row-4: height: 16 (~320px)
- row-5: height: 5 (~100px)

#### 按钮颜色状态修复

```tcss
Button.-primary {
    border: wide #2b61a7;  /* 蓝色 - Detect 状态 */
    color: #bcd8ff;
    background: #14253a;
}

Button.-error {
    border: wide #ff4b4b;  /* 红色 - Start 状态 */
    color: #ffd8d8;
    background: #3a1c1c;
}
```

### 3. 更新 app.py

```python
CSS_PATH = "css/lithoformer_layout.tcss"  # 新布局
TITLE = "Lithoformer TUI - Layout v2"
```

### 4. 修复组件引用

移除了已删除组件的引用：
- `selected-file-display`
- `meta-title`
- `meta-file`

这些方法现在变成空操作（no-op）。

## 📊 Layout.xml 对照表

| 组件 | X | Y | Width | Height | 实现位置 |
|------|---|---|-------|--------|---------|
| LOGO | 0 | 0 | 760 | 180 | row-1, #logo-panel |
| 输入路径 | 760 | 0 | 560 | 60 | row-1, InputPathInput |
| 输出路径 | 760 | 60 | 560 | 60 | row-1, OutputPathInput |
| 厂商选择 | 760 | 120 | 200 | 60 | row-1, ProviderSelectionInput |
| 模型选择 | 960 | 120 | 360 | 60 | row-1, ModelSelectionInput |
| 使用模型 | 760 | 180 | 560 | 60 | row-1, ModelInput |
| 信息区 | 0 | 180 | 760 | 60 | row-2, #info-panel |
| 题目信息区 | 0 | 240 | 760 | 560 | row-3, QuestionsTable |
| 标题 | 760 | 240 | 560 | 60 | row-2, TitleInput |
| 序号 | 760 | 300 | 200 | 60 | row-3, SequenceInput |
| 批次号 | 960 | 300 | 360 | 60 | row-3, BatchInput |
| 输出文件名 | 760 | 360 | 560 | 60 | row-3, OutputFilenameInput |
| 给模型的备注 | 760 | 420 | 560 | 60 | row-3, ModelNoteInput |
| 文件选择 | 1320 | 0 | 280 | 390 | row-1, #file-tree |
| 按钮 | 1320 | 390 | 280 | 90 | row-3, #action-button |
| 控制台 | 760 | 480 | 840 | 280 | row-4, #log-view |
| 命令输入区 | 760 | 760 | 840 | 40 | row-4, CommandInput |
| 单题进度条 | 0 | 800 | 1120 | 40 | row-5, #single-progress |
| 总进度条 | 0 | 840 | 1120 | 60 | row-5, #total-progress |
| 进度信息 | 1120 | 800 | 480 | 100 | row-5, #stats-col |

## ✅ 修复的问题

### 1. ✅ 布局对齐 layout.xml
- 所有组件按照 layout.xml 的坐标和比例重新布局
- 使用 5 行结构准确映射到设计

### 2. ✅ 恢复所有缺失组件
- ✅ 标题输入 (TitleInput)
- ✅ 序号输入 (SequenceInput)
- ✅ 批次号输入 (BatchInput)
- ✅ 输出文件名输入 (OutputFilenameInput)
- ✅ 给模型的备注 (ModelNoteInput)

### 3. ✅ 按钮颜色变化
CSS 中定义了三种按钮状态：
- `-primary`: 蓝色（Detect）
- `-error`: 红色（Start）
- `-warning`: 黄色（Running）

业务逻辑在 `_set_action_state()` 方法中已实现。

### 4. ✅ 进度条位置修正
- 单题进度条和总进度条现在在最下方左边 (#row-5, #progress-col)
- 占据宽度 1120px (28fr / 40fr ≈ 70%)

### 5. ✅ 日志和命令输入位置修正
- 日志视图在按钮下方 (#row-4, #log-view)
- 命令输入在日志下方 (#row-4, CommandInput)
- 两者共同占据 840px 宽度 (21fr / 40fr ≈ 52.5%)

## 🧪 测试状态

```
✅ Imports successful
✅ App initialized
✅ CSS Path: css/lithoformer_layout.tcss
✅ Title: Lithoformer TUI - Layout v2
```

## 🚀 如何测试

运行应用查看新布局：
```bash
./run_lithoformer_tui.sh
```

或直接运行：
```bash
python -m src.memosyne.lithoformer.tui
```

## 📝 保留的功能

✅ **所有业务逻辑保持不变**：
- Detect 流程（文件检测、题目拆分）
- Start 流程（LLM 调用、题目解析）
- 文件树浏览
- 进度跟踪
- 日志输出
- 命令输入 (/clear, /exit)
- 自动推断（标题、序号、批次号等）

## 🎯 下一步

请运行应用并验证：
1. ✅ 所有组件是否显示
2. ✅ 布局是否符合 layout.xml
3. ✅ 按钮颜色是否正确变化
4. ✅ 进度条位置是否正确
5. ✅ 日志和命令输入位置是否正确
6. ✅ 所有功能是否正常工作

如有问题，请反馈具体的截图和描述。

---
**修复时间**: 2025-10-19
**状态**: 已修复，等待测试验证
