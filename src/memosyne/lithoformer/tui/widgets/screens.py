"""Main screen implementation for the Lithoformer TUI."""

from __future__ import annotations

import asyncio
import inspect
import logging
import re
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter

from rich.markup import escape
from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Button, Input, ProgressBar, RichLog, Static

from ....core.models import TokenUsage
from ....shared.config import get_settings
from ....shared.infrastructure.llm import AnthropicProvider, OpenAIProvider
from ....shared.utils import (
    BatchIDGenerator,
    generate_output_filename,
    get_provider_from_model,
    resolve_model_input,
    unique_path,
)
from ....shared.utils.model_codes import list_all_models
from ...application import ParseQuizUseCase, QuizProcessingEvent
from ...domain.services import (
    infer_titles_from_filename,
    infer_titles_from_markdown,
    infer_question_seed,
    split_markdown_into_questions,
)
from ...infrastructure import FileAdapter, FormatterAdapter, LithoformerLLMAdapter
from ..constants import ASCII_LOGO
from ..logging_utils import build_textual_handler
from .filters import (
    BatchInput,
    CommandInput,
    InputPathInput,
    LithoformerDirectoryTree,
    ModelInput,
    ModelNoteInput,
    ModelSelectionInput,
    OutputFilenameInput,
    OutputPathInput,
    ProviderSelectionInput,
    SequenceInput,
    TagInput,
    TitleInput,
)
from .questions_table import QuestionRow, QuestionsTable


@dataclass(slots=True)
class DetectionResult:
    """Aggregate data produced by the Detect phase."""

    file_path: Path
    markdown: str
    blocks: list[dict[str, str]]
    provider: str
    model_id: str
    model_code: str
    title_main: str
    title_sub: str
    sequence: str
    batch_id: str
    output_filename: str
    detected_at: datetime
    questions: list[QuestionRow]


class MainScreen(Screen):
    """Main screen of the Lithoformer TUI application."""

    AUTO_INPUT_IDS = {
        "model-input",
        "tag-input",
        "title-input",
        "sequence-input",
        "batch-input",
        "output-filename-input",
    }

    action_mode = reactive("detect")  # detect | start | running

    def __init__(self) -> None:
        super().__init__()
        self.settings = get_settings()
        self.settings.ensure_dirs()

        self._detection: DetectionResult | None = None
        self._rows: dict[int, QuestionRow] = {}
        self._model_option_values: set[str] = set()
        self._manual_overrides: set[str] = set()
        self._auto_values: dict[str, str] = {}
        self._suspend_change_events = False

        self._main_thread_id: int | None = None
        self._log_handler = None
        self._file_tree = LithoformerDirectoryTree(self.settings.lithoformer_input_dir)
        self._selected_file: Path | None = None

        self._run_start_time: float | None = None
        self._total_tokens: int = 0
        self._processed_count: int = 0

        self._run_task: asyncio.Task[None] | None = None

        self.logger = logging.getLogger("memosyne.lithoformer.tui")

    # region convenience accessors -------------------------------------------------
    @property
    def questions_table(self) -> QuestionsTable:
        return self.query_one(QuestionsTable)

    @property
    def input_path_input(self) -> InputPathInput:
        return self.query_one(InputPathInput)

    @property
    def output_path_input(self) -> OutputPathInput:
        return self.query_one(OutputPathInput)

    @property
    def provider_select(self) -> ProviderSelectionInput:
        return self.query_one(ProviderSelectionInput)

    @property
    def model_select(self) -> ModelSelectionInput:
        return self.query_one(ModelSelectionInput)

    @property
    def model_input(self) -> ModelInput:
        return self.query_one(ModelInput)

    @property
    def tag_input(self) -> TagInput:
        return self.query_one(TagInput)

    @property
    def title_input(self) -> TitleInput:
        return self.query_one(TitleInput)

    @property
    def sequence_input(self) -> SequenceInput:
        return self.query_one(SequenceInput)

    @property
    def batch_input(self) -> BatchInput:
        return self.query_one(BatchInput)

    @property
    def output_filename_input(self) -> OutputFilenameInput:
        return self.query_one(OutputFilenameInput)

    @property
    def model_note_input(self) -> ModelNoteInput:
        return self.query_one(ModelNoteInput)

    @property
    def command_input(self) -> CommandInput:
        return self.query_one(CommandInput)

    @property
    def analysis_panel(self) -> Static:
        return self.query_one("#analysis-panel", Static)

    @property
    def log_view(self) -> RichLog:
        return self.query_one(RichLog)

    @property
    def action_button(self) -> Button:
        return self.query_one("#action-button", Button)

    @property
    def single_progress(self) -> ProgressBar:
        return self.query_one("#single-progress", ProgressBar)

    @property
    def total_progress(self) -> ProgressBar:
        return self.query_one("#total-progress", ProgressBar)

    # endregion -------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        """Compose the main screen layout."""
        yield Static(ASCII_LOGO, id="logo-panel")

        with Horizontal(id="meta-row"):
            yield Static(self._build_date_text(), id="meta-date")
            yield Static(self._build_time_text(), id="meta-time")
            yield Static(f"版本号：{self._get_version()}", id="meta-version")
            yield Static("标题：—", id="meta-title")
            yield Static("文件：—", id="meta-file")

        questions_table = QuestionsTable()
        table_panel = Container(questions_table, id="table-wrapper")
        table_panel.border_title = "题目列表"
        table_panel.border_subtitle = "[dodger_blue2]数据表[/]"

        analysis_panel = Static("[dim]空[/]", id="analysis-panel")
        analysis_panel.border_title = "解析摘要"
        analysis_panel.border_subtitle = "[dodger_blue2]预留区域[/]"

        form_column = Vertical(
            InputPathInput(value=str(self.settings.lithoformer_input_dir)),
            OutputPathInput(value=str(self.settings.lithoformer_output_dir)),
            ProviderSelectionInput(value=self.settings.default_llm_provider),
            ModelSelectionInput(),
            ModelInput(),
            TagInput(),
            TitleInput(),
            SequenceInput(),
            BatchInput(),
            OutputFilenameInput(),
            ModelNoteInput(value=""),
            analysis_panel,
            id="form-column",
        )
        form_column.border_title = "运行配置"
        form_column.border_subtitle = "[dodger_blue2]输入/自动推断[/]"

        selected_file_display = Static("当前未选择文件", id="selected-file-display")
        selected_file_display.border_title = "当前文件"
        selected_file_display.border_subtitle = "[dodger_blue2]自动推断[/]"

        action_button = Button("Detect", id="action-button", variant="primary")
        action_wrapper = Container(action_button, id="action-wrapper")
        action_wrapper.border_title = "操作"
        action_wrapper.border_subtitle = "[dodger_blue2]按钮[/]"

        tree_column = Vertical(
            self._file_tree,
            selected_file_display,
            action_wrapper,
            id="tree-column",
        )
        tree_column.border_title = "文件选择"

        with Horizontal(id="workspace"):
            yield table_panel
            with Horizontal(id="side-wrapper"):
                yield form_column
                yield tree_column

        log_view = RichLog(
            id="log-view",
            highlight=True,
            markup=True,
        )
        log_view.border_title = "日志"
        log_view.border_subtitle = "[dodger_blue2]RichLog[/]"
        if hasattr(log_view, "max_lines"):
            log_view.max_lines = 999

        log_panel = Vertical(
            Static("Log", id="log-title"),
            log_view,
            id="log-panel",
        )
        log_panel.border_title = "日志输出"
        log_panel.border_subtitle = "[dodger_blue2]RichLog[/]"

        command_panel = Vertical(
            Static("单题进度", classes="progress-label"),
            ProgressBar(id="single-progress", total=1),
            Static("总进度", classes="progress-label"),
            ProgressBar(id="total-progress", total=1),
            CommandInput(),
            Static("状态：待机", id="status-message"),
            Static("完成：0/0 | 耗时：00:00 | 估计剩余：--:-- | Tokens：0", id="stats-display"),
            id="command-panel",
        )
        command_panel.border_title = "运行状态"
        command_panel.border_subtitle = "[dodger_blue2]统计指标[/]"

        with Horizontal(id="bottom-row"):
            yield log_panel
            yield command_panel

    # region lifecycle ------------------------------------------------------------
    async def on_mount(self) -> None:
        """Handle mount event."""
        self._main_thread_id = threading.get_ident()

        handler = build_textual_handler(self._write_log)
        self._log_handler = handler
        logging.getLogger().addHandler(handler)

        self._refresh_model_options(self.settings.default_llm_provider)
        self.action_mode = "detect"
        self._reset_progress_bars()

        self.logger.info("Lithoformer TUI 已启动")

    async def on_unmount(self) -> None:
        """Detach logging handlers when leaving the screen."""
        if self._log_handler:
            logging.getLogger().removeHandler(self._log_handler)
            self._log_handler = None

    # endregion ------------------------------------------------------------------

    # region event handlers ------------------------------------------------------
    @on(Button.Pressed, "#action-button")
    async def handle_action_button(self) -> None:
        """Route button presses depending on the current mode."""
        if self.action_mode == "detect":
            await self._run_detect()
        elif self.action_mode == "start":
            await self._run_start()

    @on(ProviderSelectionInput.Changed)
    async def handle_provider_changed(self, event: ProviderSelectionInput.Changed) -> None:
        """Refresh model options when provider changes."""
        provider = event.value if isinstance(event.value, str) else "openai"
        self._refresh_model_options(provider)
        self.logger.info("已切换厂商为 %s", provider)

    @on(ModelSelectionInput.Changed)
    async def handle_model_selected(self, event: ModelSelectionInput.Changed) -> None:
        """Populate model input when a model is picked from the dropdown."""
        if isinstance(event.value, str) and event.value:
            self._set_input_value(self.model_input, event.value)

    @on(LithoformerDirectoryTree.FileSelected)
    async def handle_file_selected(self, event: LithoformerDirectoryTree.FileSelected) -> None:
        """Handle file selection from the directory tree."""
        if event.path.suffix.lower() != ".md":
            self.logger.warning("请选择 Markdown (.md) 文件")
            return

        self._selected_file = event.path
        self._update_meta_file(event.path)
        self._update_selected_file_display(event.path)
        self.logger.info("已选择输入文件：%s", event.path.name)
        self._reset_detection()

    @on(Input.Changed, "#input-directory")
    async def handle_input_path_changed(self, event: Input.Changed) -> None:
        """Update the directory tree root when the input path changes."""
        if self._suspend_change_events:
            return

        path = Path(event.value).expanduser()
        if not path.exists() or not path.is_dir():
            self.logger.error("输入路径无效：%s", path)
            return

        await self._swap_directory_tree(path)
        self.logger.info("已更新输入路径至：%s", path)

    @on(Input.Submitted, "#input-directory")
    async def handle_input_path_submitted(self, event: Input.Submitted) -> None:
        """Ensure the tree refreshes after pressing Enter."""
        await self.handle_input_path_changed(Input.Changed(event.input, event.value))

    @on(Input.Blurred, "#input-directory")
    async def handle_input_path_blur(self, event: Input.Blurred) -> None:
        """Normalize the path display on blur."""
        value = event.value.strip()
        if value:
            normalized = str(Path(value).expanduser())
            self._set_input_value(self.input_path_input, normalized)

    @on(Input.Blurred, "#output-directory")
    async def handle_output_path_blur(self, event: Input.Blurred) -> None:
        """Normalize output path on blur."""
        value = event.value.strip()
        if value:
            normalized = str(Path(value).expanduser())
            self._set_input_value(self.output_path_input, normalized)

    @on(Input.Submitted, "#command-input")
    async def handle_command_submitted(self, event: Input.Submitted) -> None:
        """Handle command input submission."""
        command = event.value.strip()
        if command == "/clear":
            self.log_view.clear()
            self._set_input_value(self.command_input, "")
            self.logger.info("日志已清空")
        elif command:
            self.logger.warning("未知命令：%s", command)
            self._set_input_value(self.command_input, "")

    @on(Input.Changed, "#command-input")
    async def handle_command_changed(self, event: Input.Changed) -> None:
        """Prevent command input from marking manual overrides."""
        if self._suspend_change_events:
            return
        self._set_input_value(self.command_input, event.value)

    @on(Input.Changed, "#model-input")
    @on(Input.Changed, "#tag-input")
    @on(Input.Changed, "#title-input")
    @on(Input.Changed, "#sequence-input")
    @on(Input.Changed, "#batch-input")
    @on(Input.Changed, "#output-filename-input")
    async def handle_auto_field_changed(self, event: Input.Changed) -> None:
        """Track manual overrides for auto-filled fields."""
        widget_id = event.input.id
        if self._suspend_change_events:
            return
        if widget_id in self.AUTO_INPUT_IDS:
            if event.value.strip():
                self._manual_overrides.add(widget_id)
            else:
                self._manual_overrides.discard(widget_id)

    # endregion ------------------------------------------------------------------

    async def _run_detect(self) -> None:
        """Run detection on the currently selected file."""
        if not self._selected_file:
            self.logger.error("请先在右侧选择一个 Markdown 文件")
            return

        if not self.model_input.value.strip():
            self.logger.error("请先配置使用的模型")
            return

        self._set_action_state("detecting")
        self.logger.info("开始检测文件：%s", self._selected_file.name)
        self._set_status("状态：检测中…")

        try:
            provider, model_id, model_code = self._resolve_model()
            detection = await asyncio.to_thread(
                self._detect_worker,
                self._selected_file,
                provider,
                model_id,
                model_code,
            )
        except Exception as exc:
            self.logger.error("检测失败：%s", exc)
            self._set_action_state("detect")
            self._set_status("状态：待机")
            return

        self._capture_detection(detection)
        self.logger.info("检测完成，共 %d 题", len(detection.questions))
        self._set_status("状态：等待开始")
        self._reset_progress_bars(total=len(detection.questions))
        self.action_mode = "start"
        self._set_action_state("start")

    async def _run_start(self) -> None:
        """Start parsing the detected questions."""
        if not self._detection:
            self.logger.error("请先执行 Detect")
            return

        if not self._validate_before_start():
            return

        detection = self._detection

        try:
            adapter = self._create_llm_adapter(detection.provider, detection.model_id)
        except Exception as exc:
            self.logger.error("创建 LLM Provider 失败：%s", exc)
            return

        self.action_mode = "running"
        self._set_action_state("running")
        self._set_status("状态：解析中…")
        self._run_start_time = perf_counter()
        self._processed_count = 0
        self._total_tokens = 0

        use_case = ParseQuizUseCase(llm=adapter)
        formatter = FormatterAdapter.create()
        file_adapter = FileAdapter.create()

        if self._run_task:
            self.logger.warning("解析任务仍在运行，忽略新的 START 请求")
            return

        self._run_task = asyncio.create_task(
            self._process_questions(detection, use_case, formatter, file_adapter),
            name="LithoformerRunTask",
        )

    async def _process_questions(
        self,
        detection: DetectionResult,
        use_case: ParseQuizUseCase,
        formatter: FormatterAdapter,
        file_adapter: FileAdapter,
    ) -> None:
        """Background task that processes questions sequentially without freezing UI."""
        try:
            items: list = []
            total_questions = len(detection.questions)
            running_tokens = TokenUsage()

            for index, block in enumerate(detection.blocks, start=1):
                self._mark_row_in_progress(index)
                self._set_status(f"状态：解析第 {index}/{total_questions} 题…")
                self._update_single_progress(reset=True)
                await asyncio.sleep(0)

                try:
                    event, running_tokens = await asyncio.to_thread(
                        use_case.process_block,
                        block,
                        index,
                        total_questions,
                        running_tokens,
                        show_spinner=False,
                    )
                except Exception as exc:  # pragma: no cover - defensive
                    self.logger.error("解析过程中发生错误：%s", exc)
                    self._set_status("状态：解析失败")
                    self.action_mode = "detect"
                    self._set_action_state("detect")
                    return

                self._apply_event_to_row(event, formatter, detection.title_main, detection.title_sub)
                if event.status == "success" and event.item:
                    items.append(event.item)

                self._processed_count += 1
                self._total_tokens = running_tokens.total_tokens
                self._update_single_progress(done=True)
                self._update_total_progress(self._processed_count, total_questions)
                self._refresh_stats(total_questions)
                await asyncio.sleep(0)

            try:
                output_dir = Path(self.output_path_input.value.strip() or self.settings.lithoformer_output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)
                output_path = unique_path(output_dir / detection.output_filename)
                sequence_source = self.sequence_input.value.strip() or detection.sequence
                output_text = formatter.format(
                    items,
                    detection.title_main,
                    detection.title_sub,
                    batch_code=detection.batch_id,
                    question_start=infer_question_seed(sequence_source),
                )
                file_adapter.write_text(output_path, output_text)
            except Exception as exc:
                self.logger.error("写入输出文件失败：%s", exc)
                self._set_status("状态：写入失败")
                self.action_mode = "detect"
                self._set_action_state("detect")
                return

            self.logger.info(
                "解析完成：%s（成功 %d/%d，Tokens %s）",
                detection.output_filename,
                len(items),
                total_questions,
                f"{self._total_tokens:,}",
            )
            self._set_status("状态：解析完成")
        finally:
            self._run_start_time = None
            self.action_mode = "detect"
            self._set_action_state("detect")
            self._run_task = None

    # region detection helpers ----------------------------------------------------
    def _detect_worker(
        self,
        file_path: Path,
        provider: str,
        model_id: str,
        model_code: str,
    ) -> DetectionResult:
        """Worker function that runs during Detect."""
        adapter = FileAdapter.create()
        markdown = adapter.read_markdown(file_path)
        blocks = split_markdown_into_questions(markdown)
        if not blocks:
            raise ValueError("未在 Markdown 中检测到题目内容")

        title_main, title_sub = infer_titles_from_markdown(markdown)
        if not title_main or not title_sub:
            fallback_main, fallback_sub = infer_titles_from_filename(file_path)
            title_main = title_main or fallback_main
            title_sub = title_sub or fallback_sub

        sequence = self._infer_sequence_from_path(file_path)

        generator = BatchIDGenerator(
            output_dir=self.settings.lithoformer_output_dir,
            timezone=self.settings.batch_timezone,
        )
        batch_id = generator.generate(term_count=len(blocks))

        output_filename = generate_output_filename(
            batch_id=batch_id,
            model_code=model_code,
            input_filename=file_path.name,
            ext="txt",
        )

        questions: list[QuestionRow] = []
        for index, block in enumerate(blocks, start=1):
            number = self._guess_question_number(block, index)
            char_count = self._measure_characters(block)
            questions.append(
                QuestionRow(
                    row_key=f"row-{index}",
                    index=index,
                    number=number,
                    status="Pending",
                    char_count=char_count,
                    qtype="—",
                    output_chars=0,
                    elapsed=0.0,
                )
            )

        return DetectionResult(
            file_path=file_path,
            markdown=markdown,
            blocks=blocks,
            provider=provider,
            model_id=model_id,
            model_code=model_code,
            title_main=title_main,
            title_sub=title_sub,
            sequence=sequence,
            batch_id=batch_id,
            output_filename=output_filename,
            detected_at=datetime.now(),
            questions=questions,
        )

    def _capture_detection(self, detection: DetectionResult) -> None:
        """Persist detection results into screen state."""
        self._detection = detection
        self._rows = {row.index: row for row in detection.questions}
        self.questions_table.questions = detection.questions

        self._set_meta_title(detection.title_main or "—")

        self._set_auto_field(self.tag_input, detection.title_sub or "")
        self._set_auto_field(self.title_input, detection.title_main or "")
        self._set_auto_field(self.sequence_input, detection.sequence or "")
        self._set_auto_field(self.batch_input, detection.batch_id)
        self._set_auto_field(self.output_filename_input, detection.output_filename)

        if detection.model_code:
            self._set_auto_field(self.model_input, detection.model_code)

        self._update_analysis_summary(detection)

    def _reset_detection(self) -> None:
        """Reset detection-related state when switching files."""
        self._detection = None
        self._rows.clear()
        self.questions_table.clear()
        self._reset_progress_bars()
        self._processed_count = 0
        self._total_tokens = 0
        self._set_status("状态：待机")
        self._set_stats_text(0, 0, 0.0, "--:--", 0)
        self.action_mode = "detect"
        self._set_action_state("detect")
        self._update_analysis_summary(None)

    def _update_analysis_summary(self, detection: DetectionResult | None) -> None:
        """Render a compact summary of the detection outcome."""
        panel = self.analysis_panel
        if detection is None:
            panel.update("[dim]空[/]")
            return

        provider_label = detection.provider.title() if detection.provider else "—"
        summary_lines = [
            f"[bold cyan]文件[/] {escape(detection.file_path.name)}",
            f"[bold cyan]题目数[/] {len(detection.questions)}",
            f"[bold cyan]厂商[/] {escape(provider_label)}",
            f"[bold cyan]主标题[/] {escape(detection.title_main or '—')}",
            f"[bold cyan]副标题[/] {escape(detection.title_sub or '—')}",
            f"[bold cyan]模型[/] {escape(detection.model_id)}",
            f"[bold cyan]批次号[/] {escape(detection.batch_id)}",
            f"[bold cyan]输出文件[/] {escape(detection.output_filename)}",
            f"[bold cyan]检测时间[/] {detection.detected_at.strftime('%H:%M:%S')}",
        ]
        panel.update("\n".join(summary_lines))

    # endregion ------------------------------------------------------------------

    # region parsing helpers ------------------------------------------------------
    def _apply_event_to_row(
        self,
        event: QuizProcessingEvent,
        formatter: FormatterAdapter,
        title_main: str,
        title_sub: str,
    ) -> None:
        """Apply a processing event to the table row and log on failure."""
        row = self._rows.get(event.index)
        if not row:
            return

        if event.status == "success" and event.item:
            row.status = "Done"
            row.qtype = event.item.qtype or row.qtype
            rendered = formatter.format([event.item], title_main, title_sub)
            row.output_chars = len(rendered)
            row.elapsed = event.elapsed
            row.error = None
        elif event.status == "invalid":
            row.status = "ERROR"
            row.error = event.error or "输出校验失败"
            row.elapsed = event.elapsed
        else:
            row.status = "ERROR"
            row.error = event.error or "解析失败"
            row.elapsed = event.elapsed

        self.questions_table.update_question_status(
            row.row_key,
            row.status,
            row.qtype,
            row.output_chars,
            row.elapsed,
        )

        if row.error:
            self.logger.error("题目 #%s 解析失败：%s", row.number, row.error)

    def _mark_row_in_progress(self, index: int) -> None:
        """Highlight the row that is currently being processed."""
        row = self._rows.get(index)
        if not row:
            return
        row.status = "In Progress"
        self.questions_table.update_question_status(row.row_key, "In Progress")

    # endregion ------------------------------------------------------------------

    # region UI helpers -----------------------------------------------------------
    def _set_action_state(self, state: str) -> None:
        """Synchronise the action button with internal state."""
        button = self.action_button
        if state == "detect":
            button.label = "Detect"
            button.variant = "primary"
            button.disabled = False
            button.loading = False
        elif state == "detecting":
            button.label = "Detect…"
            button.variant = "primary"
            button.disabled = True
            button.loading = True
        elif state == "start":
            button.label = "START"
            button.variant = "error"
            button.disabled = False
            button.loading = False
        elif state == "running":
            button.label = "RUNNING…"
            button.variant = "warning"
            button.disabled = True
            button.loading = True

    def _reset_progress_bars(self, total: int = 0) -> None:
        """Reset both progress bars."""
        single = self.single_progress
        single.total = 1
        single.progress = 0

        total_bar = self.total_progress
        total_bar.total = max(total, 1)
        total_bar.progress = 0

    def _update_single_progress(self, *, reset: bool = False, done: bool = False) -> None:
        """Update the per-question progress indicator."""
        bar = self.single_progress
        if reset:
            bar.progress = 0
        if done:
            bar.progress = bar.total

    def _update_total_progress(self, completed: int, total: int) -> None:
        """Update the total progress indicator."""
        bar = self.total_progress
        bar.total = max(total, 1)
        bar.progress = min(completed, bar.total)

    def _set_status(self, text: str) -> None:
        """Update status message."""
        self.query_one("#status-message", Static).update(text)

    def _refresh_stats(self, total: int) -> None:
        """Refresh statistics display based on current counters."""
        elapsed = (perf_counter() - self._run_start_time) if self._run_start_time else 0.0
        remaining = self._estimate_remaining_time(elapsed, self._processed_count, total)
        self._set_stats_text(self._processed_count, total, elapsed, remaining, self._total_tokens)

    def _set_stats_text(self, completed: int, total: int, elapsed: float, remaining: str, tokens: int) -> None:
        """Render the stats text."""
        self.query_one("#stats-display", Static).update(
            f"完成：{completed}/{total} | 耗时：{self._format_seconds(elapsed)} | "
            f"估计剩余：{remaining} | Tokens：{tokens:,}"
        )

    def _write_log(self, markup: str) -> None:
        """Thread-safe log sink for the custom logging handler."""
        if threading.get_ident() == self._main_thread_id:
            self.log_view.write(markup)
        else:
            self.call_from_thread(self.log_view.write, markup)

    def _set_auto_field(self, widget, value: str) -> None:
        """Populate an auto field if it wasn't manually overridden."""
        if widget.id in self._manual_overrides and widget.value.strip():
            return
        self._auto_values[widget.id] = value
        self._set_input_value(widget, value)

    def _set_input_value(self, widget, value: str) -> None:
        """Set an input value without triggering manual override logic."""
        self._suspend_change_events = True
        try:
            widget.value = value
        finally:
            self._suspend_change_events = False

    async def _swap_directory_tree(self, path: Path) -> None:
        """Replace the directory tree with a new root path."""
        container = self.query_one("#tree-column", Vertical)
        removal = self._file_tree.remove()
        if inspect.isawaitable(removal):
            await removal
        self._file_tree = LithoformerDirectoryTree(path)
        mount_result = container.mount(self._file_tree, before=self.query_one("#selected-file-display", Static))
        if inspect.isawaitable(mount_result):
            await mount_result

    def _set_meta_title(self, title: str) -> None:
        safe_title = escape(title) if title else "—"
        self.query_one("#meta-title", Static).update(f"标题：{safe_title}")

    def _update_meta_file(self, path: Path) -> None:
        self.query_one("#meta-file", Static).update(f"文件：{escape(path.name)}")

    def _update_selected_file_display(self, path: Path) -> None:
        self.query_one("#selected-file-display", Static).update(escape(str(path)))

    # endregion ------------------------------------------------------------------

    # region validation & utility helpers ---------------------------------------
    def _validate_before_start(self) -> bool:
        """Ensure all required fields are populated before START."""
        required = {
            "输入路径": self.input_path_input.value.strip(),
            "输出路径": self.output_path_input.value.strip(),
            "模型": self.model_input.value.strip(),
            "标题": self.title_input.value.strip(),
            "标签": self.tag_input.value.strip(),
            "序号": self.sequence_input.value.strip(),
            "批次号": self.batch_input.value.strip(),
            "输出文件名": self.output_filename_input.value.strip(),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            self.logger.error("以下字段不能为空：%s", ", ".join(missing))
            return False
        return True

    def _refresh_model_options(self, provider: str) -> None:
        """Refresh model options based on provider."""
        models = list_all_models()
        options = [(model, model) for model in models.get(provider, [])]
        self.model_select.models = options
        self._model_option_values = {value for _, value in options}

        default_model = (
            self.settings.default_openai_model if provider == "openai" else self.settings.default_anthropic_model
        )

        if default_model in self._model_option_values and not self.model_input.value:
            self.model_select.value = default_model
            self._set_auto_field(self.model_input, default_model)

    def _resolve_model(self) -> tuple[str, str, str]:
        """Resolve model string to provider, model_id, and model_code."""
        value = self.model_input.value.strip()
        if not value:
            raise ValueError("模型输入不能为空")
        model_id, model_code = resolve_model_input(value)
        provider = get_provider_from_model(model_id)
        return provider, model_id, model_code

    def _create_llm_adapter(self, provider: str, model_id: str) -> LithoformerLLMAdapter:
        """Create LLM adapter based on provider."""
        if provider == "anthropic":
            if not self.settings.anthropic_api_key:
                raise RuntimeError("未配置 ANTHROPIC_API_KEY")
            llm_provider = AnthropicProvider(
                model=model_id,
                api_key=self.settings.anthropic_api_key,
                temperature=self.settings.default_temperature,
            )
        else:
            llm_provider = OpenAIProvider(
                model=model_id,
                api_key=self.settings.openai_api_key,
                temperature=self.settings.default_temperature,
            )
        return LithoformerLLMAdapter.from_provider(llm_provider)

    @staticmethod
    def _guess_question_number(block: dict[str, str], index: int) -> str:
        """Extract a human-friendly question number."""
        question_text = (block.get("question") or "").strip()
        if question_text:
            first_line = question_text.splitlines()[0].strip()
            if len(first_line) > 24:
                first_line = first_line[:24]
            if first_line:
                return first_line
        return f"Q{index:02d}"

    @staticmethod
    def _measure_characters(block: dict[str, str]) -> int:
        """Measure the total characters for a block."""
        return sum(len(block.get(key, "")) for key in ("context", "question", "answer"))

    @staticmethod
    def _infer_sequence_from_path(path: Path) -> str:
        """Infer sequence number from file path."""
        matches = re.findall(r"\d+", path.stem)
        return matches[-1] if matches else ""

    @staticmethod
    def _format_seconds(seconds: float) -> str:
        """Format seconds to MM:SS."""
        if seconds <= 0:
            return "00:00"
        minutes, secs = divmod(seconds, 60)
        return f"{int(minutes):02d}:{int(secs):02d}"

    @staticmethod
    def _estimate_remaining_time(elapsed: float, completed: int, total: int) -> str:
        """Estimate remaining processing time based on average."""
        if completed <= 0 or elapsed <= 0:
            return "--:--"
        avg = elapsed / completed
        remaining_seconds = max((total - completed) * avg, 0)
        return MainScreen._format_seconds(remaining_seconds)

    @staticmethod
    def _build_date_text() -> str:
        return f"日期：{datetime.now().strftime('%Y-%m-%d')}"

    @staticmethod
    def _build_time_text() -> str:
        return f"时间：{datetime.now().strftime('%H:%M')}"

    @staticmethod
    def _get_version() -> str:
        """Get application version."""
        try:
            from .... import __version__

            return __version__
        except ImportError:
            return "0.0.0"

    # endregion ------------------------------------------------------------------


__all__ = ["MainScreen", "DetectionResult"]
