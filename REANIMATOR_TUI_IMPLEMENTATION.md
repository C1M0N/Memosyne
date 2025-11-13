# Reanimator TUI 实施文档

**版本**: v0.16.0
**开始日期**: 2025-11-11
**状态**: 进行中 🚧

---

## 📋 项目概览

### 目标
为 Reanimator（术语重生器）创建完整的 TUI 界面，作为独立 Tab 集成到主应用中。

### 核心功能
- **输入**: CSV 文件（word, zh_def 两列）
- **处理**: LLM 生成完整术语卡片（14 字段）
- **输出**: CSV 文件 + 术语库保存
- **工作流**: Detect → Start 两阶段（仿照 Lithoformer）

### 技术栈
- **框架**: Textual (TUI)
- **架构**: DDD + Hexagonal Architecture
- **数据库**: SQLite (config.db + stat.db)
- **并发**: asyncio + Semaphore

---

## 🗄️ 数据库设计

### config.db 新增表（2个）

#### reanimator_config
```sql
CREATE TABLE reanimator_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
```
**默认配置**:
- `reanimator_input_dir`: misc/input/reanimator
- `reanimator_output_dir`: misc/output/reanimator
- `default_model`: OpenAI::gpt-4o
- `term_list_path`: db/term_list_v1.csv
- `max_concurrent`: 3
- `max_retries`: 3

#### reanimator_feature
```sql
CREATE TABLE reanimator_feature (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
```
**功能开关**:
- `enable_concurrent`: 0 (默认关闭)

### stat.db 新增表（5个）

#### reanimator_processing_logs（处理日志）
```sql
CREATE TABLE reanimator_processing_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memo_id TEXT NOT NULL,
    wm_pair TEXT NOT NULL,
    word TEXT NOT NULL,
    zh_def TEXT NOT NULL,
    model TEXT NOT NULL,
    batch_id TEXT NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    processing_time REAL,
    has_error BOOLEAN DEFAULT 0,
    timestamp TEXT NOT NULL
)
```

#### reanimator_bank（术语库）
```sql
CREATE TABLE reanimator_bank (
    wm_pair TEXT PRIMARY KEY,        -- 词义对（唯一标识）
    memo_id TEXT NOT NULL,            -- M + 6位数字
    word TEXT NOT NULL,
    zh_def TEXT NOT NULL,
    ipa TEXT,                         -- 音标
    pos TEXT,                         -- 词性
    tag TEXT,                         -- 中文标签
    rarity TEXT,                      -- 稀有度
    en_def TEXT,                      -- 英文定义
    example TEXT,                     -- 例句
    pp_fix TEXT,                      -- 词根词缀
    pp_means TEXT,                    -- 词根含义
    batch_id TEXT,
    batch_note TEXT,
    model TEXT,
    timestamp TEXT NOT NULL
)
```

#### reanimator_terminal_logs（终端日志）
```sql
CREATE TABLE reanimator_terminal_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    log_type TEXT NOT NULL,
    logger TEXT NOT NULL,
    message TEXT
)
```

#### reanimator_prompts（Prompt 版本）
```sql
CREATE TABLE reanimator_prompts (
    section TEXT NOT NULL,
    version TEXT NOT NULL,
    content TEXT NOT NULL,
    PRIMARY KEY (section, version)
)
```
**Sections**:
- `reanimator_system`: 系统提示词
- `reanimator_user`: 用户提示词模板

#### reanimator_terms（术语表映射）
```sql
CREATE TABLE reanimator_terms (
    tag_en TEXT PRIMARY KEY,
    tag_zh TEXT NOT NULL
)
```
**数据来源**: 从 `db/term_list_v1.csv` 自动导入

---

## 📁 文件结构

### 项目目录树
```
src/memosyne/
├── shared/
│   ├── config/
│   │   └── reanimator_config.py          ✅ [已创建]
│   └── infrastructure/
│       ├── config_db.py                  ✅ [已修改]
│       ├── stats_db.py                   ✅ [已修改]
│       └── reanimator_db.py              ⬜ [待创建]
├── reanimator/
│   ├── application/
│   │   └── concurrent_use_case.py        ⬜ [待创建]
│   └── tui/
│       ├── __init__.py                   ⬜ [待创建]
│       ├── app.py                        ⬜ [待创建]
│       ├── constants.py                  ⬜ [待创建]
│       ├── logging_utils.py              ⬜ [待创建]
│       ├── widgets/
│       │   ├── __init__.py               ⬜ [待创建]
│       │   ├── screens.py                ⬜ [待创建]
│       │   ├── filters.py                ⬜ [待创建]
│       │   ├── terms_table.py            ⬜ [待创建]
│       │   ├── custom_progress.py        🔄 [迁移至 shared/tui/widgets]
│       │   ├── rate_limit_bar.py         🔄 [迁移至 shared/tui/widgets]
│       │   └── feature_toggles.py        ⬜ [待创建]
│       └── css/
│           └── reanimator_layout.tcss    ⬜ [待创建]
└── lithoformer/
    └── tui/
        └── app.py                        ⬜ [待修改 - Tab集成]
```

---

## ✅ 实施进度

### 阶段1: 数据库层 (3/3 完成) ✅

- [x] **config_db.py** - 添加 reanimator_config 和 reanimator_feature 表
  - 位置: lines 164-216
  - 完成时间: 2025-11-11
  - 状态: ✅ 已完成并测试

- [x] **stats_db.py** - 添加 5 个 reanimator 表
  - 位置: lines 143-268
  - 完成时间: 2025-11-11
  - 状态: ✅ 已完成并测试
  - 包含: processing_logs, bank, terminal_logs, prompts, terms
  - 特殊处理: CSV 自动导入 + Prompt 默认值

- [x] **reanimator_db.py** - Reanimator 数据库仓储类
  - 实际行数: 430 行
  - 完成时间: 2025-11-11
  - 状态: ✅ 已完成并测试
  - 已实现功能:
    - `save_processing_log()` - 保存处理日志
    - `save_to_bank()` - 保存到术语库（INSERT OR REPLACE 策略）
    - `get_existing_term()` - 查询已存在术语（wm_pair）
    - `check_bank_exists()` - 检查术语是否存在
    - `get_max_memo_id()` - 查询最大 Memo ID
    - `save_terminal_log()` - 保存终端日志
    - `get_term_mapping()` - 获取术语表映射
    - `get_prompts()` - 获取 Prompt 版本
    - `get_all_terms_from_bank()` - 获取所有术语
    - `clear_bank()` - 清空术语库
    - `clear_processing_logs()` - 清空处理日志
    - `get_reanimator_repository()` - 单例获取方法

### 阶段2: 配置层 (2/2 完成) ✅

- [x] **reanimator_config.py** - Reanimator 配置模型
  - 实际行数: 40 行
  - 完成时间: 2025-11-11
  - 状态: ✅ 已完成并测试
  - 已实现模型:
    - `ReanimatorFeature` - 功能开关模型（enable_concurrent）
    - `ReanimatorConfig` - 配置模型（6个配置项）
    - `ReanimatorPaths` - 路径配置模型
    - `ReanimatorConfigBundle` - 完整配置包

- [x] **reanimator_config_service.py** - Reanimator 配置服务
  - 实际行数: 260 行
  - 完成时间: 2025-11-11
  - 状态: ✅ 已完成并测试
  - 已实现方法:
    - `get_feature_flags()` - 获取功能开关
    - `update_feature_flags()` - 更新功能开关
    - `get_config()` - 获取单个配置项
    - `set_config()` - 设置单个配置项
    - `get_all_config()` - 获取所有配置
    - `update_config()` - 批量更新配置
    - `get_config_bundle()` - 获取完整配置包
    - `get_reanimator_config_service()` - 单例获取方法

### 阶段3: 应用层 (1/1 完成) ✅

- [x] **concurrent_use_case.py** - 并发处理用例
  - 实际行数: 240 行
  - 完成时间: 2025-11-11
  - 状态: ✅ 已完成并测试
  - 已实现功能:
    - `ConcurrentProcessTermsUseCase` - 并发处理类
    - 使用 `asyncio.Semaphore` 限制并发数
    - 使用 `ThreadPoolExecutor` 执行同步 LLM 调用
    - 结果按索引排序保证顺序
    - 实时更新进度和 Token 统计
    - 线程安全的 Token 累加
    - 异常处理不中断其他任务

### 阶段4: TUI 基础设施 (0/2 完成)

- [ ] **constants.py** - ASCII Logo 和常量
  - 预计行数: ~30 行
  - 内容: Reanimator ASCII Logo

- [ ] **logging_utils.py** - 日志工具
  - 预计行数: ~50 行
  - 功能: 构建 Textual Handler

### 阶段5: TUI 组件 (0/4 完成)

- [ ] **filters.py** - 输入组件库
  - 预计行数: ~300 行
  - 组件:
    - `InputPathInput` - CSV 路径输入
    - `OutputPathInput` - 输出目录
    - `OutputFilenameInput` - 输出文件名
    - `BatchNoteInput` - 批次备注
    - `ReanimatorDirectoryTree` - 文件浏览器
    - `ConfigMaxConcurrentInput` - 并发数

- [ ] **terms_table.py** - 术语结果表格
  - 预计行数: ~200 行
  - 显示列:
    - Memo ID (M000001)
    - WM Pair (word - zh_def)
    - POS (词性)
    - Tag (中文标签)

- [ ] **feature_toggles.py** - 功能开关组件
  - 预计行数: ~150 行
  - 开关:
    - 并行模式 (灰色/蓝色)

- [ ] **screens.py** - 主屏幕（核心）
  - 预计行数: ~800 行
  - 功能:
    - Detect 阶段: 检测 CSV、配置参数
    - Start 阶段: 处理术语、显示结果
    - 覆盖确认: 检测 wm_pair 冲突
    - 保存到术语库: y/n 确认流程

### 阶段6: TUI 样式 (0/1 完成)

- [ ] **reanimator_layout.tcss** - CSS 样式
  - 预计行数: ~200 行
  - 仿照: `lithoformer_layout.tcss`

### 阶段7: TUI 应用 (0/1 完成)

- [ ] **app.py** - Reanimator TUI 主应用
  - 预计行数: ~100 行
  - 功能: 应用入口、依赖注入

### 阶段8: 集成 (0/1 完成)

- [ ] **lithoformer/tui/app.py** - Tab 集成
  - 修改位置: `compose()` 方法
  - 添加内容:
    ```python
    with TabPane("Reanimator", id="tab-reanimator"):
        yield ReanimatorMainScreen()
    ```

---

## 📊 统计信息

### 代码量预估
| 类别 | 文件数 | 预计行数 |
|-----|-------|---------|
| 数据库层 | 1 | 400 |
| 配置层 | 1 | 100 |
| 应用层 | 1 | 200 |
| TUI基础 | 2 | 80 |
| TUI组件 | 4 | 1450 |
| TUI样式 | 1 | 200 |
| TUI应用 | 1 | 100 |
| 集成 | 1 | 10 |
| **总计** | **12** | **~2540** |

### 进度统计
- **已完成**: 6/12 文件 (50%)
- **进行中**: 0/12 文件 (0%)
- **待完成**: 6/12 文件 (50%)
- **实际代码量**: 970 行
  - 数据库仓储: 430 行
  - 配置模型: 40 行
  - 配置服务: 260 行
  - 并发用例: 240 行

### 关键里程碑
- [x] **M1**: 数据库层完成（数据持久化能力）✅
- [x] **M2**: 配置层完成（配置管理能力）✅
- [x] **M3**: 应用层完成（业务逻辑能力）✅
- [ ] **M4**: TUI基础完成（UI框架搭建）
- [ ] **M5**: TUI组件完成（完整UI）
- [ ] **M6**: 集成完成（功能可用）

---

## 🎯 下一步行动

### 当前优先级
1. ✅ **完成数据库表结构** - 已完成
2. ✅ **创建 reanimator_db.py** - 已完成
3. ✅ **创建配置层** - 已完成
4. ✅ **创建并发用例** - 已完成
5. 🔄 **创建 TUI 组件** - 下一步（6个文件）

### 关键决策点
- **并发实现**: 使用 asyncio.gather() + Semaphore
- **冲突检测**: 基于 wm_pair 字段
- **Memo ID 生成**: 查询数据库最大值 +1
- **术语表**: 从 CSV 导入到数据库（已实现）

---

## 🐛 已知问题

暂无

---

## 📝 技术笔记

### Memo ID 自动生成逻辑
```python
# 保存到 Bank 时：
1. 查询 reanimator_bank 是否存在相同 wm_pair
2. 如果不存在 → 查询数据库最大 memo_id + 1
3. 如果存在 → 保持原 memo_id（或询问是否覆盖）
```

### 覆盖确认流程
```python
# 仿照 Lithoformer v0.15.2：
1. 处理完成后，遍历所有术语检查 wm_pair 是否存在
2. 收集所有冲突 → 显示对比列表
3. 询问"是否全部覆盖？(y/n)"
4. y → 批量覆盖，n → 跳过保存
```

### 术语表数据库化
```python
# 初始化时从 CSV 导入：
1. 读取 db/term_list_v1.csv
2. 插入到 reanimator_terms 表
3. TermListAdapter 改为查询数据库
```

---

## 🔗 相关文件

### 参考实现
- `src/memosyne/lithoformer/tui/widgets/screens.py` - TUI 主屏幕参考
- `src/memosyne/lithoformer/tui/widgets/filters.py` - 输入组件参考
- `src/memosyne/lithoformer/tui/widgets/questions_table.py` - 表格组件参考
- `src/memosyne/lithoformer/tui/widgets/feature_toggles.py` - 开关组件参考

### 业务逻辑
- `src/memosyne/reanimator/application/use_cases.py` - 现有处理逻辑
- `src/memosyne/reanimator/domain/services.py` - 业务规则
- `src/memosyne/reanimator/infrastructure/prompts.py` - LLM Prompts

---

**最后更新**: 2025-11-11 (阶段1-3完成，进度50%)
**更新人**: Claude Code
**当前里程碑**: M3 应用层 ✅ (数据库 + 配置 + 业务逻辑)
