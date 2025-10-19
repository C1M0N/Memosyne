# Lithoformer TUI 布局结构图

## 整体布局 (1600×900)

```
┌────────────────────────────────────────────────────────────────────────┐
│ #main-container (Horizontal)                                          │
├─────────────────────────┬──────────────────────────────────────────────┤
│  #left-col (760px)      │  #right-area (840px)                         │
│  ┌───────────────────┐  │  ┌────────────────────────────────────────┐  │
│  │ LOGO              │  │  │ #top-section (Horizontal)              │  │
│  │ (180px 高)        │  │  ├─────────────────┬──────────────────────┤  │
│  └───────────────────┘  │  │ #middle-col     │ #right-col           │  │
│  ┌───────────────────┐  │  │ (560px)         │ (280px)              │  │
│  │ 信息区            │  │  │                 │                      │  │
│  │ (60px 高)         │  │  │ 输入路径        │ ┌──────────────────┐ │  │
│  └───────────────────┘  │  │ 输出路径        │ │                  │ │  │
│  ┌───────────────────┐  │  │ 厂商选择+模型   │ │                  │ │  │
│  │                   │  │  │ 使用模型        │ │   文件树         │ │  │
│  │                   │  │  │ 标题            │ │   (390px 高)     │ │  │
│  │   题目列表        │  │  │ 序号+批次号     │ │                  │ │  │
│  │   (560px 高)      │  │  │ 输出文件名      │ │                  │ │  │
│  │   [固定大小]      │  │  │ 标签(副标题)    │ │                  │ │  │
│  │                   │  │  │ 给模型的备注    │ └──────────────────┘ │  │
│  │                   │  │  │                 │ ┌──────────────────┐ │  │
│  │                   │  │  │                 │ │   Detect 按钮    │ │  │
│  └───────────────────┘  │  │                 │ │   (90px 高)      │ │  │
│                         │  │                 │ └──────────────────┘ │  │
│                         │  └─────────────────┴──────────────────────┘  │
│                         │  ┌────────────────────────────────────────┐  │
│                         │  │ 控制台 (横跨整个 right-area 840px)     │  │
│                         │  │ (280px 高)                             │  │
│                         │  └────────────────────────────────────────┘  │
│                         │  ┌────────────────────────────────────────┐  │
│                         │  │ 命令输入 (横跨整个 right-area 840px)   │  │
│                         │  │ (40px 高)                              │  │
│                         │  └────────────────────────────────────────┘  │
└─────────────────────────┴──────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────────────────────┐
│ #bottom-row (Horizontal)                                               │
├────────────────────────────────────┬───────────────────────────────────┤
│  #progress-col (1120px)            │  #stats-col (480px)               │
│  ┌──────────────────────────────┐  │  ┌─────────────────────────────┐  │
│  │ 单题进度条 (40px 高)         │  │  │ 状态信息                    │  │
│  └──────────────────────────────┘  │  ├─────────────────────────────┤  │
│  ┌──────────────────────────────┐  │  │ 统计数据                    │  │
│  │ 总进度条 (60px 高)           │  │  ├─────────────────────────────┤  │
│  └──────────────────────────────┘  │  │ 解析摘要                    │  │
│                                    │  └─────────────────────────────┘  │
└────────────────────────────────────┴───────────────────────────────────┘
```

## 关键理解

### 1. 两级嵌套结构

```
main-container (水平)
├─ left-col (垂直)
│   ├─ LOGO
│   ├─ 信息区
│   └─ 题目列表
└─ right-area (垂直) ← 这是关键！
    ├─ top-section (水平)
    │   ├─ middle-col (垂直)
    │   │   └─ 所有配置输入
    │   └─ right-col (垂直)
    │       ├─ 文件树
    │       └─ 按钮
    ├─ 控制台 (横跨 right-area 全宽)
    └─ 命令输入 (横跨 right-area 全宽)
```

### 2. 为什么需要 right-area？

根据 layout.xml：
- 控制台：X=760, Width=840 → 从 760px 到 1600px（横跨中列+右列）
- 命令输入：X=760, Width=840 → 从 760px 到 1600px（横跨中列+右列）

如果使用简单的 3 列布局，控制台无法横跨两列。因此：
- **right-area** 作为容器，宽度 840px
- 控制台在 right-area 内，自动占据全宽 840px ✅

### 3. 宽度比例计算

#### 主容器级别（1600px 总宽）
```
left-col:   760px / 1600px = 19/40 = 19fr
right-area: 840px / 1600px = 21/40 = 21fr
```

#### top-section 级别（840px 总宽，right-area 内部）
```
middle-col: 560px / 840px = 560/280 = 2fr
right-col:  280px / 840px = 280/280 = 1fr
```

## 代码结构对应

```python
# screens.py - compose() 方法

with Horizontal(id="main-container"):              # 主容器

    with Vertical(id="left-col"):                  # 左列 760px
        yield Static(ASCII_LOGO)                   #   - LOGO
        yield Static("...", id="info-panel")       #   - 信息区
        yield QuestionsTable()                     #   - 题目列表

    with Vertical(id="right-area"):                # 右侧区域 840px ← 关键！

        with Horizontal(id="top-section"):         # 顶部区域

            with Vertical(id="middle-col"):        #   中列 560px
                yield InputPathInput()             #     所有配置输入
                yield OutputPathInput()
                # ... 更多输入 ...

            with Vertical(id="right-col"):         #   右列 280px
                yield DirectoryTree()              #     文件树
                yield Button("Detect")             #     按钮

        yield RichLog(id="log-view")               # 控制台（全宽 840px）
        yield CommandInput()                        # 命令输入（全宽 840px）

with Horizontal(id="bottom-row"):                  # 底部行
    with Vertical(id="progress-col"):              #   进度条列 1120px
        yield ProgressBar(id="single-progress")
        yield ProgressBar(id="total-progress")

    with Vertical(id="stats-col"):                 #   统计列 480px
        yield Static("状态：待机")
        yield Static("完成：0/0 | ...")
        yield Static("...", id="analysis-panel")   #   解析摘要
```

## CSS 对应

```tcss
/* 主容器分割 */
#main-container { layout: horizontal; }

#left-col    { width: 19fr; }  /* 760/40 = 19 */
#right-area  { width: 21fr; }  /* 840/40 = 21 */

/* right-area 内部分割 */
#right-area      { layout: vertical; }
#top-section     { layout: horizontal; }

#middle-col { width: 2fr; }    /* 560/280 = 2 */
#right-col  { width: 1fr; }    /* 280/280 = 1 */

/* 控制台和命令输入（在 right-area 内，自动全宽） */
#log-view       { height: 14; }  /* 280px */
#command-input  { height: 2; }   /* 40px */

/* 固定高度组件 */
#questions-table {
    height: 28;        /* 560px */
    min-height: 28;    /* 确保空时也保持大小 */
}

#file-tree {
    height: 19;        /* 380px */
    min-height: 19;    /* 确保很长 */
}
```

## 与 layout.xml 的精确对应

| Layout.xml 坐标 | 组件 | 代码容器 | CSS ID |
|----------------|------|---------|--------|
| (0, 0, 760, 180) | LOGO | left-col | #logo-panel |
| (0, 180, 760, 60) | 信息区 | left-col | #info-panel |
| (0, 240, 760, 560) | 题目列表 | left-col | #questions-table |
| (760, 0-480, 560, 480) | 配置输入 | middle-col | 各种 Input |
| (1320, 0, 280, 390) | 文件树 | right-col | #file-tree |
| (1320, 390, 280, 90) | 按钮 | right-col | #action-button |
| (760, 480, 840, 280) | 控制台 | right-area | #log-view |
| (760, 760, 840, 40) | 命令输入 | right-area | CommandInput |
| (0, 800, 1120, 100) | 进度条 | progress-col | #single/total-progress |
| (1120, 800, 480, 100) | 统计 | stats-col | #stats-col |

---

**关键点**：right-area 是理解整个布局的核心！它让控制台能够横跨 840px 宽度。
