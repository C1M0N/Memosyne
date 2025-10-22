# Changelog

All notable changes to this project are recorded here. Detailed iteration notes for the Lithoformer TUI live in `TUI_design_note/` and have been distilled into the entries below.

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
