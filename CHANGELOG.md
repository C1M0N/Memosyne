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
- Added `UseCaseFactory` to assemble provider/adapter/use case in the Application layer; TUI/CLI reuse the factory.
- CLI reads defaults (paths, flags, tuning) from `AppConfigService`; supports concurrent mode and streams progress per question.
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
- Introduced `config/paths.json` and `misc/` sample directories; CLI/API/TUI detect read-only samples and prompt users for real input/output paths.

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
- Lithoformer bilingual pipeline: LLM schema emits paired `*_translation` fields consumed by CLI, API, and TUI.
- QuizFormatter interleaves original text and Simplified Chinese line-by-line and appends batch IDs with sequential `L` codes.

### Changed
- CLI/API forward batch identifiers and question seeds so formatter output stays deterministic across a batch.

## [v0.9.3]
- Introduced the bilingual formatter pipeline and synchronized it with CLI/TUI flows.

## [v0.9.2]
- First Textual-based Lithoformer TUI rewrite featuring Detect/Start workflow, live log tailing, and the responsive questions table.

## [v0.9.1a]
- Added new Markdown quiz datasets to `data/input/lithoformer/`.

## [v0.9.1]
- Marked the project production-ready; hardened logging, error handling, and batch ID tooling.

## [v0.9.0]
- Established the DDD + Hexagonal architecture with Reanimator and Lithoformer as separate bounded contexts atop a shared kernel.
