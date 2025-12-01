# Reanimator/Lithoformer Symmetry Plan

> Living checklist tracking the full architecture realignment. Update this file as tasks move between phases.

## Phase 1 – Shared Foundations ✅
- [x] Context-aware `SQLiteAppConfigService` (per-domain config/feature tables, shared provider/tier API)
- [x] `db/library.db` + `reanimator_fieldterms` seeded from `db/term_list_v1.csv`
- [x] `stat.db` tables rebuilt for Reanimator (processing logs, bank, prompts, terminal logs)
- [x] Prompt storage uses numeric versions (`0001`, `0002`, …) for both domains

## Phase 2 – Domain & Application Alignment (in progress)
- [x] Replace legacy Reanimator domain models with `WordEn/MeanZh` schema (15-column IO)
- [x] Dynamic prompt assembly (LLM only fills missing optional fields, like Lithoformer)
- [x] Shared BatchID/output filename utilities; WordId derived from numeric file names
- [x] Reanimator CSV adapter reads/writes new headers; CLI/API kept only until removal phase
- [x] Remove `TermListRepo` dependency; use `library.db` field terms everywhere
- [x] Bank/processing logs write through `SQLiteStatsRepository` helpers

- [x] Reanimator TUI adopts Lithoformer layout widgets（左列 LOGO+切换 + TermsTable+RateLimitBar；右列 Input/Config Tabs、文件树、RichLog、CustomProgressBar；无预览 Tab）
- [x] Reanimator 输入 Tab 增加 Provider / Model 选择器，与 Lithoformer 同步（可读、自动填值、禁手动序号）
- [x] RateLimitManager / CustomProgressBar 抽到 shared 并在两个 TUIs 接入
- [x] Lithoformer 序号输入锁定 + Reanimator 继续自动派号（仅文件名控制）
- [x] Command palette parity（`/clear`、`/bank`、`/yes`、`/no` 均可用）
- [x] Reanimator Screen 直接继承 Textual `Screen` 并复制 Lithoformer 布局/按钮样式，消除了额外空行
- [x] Feature toggles 组件回归各自子域（Lithoformer 保留三开关，Reanimator 仅并行）
- [x] 数据库日志 handler / 命令交互完全对齐（含 `/bank` 详情展示、日志缓冲）
- [x] 输入路径 / 配置字段变更实时反馈与目录刷新与 Lithoformer 保持一致
- [x] Lithoformer/Reanimator sequence/word 起始号输入锁定（只读，来自文件名）
- [x] Command palette parity（`/clear`、`/bank`、`/yes`、`/no` 等命令在两个 TUIs 行为一致）
- [x] Remove CLI scripts + `memosyne.api`; README/AGENTS/CHANGELOG updated accordingly


## Phase 4 – Cleanup & Verification
- [ ] Migrate existing `stat.db` data to new schema (scripts/migration doc)
- [ ] Add smoke tests (unit or e2e) covering both flows
- [ ] Final doc sweep: README symmetry table, AGENTS common workflow, CHANGELOG entry
