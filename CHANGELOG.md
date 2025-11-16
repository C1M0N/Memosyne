# Changelog

All notable changes to this project are recorded here. Detailed iteration notes for the Lithoformer TUI live in `TUI_design_note/` and have been distilled into the entries below.

## [Unreleased]

### Changed
- Lithoformer LLM 适配器默认使用动态生成的 system prompt 与 JSON Schema；移除了 `LITHOFORMER_SYSTEM_PROMPT` / `QUESTION_SCHEMA` 常量，统一调用动态构建器。
- Lithoformer 只保留 MCQ / CLOZE 题型：彻底移除 ORDER 相关字段与逻辑，提示词升级为通用考试场景并强调零幻觉输出。
- 选择题选项扩展为 A-Z，Schema / 域模型 / Formatter 支持任意数量的字母选项，并要求解析（distractors）覆盖全部错误选项。
- 更新 Lithoformer system prompt：全英文输出，并要求解析中的每个专业术语在中文后加上英文原词括号，便于考试记忆；翻译段落同步使用英文说明。
- 解析术语标注格式升级为 `((中文术语::[English original]))`，示例及指令全面更新，仅对首次出现的专业词汇注释，并限制干扰项说明只覆盖实际存在的选项。
- 单题 LLM 调用增加 5 分钟超时保护，超时会自动消耗一次 `max_retries` 发起重试，避免长时间卡死。
- 新增 `lithoformer_prompts` 表（存储 prompt 版本），提示词改为从 `stat.db` 动态加载，可按版本迭代。
- `lithoformer_terminal_logs` 表新增 `logger` 列，持久化原始 logger 名称并在写入时剥离时间戳/级别前缀，同时屏蔽 httpx 内部噪声日志。
- 移除遗留 CLI 层与 `memosyne.api`：删除 `src/memosyne/*/cli/`、`scripts/run_reanimate.sh`、`scripts/LfC.sh` 与 `api.py`，仅保留 Textual TUI（`./scripts/RaT.sh`、`./scripts/LfT.sh`）。README / AGENTS 重写以反映新的入口。
- Reanimator TUI 与 Lithoformer 对齐：新增数据库日志 handler、命令面板 `/clear`/`/bank`/`/yes`/`/no`、输入/配置字段即时校验、自动重建目录树与序号预览，并共用 RateLimitBar + CustomProgressBar 实现。
- Reanimator Start 阶段强制关闭 `tqdm` 进度条（只使用 Textual 更新），修复 macOS 3.13 `bad value(s) in fds_to_keep` 崩溃。
- 移除 tqdm 依赖：`Progress` 工具成为轻量级占位实现，`requirements.txt` 不再需要 tqdm。
- Reanimator `LLMResponse` / `TermOutput` 对齐 Lithoformer：missing 字段自动补空，输出阶段校验 `DefEn/Example/IPA/POS` 等必填列；当 CSV 自带字段时跳过 LLM prompt 但仍保证最终输出完整，并在缺失时给出友好提示。

### Fixed
- Propagated TUI-detected `question_number` values into sequential/concurrent Lithoformer pipelines (stats + bank writes) with index-based fallback, and trimmed stored `batch_id` to the leading segment (e.g. `251030E006`).
- Normalised character counting in concurrent saves so input/output lengths match the sequential pipeline (context/question/answer only, JSON formatting excluded).

## [v0.12.0a] - 2025-10-24

### Changed
- Consolidated all parameters into SQLite `config` table; feature flags moved to single-row `feature` table (auto-migrated from `feature_config`).
- Removed `processing_stats` from `config.db` (stats live in `stat.db`).
- Introduced `AppConfigService` (SQLite-backed) exposing typed models: `FeatureFlags`, `RuntimeTuning`, `AppConfigBundle`, `LithoformerPaths`.
- TUI “配置/功能” tabs now read/write via `AppConfigService`; default model is persisted only from the “配置” tab (model dropdown does not persist).
- Unified concurrent/sequential pipelines behind a single async event interface: `ConcurrentParseQuizUseCase.stream_async()`; TUI consumes events to update rows/progress/tokens.
- Added `UseCaseFactory` to assemble provider/adapter/use case in the Application layer; UI 入口（当时包含 CLI）复用该工厂。
- UI 入口（当时 CLI + TUI）读取 `AppConfigService` 默认路径/旗标/调优配置，支持并发模式并按题目流式输出进度。
- Settings refactor: only API keys (and temp) remain from `.env`; default dirs and model now resolved via `AppConfigService` with sample-dir safeguards.

### Fixed
- Model switching in TUI updates Detection snapshot (provider/model_code) and recomputes output filename immediately.

### Notes
- This release focuses on DDD + Hexagonal alignment: UI is thin, Application owns orchestration, Infrastructure centralizes persistence. Backward compatibility for old feature table is dropped in favor of auto-migration on startup.

## [v0.10.5a] - 2025-10-21

### Added
- `CustomProgressBar` widget in the Lithoformer TUI with adaptive width, runtime/remaining time/tokens telemetry, and a floating percentage indicator.

### Changed
- Rebalanced middle-column spacing and right-column alignment to match `layout.xml` exactly; Select widgets now inherit the JiraTUI focus/arrow styling.
- Command input height increased for readability and component labels simplified to avoid redundant subtitles.
- Incorporated fixes from `LAYOUT_FIX_v4`–`LAYOUT_FIX_v6`: sequence/batch inputs share a row, Detect/Start button stays beneath the file tree, component gaps reduced so “备注”与“输出文件名”字段不再被挤出视图, and Select dropdown arrows regain JiraTUI contrast.
- Consolidated helper shell scripts into `scripts/` (`run_reanimate.sh`, `LfC.sh`, `LfT.sh`) and updated documentation references.
- Moved the reference `layout.xml` blueprint into `misc/layout.xml` to keep the project root tidy.
- Renamed the TUI “标签”字段为 `NoteInput` 并改为非必填，保持备注可选同时沿用 LLM 提示附加逻辑。
- Questions table now displays canonical `L` 题号 derived from the sequence seed, and the preview选项卡会同步展示该题的完整 Markdown 原文。
- Introduced `config/paths.json` and `misc/` sample directories; TUI 会在检测到只读样例时提示用户选择真实的输入/输出目录。

### Fixed
- Batch ID input now shares the row with sequence as designed; Detect/Start button remains anchored below the directory tree.
- Model selection dropdown keeps the chosen value visible and prevents provider refresh events from clearing options.
- Rich log panel explicitly titled “控制台”, addressing the missing heading reported in v5 feedback.

## [v0.10.4] - 2025-10-20

### Added
- Dedicated `lithoformer_layout.tcss` stylesheet implementing the three-column JiraTUI-inspired layout described in `layout.xml`.
- Logging utilities integrated with Textual `RichLog` and the command channel, supporting `/clear` and `/exit`.
- `logging_utils.py` Textual handler wiring standard logging to the TUI log pane while keeping command input responsive.

### Changed
- Detect → Start button flow refined with explicit action states, asynchronous task coordination, and automatic progress bar resets.
- Questions table pinned to a fixed footprint with sorting disabled; command input anchored beneath the log view.
- Archived the experimental `lithoformer_v2.tcss` / `screens_v2.py` spike after migrating the working grid ideas into the production layout sheet.

## [v0.10.3] - 2025-10-19

### Added
- `MainScreen.compose()` rewritten to follow the 760 / 560 / 280 layout proportions while keeping every widget independent (no container wrapping).
- Provider/model selection widgets rebuilt with search, manual override detection, and the metadata auto-fill pipeline (titles, sequence, batch ID, output filename).
- Detection stage now captures full `DetectionResult` snapshots including Markdown blocks, inferred titles, and ShouldBe filename preview.

### Changed
- CSS system refactored to the JiraTUI round-border palette; application banner updated to “Lithoformer TUI - Layout v2”.
- Introduced the design-note series (`DEVELOPMENT_REPORT_v0.10.3.md`, `LAYOUT_FIX_v1–v6.md`) to document each feedback loop.
- Title field now treats raw Markdown header text as multi-line (`\n`) titles—first line rendered bold, remaining text plain—while remarks default to blank and feed directly into the LLM user prompt.

## [v0.10.1a] - 2025-10-16

### Added
- Lithoformer bilingual pipeline: LLM schema emits paired `*_translation` fields供 UI 层使用（历史 CLI 已废弃，现统一由 TUI 消费）。
- QuizFormatter interleaves original text and Simplified Chinese line-by-line and appends batch IDs with sequential `L` codes.

### Changed
- UI 层会传递批次号与题号种子，保证 Formatter 输出在同一批次内保持一致。

## [v0.9.3]
- Introduced the bilingual formatter pipeline and synchronized it with Textual TUI flows。

## [v0.9.2]
- First Textual-based Lithoformer TUI rewrite featuring Detect/Start workflow, live log tailing, and the responsive questions table.

## [v0.9.1a]
- Added new Markdown quiz datasets to `data/input/lithoformer/`.

## [v0.9.1]
- Marked the project production-ready; hardened logging, error handling, and batch ID tooling.

## [v0.9.0]
- Established the DDD + Hexagonal architecture with Reanimator and Lithoformer as separate bounded contexts atop a shared kernel.
