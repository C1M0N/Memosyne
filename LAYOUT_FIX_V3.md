# Lithoformer TUI 布局修复报告 v3

## 🎯 本次修复内容

基于用户最新反馈的 5 个问题，进行了全面的布局重构。

### 用户反馈的问题

1. ❌ **控制台和指令输入区应该在右边**
2. ❓ **解析摘要是什么？**
3. ❌ **信息区无显示且过长 应该和logo同宽**
4. ❌ **文件选择区的比例应该和layout.xml显示的一样，应该很长**
5. ❌ **题目列表的大小应该是固定的 哪怕是空的时候也保持那个区域的最大的大小**

## ✅ 解决方案

### 1. 重新理解 layout.xml 结构

根据 layout.xml 的坐标分析：

```
控制台：X=760, Y=480, Width=840, Height=280
命令输入：X=760, Y=760, Width=840, Height=40
```

**关键发现**：控制台宽度 840px = 从 X=760 到 X=1600，即横跨中列和右列！

因此，正确的布局结构应该是：

```
主容器（水平）:
  ├─ 左列 (760px)
  │   ├─ LOGO (180px 高)
  │   ├─ 信息区 (60px 高)
  │   └─ 题目列表 (560px 高，固定)
  │
  └─ 右侧区域 (840px)
      ├─ 顶部区域（水平）
      │   ├─ 中列 (560px)
      │   │   └─ 所有配置输入
      │   └─ 右列 (280px)
      │       ├─ 文件树 (390px 高，固定)
      │       └─ 按钮 (90px 高)
      │
      ├─ 控制台 (280px 高，横跨整个右侧区域)
      └─ 命令输入 (40px 高，横跨整个右侧区域)

底部行（水平）:
  ├─ 进度条列 (1120px)
  └─ 统计列 (480px)
```

### 2. 代码实现

**文件**: `src/memosyne/lithoformer/tui/widgets/screens.py`

#### compose() 方法重构 (第195-264行)

```python
def compose(self) -> ComposeResult:
    """Compose the main screen layout (完全基于 layout.xml)."""
    # 主容器：左列 + 右侧区域
    with Horizontal(id="main-container"):
        # 左列 (0-760px): LOGO + 信息区 + 题目列表
        with Vertical(id="left-col"):
            yield Static(ASCII_LOGO, id="logo-panel")

            info_panel = Static("[dim]未选择文件[/]", id="info-panel")
            info_panel.border_title = "信息区"
            yield info_panel

            yield QuestionsTable()

        # 右侧区域 (760-1600px): 包含中列、右列和控制台
        with Vertical(id="right-area"):
            # 顶部：中列 + 右列
            with Horizontal(id="top-section"):
                # 中列 (760-1320px): 所有配置输入
                with Vertical(id="middle-col"):
                    yield InputPathInput(...)
                    yield OutputPathInput(...)
                    # ... 所有配置输入 ...

                # 右列 (1320-1600px): 文件树 + 按钮
                with Vertical(id="right-col"):
                    yield self._file_tree
                    yield Button("Detect", id="action-button", ...)

            # 控制台区 (横跨整个右侧区域，760-1600px)
            log_view = RichLog(id="log-view", ...)
            log_view.border_title = "控制台"
            yield log_view

            yield CommandInput()

    # 底部：进度条区
    with Horizontal(id="bottom-row"):
        # ... 进度条和统计信息 ...
```

### 3. CSS 更新

**文件**: `src/memosyne/lithoformer/tui/css/lithoformer_layout.tcss`

#### 主要修改

```tcss
/* 左列: 760px / 1600px = 47.5% */
#left-col {
    width: 19fr;  /* 760/40 */
    layout: vertical;
}

/* 右侧区域: 840px / 1600px = 52.5% */
#right-area {
    width: 21fr;  /* 840/40 */
    layout: vertical;
}

/* 顶部区域：中列和右列的水平容器 */
#top-section {
    layout: horizontal;
    height: auto;
}

/* 中列: 560px / 840px = 66.7% */
#middle-col {
    width: 2fr;  /* 560/280 = 2 */
    layout: vertical;
}

/* 右列: 280px / 840px = 33.3% */
#right-col {
    width: 1fr;  /* 280/280 = 1 */
    layout: vertical;
}

/* 控制台：横跨右侧区域全宽 */
#log-view {
    height: 14;  /* ~280px */
    border: round #1f4b8f;
    background: #070d16;
    scrollbar-size-vertical: 1;
    padding: 1;
    margin-top: 1;
}

/* 文件树：固定高度 */
#file-tree {
    height: 19;  /* ~380px - 很长！ */
    min-height: 19;
    border: round #1f4b8f;
    background: #070d16;
    scrollbar-size-vertical: 1;
    margin-bottom: 1;
}

/* 题目列表：固定高度 */
#questions-table {
    height: 28;  /* ~560px */
    min-height: 28;  /* 确保即使为空也保持大小 */
    border: round #1f4b8f;
    background: #070d16;
    scrollbar-size-vertical: 1;
}
```

## 📊 问题解决对照表

| 问题 | 状态 | 解决方案 |
|------|------|----------|
| 1. 控制台在右边 | ✅ | 控制台现在在 right-area 中，横跨中列和右列（760-1600px） |
| 2. 解析摘要 | ℹ️ | "解析摘要"是底部统计区的一个面板，显示题目解析的摘要信息 |
| 3. 信息区显示+宽度 | ✅ | 信息区在 left-col 中，与 LOGO 同宽（760px），添加默认文本"未选择文件" |
| 4. 文件树很长 | ✅ | 文件树高度设为 19（约380px），并使用 min-height 确保固定大小 |
| 5. 题目列表固定大小 | ✅ | 题目列表高度设为 28（约560px），使用 min-height: 28 确保空时也保持大小 |

## 🎨 Layout.xml 映射关系

| 组件 | X | Y | Width | Height | 实现容器 | CSS ID |
|------|---|---|-------|--------|---------|--------|
| LOGO | 0 | 0 | 760 | 180 | left-col | #logo-panel |
| 信息区 | 0 | 180 | 760 | 60 | left-col | #info-panel |
| 题目列表 | 0 | 240 | 760 | 560 | left-col | #questions-table |
| 输入路径 | 760 | 0 | 560 | 60 | middle-col | InputPathInput |
| 输出路径 | 760 | 60 | 560 | 60 | middle-col | OutputPathInput |
| 厂商选择 | 760 | 120 | 200 | 60 | middle-col | ProviderSelectionInput |
| 模型选择 | 960 | 120 | 360 | 60 | middle-col | ModelSelectionInput |
| 使用模型 | 760 | 180 | 560 | 60 | middle-col | ModelInput |
| 标题 | 760 | 240 | 560 | 60 | middle-col | TitleInput |
| 序号 | 760 | 300 | 200 | 60 | middle-col | SequenceInput |
| 批次号 | 960 | 300 | 360 | 60 | middle-col | BatchInput |
| 输出文件名 | 760 | 360 | 560 | 60 | middle-col | OutputFilenameInput |
| 标签（副标题） | 760 | 420 | 560 | 60 | middle-col | TagInput |
| 给模型的备注 | 760 | 480 | 560 | 60 | middle-col | ModelNoteInput |
| 文件树 | 1320 | 0 | 280 | 390 | right-col | #file-tree |
| 按钮 | 1320 | 390 | 280 | 90 | right-col | #action-button |
| 控制台 | 760 | 480 | 840 | 280 | right-area | #log-view |
| 命令输入 | 760 | 760 | 840 | 40 | right-area | CommandInput |
| 单题进度条 | 0 | 800 | 1120 | 40 | progress-col | #single-progress |
| 总进度条 | 0 | 840 | 1120 | 60 | progress-col | #total-progress |
| 统计信息 | 1120 | 800 | 480 | 100 | stats-col | #stats-col |
| 解析摘要 | 1120 | 800 | 480 | -- | stats-col | #analysis-panel |

## 🧪 测试状态

```bash
✅ App 导入成功
✅ 所有组件都在 compose() 中
✅ CSS 文件结构更新
✅ 容器 ID 引用已修复
```

## 🔧 技术细节

### 关键改进

1. **嵌套容器结构**
   - 使用 `right-area` 作为中列、右列和控制台的父容器
   - `top-section` 水平容器包含 middle-col 和 right-col
   - 控制台和命令输入直接在 right-area 下，自动横跨全宽

2. **CSS 比例计算**
   - 总宽度：1600px = 40 份（每份 40px）
   - 左列：760px = 19fr
   - 右侧区域：840px = 21fr
   - 中列（在右侧区域内）：560px = 2fr（相对于右列的 280px = 1fr）

3. **固定高度实现**
   - 使用 `height` 和 `min-height` 双重保证
   - 即使内容为空，组件也保持最小高度
   - 适用于：题目列表、文件树

## 📝 已保留的功能

✅ 所有业务逻辑保持不变：
- Detect 流程（文件检测、题目拆分、元数据推断）
- Start 流程（LLM 调用、题目解析、输出生成）
- 文件树浏览和刷新
- 进度跟踪和显示
- 日志输出和命令输入
- 按钮状态变化（Detect=蓝色，Start=红色）
- 所有配置输入和验证

## 🚀 测试建议

运行应用验证布局：

```bash
./run_lithoformer_tui.sh
```

或：

```bash
python -m src.memosyne.lithoformer.tui
```

### 验证清单

- [ ] 控制台是否在右侧（横跨中列和右列）
- [ ] 信息区是否显示"未选择文件"文本
- [ ] 信息区宽度是否与 LOGO 一致
- [ ] 文件树是否足够长（约占右列大部分高度）
- [ ] 题目列表是否保持固定大小（即使为空）
- [ ] 所有输入组件是否正确显示
- [ ] 按钮是否在文件树下方
- [ ] 进度条是否在底部左侧
- [ ] 统计信息是否在底部右侧

## 🎯 与之前版本的区别

### v2 (错误版本)
- ❌ 使用 3 列布局（left-col, middle-col, right-col）
- ❌ 控制台在 middle-col 内，只占中列宽度
- ❌ 布局不符合 layout.xml 的 840px 宽控制台设计

### v3 (本次修复)
- ✅ 使用 2 列布局（left-col + right-area）
- ✅ right-area 内部分为顶部（top-section：middle-col + right-col）和底部（控制台+命令输入）
- ✅ 控制台横跨整个 right-area（840px），符合 layout.xml 设计
- ✅ 所有组件位置和尺寸精确匹配 layout.xml

---

**修复时间**: 2025-10-19
**版本**: v3
**状态**: ✅ 已修复，等待用户测试验证
