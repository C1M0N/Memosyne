"""Main screen implementation for the Reanimator TUI (aligned with Lithoformer)."""

from __future__ import annotations

import asyncio
import inspect
import logging
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter

from rich.markup import escape
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.events import Key
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Button, Footer, Input, RichLog, Static, TabbedContent, TabPane

from ....core.models import TokenUsage
from ....shared.config import get_settings
from ....shared.infrastructure.app_config import SQLiteAppConfigService
from ....shared.infrastructure.llm import OpenAIProvider, AnthropicProvider
from ....shared.infrastructure.stats_db import get_stats_repository
from ....shared.infrastructure.storage.csv_repository import CSVTermRepository
from ....shared.tui import CustomProgressBar, RateLimitBar, RateLimitManager
from ....shared.utils import unique_path
from ....shared.utils.batch import BatchIDGenerator
from ....shared.utils.filename import generate_output_filename, format_batch_id
from ....shared.utils.model_codes import resolve_model_input, get_provider_from_model
from ...application.concurrent_use_case import ConcurrentProcessTermsUseCase
from ...application.use_cases import ProcessTermsUseCase
from ...domain.models import TermInput, TermOutput, WordID
from ...domain.services import map_field_label, parse_word_index_from_filename
from ...infrastructure.llm_adapter import ReanimatorLLMAdapter
from ...infrastructure.term_list_adapter import TermListAdapter
from ..constants import ASCII_LOGO
from ..database_log_handler import setup_database_logging
from ..logging_utils import build_textual_handler
from .feature_toggles import ReanimatorFeatureToggles
from .filters import (
    BatchIdInput,
    BatchNoteInput,
    CommandInput,
    ConfigDefaultInputDirInput,
    ConfigDefaultModelInput,
    ConfigDefaultOutputDirInput,
    ConfigMaxConcurrentInput,
    ConfigMaxRetriesInput,
    ConfigTermListPathInput,
    InputPathInput,
    ModelSelectionInput,
    ModelInput,
    NoteInput,
    OutputFilenameInput,
    OutputPathInput,
    ProviderSelectionInput,
    SequenceInput,
    ReanimatorDirectoryTree,
)
from .terms_table import TermRow, TermsTable


@dataclass(slots=True)
class DetectionResult:
    file_path: Path
    terms: list[TermInput]
    model: str  # canonical model id (e.g., gpt-4o)
    model_code: str
    provider: str  # openai / anthropic
    batch_id: str
    batch_note: str
    extra_note: str
    start_word_index: int
    output_filename: str
    output_dir: Path
    detected_at: datetime
    term_rows: list[TermRow]
    row_map: dict[str, TermRow]


class ReanimatorScreen(Screen):
    """Main screen of the Reanimator TUI, mirroring Lithoformer layout."""

    DEFAULT_CSS = """
    #left-col {
        height: 100%;
    }

    #header-area {
        height: auto;
    }

    #questions-area {
        height: 1fr;
        border: round $primary;
        padding: 0;
    }

    #rate-limit-bar {
        height: 1;
        min-height: 1;
        max-height: 1;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit_app", "Quit", show=True, priority=True),
        Binding("p", "toggle_concurrent", "并行", show=True, priority=False),
    ]

    action_mode = reactive("detect")

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.settings = get_settings()
        self.settings.ensure_dirs()

        self._config_service = SQLiteAppConfigService(
            self.settings.db_dir / "config.db",
            context="reanimator",
        )
        self._stats_repo = get_stats_repository(self.settings.db_dir / "stat.db")

        paths = self._config_service.get_paths()
        input_dir = paths.input_dir or (self.settings.db_dir.parent / "misc/input/reanimator")
        input_dir.mkdir(parents=True, exist_ok=True)
        self._file_tree = ReanimatorDirectoryTree(input_dir)
        self._selected_file: Path | None = None

        self._detection: DetectionResult | None = None
        self._rows: dict[int, TermRow] = {}

        self._waiting_for_overwrite_confirmation = False
        self._conflict_terms: list[TermOutput] = []

        self._log_handler = None
        self._database_log_handler = None
        self._main_thread_id: int | None = None
        self._run_start_time: float | None = None
        self._total_tokens: TokenUsage = TokenUsage()
        self._rate_limit_manager = RateLimitManager()
        self._provider_options: list[tuple[str, str]] = []
        self._model_options_by_provider: dict[str, list[tuple[str, str]]] = {}
        self._current_provider: str = "openai"
        self._current_prompt_note: str = ""
        self._suspend_change_events = False

        self.logger = logging.getLogger("memosyne.reanimator.tui")

    # ------------------------------------------------------------------
    # Compose / layout helpers
    # ------------------------------------------------------------------
    def compose(self) -> ComposeResult:
        flags = self._config_service.get_feature_flags()
        bundle = self._config_service.get_bundle()
        paths = self._config_service.get_paths()
        provider_options = self._build_provider_options()
        provider_values = [value for _, value in provider_options]

        default_model = bundle.default_model or ""
        default_provider = provider_values[0] if provider_values else "openai"
        default_model_value: str | None = None
        if "::" in default_model:
            prov_hint, model_hint = default_model.split("::", 1)
            prov_hint = prov_hint.lower()
            candidate = f"{prov_hint}::{model_hint}"
            if prov_hint in provider_values:
                default_provider = prov_hint
                default_model_value = candidate

        model_options_map = self._build_model_option_map()
        self._model_options_by_provider = model_options_map
        model_options = model_options_map.get(default_provider, [])
        if default_model_value and default_model_value not in {value for _, value in model_options}:
            default_model_value = None

        self._provider_options = provider_options
        self._current_provider = default_provider

        input_dir_value = str(paths.input_dir or "")
        output_dir_value = str(paths.output_dir or "")

        with Horizontal(id="main-container"):
            with Vertical(id="left-col"):
                with Vertical(id="header-area"):
                    yield Static(ASCII_LOGO, id="logo-panel")
                    yield ReanimatorFeatureToggles(
                        concurrent=flags.enable_concurrent,
                        id="feature-toggles",
                    )

                terms_area = Vertical(id="questions-area")
                terms_area.border_title = "术语列表"
                with terms_area:
                    yield TermsTable()
                    yield RateLimitBar()

            with Vertical(id="right-area"):
                with Horizontal(id="top-section"):
                    with Vertical(id="middle-col"):
                        with TabbedContent(id="main-tabs"):
                            with TabPane("输入", id="tab-inputs"):
                                yield InputPathInput(value=input_dir_value)
                                yield OutputPathInput(value=output_dir_value)
                                with Horizontal(id="provider-model-row"):
                                    yield ProviderSelectionInput(options=provider_options, value=default_provider)
                                    yield ModelSelectionInput(options=model_options, value=default_model_value)
                                yield ModelInput(value=bundle.default_model)
                                yield BatchNoteInput()
                                with Horizontal(id="seq-batch-row"):
                                    yield SequenceInput(value="")
                                    yield BatchIdInput()
                                yield OutputFilenameInput()
                                yield NoteInput()

                            with TabPane("配置", id="tab-config"):
                                yield ConfigDefaultInputDirInput(value=input_dir_value)
                                yield ConfigDefaultOutputDirInput(value=output_dir_value)
                                yield ConfigDefaultModelInput(value=bundle.default_model)
                                yield ConfigMaxConcurrentInput(value=str(bundle.tuning.max_concurrent))
                                yield ConfigMaxRetriesInput(value=str(bundle.tuning.max_retries))
                                yield ConfigTermListPathInput(value="db/term_list_v1.csv")

                    with Vertical(id="right-col"):
                        yield self._file_tree
                        yield Button("Detect", id="action-button", variant="primary")

                log_view = RichLog(id="log-view", highlight=True, markup=True)
                log_view.border_title = "控制台"
                if hasattr(log_view, "max_lines"):
                    log_view.max_lines = 999
                yield log_view
                yield CommandInput()

        yield CustomProgressBar(total=1, id="total-progress")
        yield Footer()

    def _build_provider_options(self) -> list[tuple[str, str]]:
        options = self._config_service.get_providers_list()
        if options:
            return options
        return [("OpenAI", "openai"), ("Anthropic", "anthropic")]

    def _build_model_option_map(self) -> dict[str, list[tuple[str, str]]]:
        display_models = getattr(self._config_service, "get_display_models", lambda: [])()
        mapping: dict[str, list[tuple[str, str]]] = {}
        if not display_models:
            mapping["openai"] = [("GPT-4o", "openai::gpt-4o")]
            return mapping
        for model in display_models:
            label = model.display_name
            if model.alias:
                label = f"{label} ({model.alias})"
            value = f"{model.provider}::{model.model_id}"
            mapping.setdefault(model.provider, []).append((label, value))
        return mapping

    def _refresh_model_select(self, provider: str, preferred_value: str | None = None) -> None:
        options = self._model_options_by_provider.get(provider)
        if not options:
            self.logger.warning("未找到厂商 %s 的模型列表，保留现有选项", provider)
            return
        select = self.model_select
        with suppress(Exception):
            select.clear()
            select.set_options(options)
        self._current_provider = provider
        option_values = {value for _, value in options}
        target = preferred_value if preferred_value in option_values else options[0][1]
        with suppress(Exception):
            select.value = target
        self._apply_model_choice(target)

    def _apply_model_choice(self, value: str | None) -> None:
        if not value or value == "others":
            self.logger.info("请选择或在输入框中手动输入模型 ID")
            return
        self.model_input.value = value

    def _handle_progress_event(
        self,
        completed: int,
        total: int,
        token_usage: TokenUsage,
        rate_limit_info: dict | None,
        term_index: int | None = None,
        term_elapsed: float | None = None,
        state: str = "done",
        retry_wait: float | None = None,
    ) -> None:
        def _update() -> None:
            elapsed_run = perf_counter() - self._run_start_time if self._run_start_time else 0
            self._total_tokens = token_usage
            self._update_progress_summary(elapsed_run, completed, total)
            if rate_limit_info:
                self._update_rate_limit_bar(rate_limit_info)
            if term_index is not None:
                row = self._rows.get(term_index + 1)
                if row:
                    if state == "start":
                        self.terms_table.update_term_status(row.row_key, "In Progress")
                    elif state == "waiting_429":
                        label = "Waiting 429"
                        if retry_wait is not None:
                            label = f"Waiting 429 ({int(retry_wait)}s)"
                        self.terms_table.update_term_status(row.row_key, label)
                    elif state == "done":
                        self.terms_table.update_term_status(row.row_key, "Done", elapsed=term_elapsed)
                    elif state == "error":
                        self.terms_table.update_term_status(row.row_key, "ERROR", elapsed=term_elapsed)

        import threading

        if threading.get_ident() == self._main_thread_id:
            _update()
        elif self.app:
            self.app.call_from_thread(_update)

    def _update_rate_limit_bar(self, info: dict | None) -> None:
        if info:
            self._rate_limit_manager.update(info)
        current = self._rate_limit_manager.get_current_info()
        with suppress(Exception):
            bar = self.query_one("#rate-limit-bar", RateLimitBar)
            bar.update_rate_limit(current)

    def _refresh_detection_model(self) -> None:
        """模型输入变化时，实时刷新检测缓存和输出文件名。"""
        if not self._detection:
            return
        try:
            provider, model_name, model_code = self._resolve_model()
        except Exception as exc:  # noqa: BLE001
            self.logger.debug("解析模型输入失败，保持原配置：%s", exc)
            return

        detection = self._detection
        changed = False

        if detection.provider != provider or detection.model != model_name:
            detection.provider = provider
            detection.model = model_name
            detection.model_code = model_code
            changed = True

        new_output = generate_output_filename(
            batch_id=detection.batch_id,
            model_code=model_code,
            input_filename=detection.file_path.name,
            ext="csv",
        )
        if detection.output_filename != new_output:
            detection.output_filename = new_output
            with suppress(Exception):
                self._set_input_value(self.output_filename_input, new_output)
            changed = True

        if changed:
            self.logger.info(
                "检测配置已更新：模型 %s，输出文件名调整为 %s",
                model_code,
                detection.output_filename,
            )

    def _update_progress_summary(self, elapsed: float, completed: int, total: int) -> None:
        remaining = 0.0
        if completed and total and elapsed > 0:
            avg = elapsed / completed
            remaining = avg * max(total - completed, 0)
        tokens_total = getattr(self._total_tokens, "total_tokens", 0)
        self.total_progress.update_progress(
            current=completed,
            total=total or completed,
            elapsed_time=self._format_duration(elapsed),
            remaining_time=self._format_duration(remaining),
            tokens=tokens_total,
        )

    @staticmethod
    def _format_duration(seconds: float | None) -> str:
        if seconds is None or seconds <= 0:
            return "--:--"
        minutes, secs = divmod(int(seconds), 60)
        if minutes >= 60:
            hours, minutes = divmod(minutes, 60)
            return f"{hours:d}:{minutes:02d}"
        return f"{minutes:d}:{secs:02d}"

    @staticmethod
    def _extract_select_value(raw: object) -> str | None:
        if isinstance(raw, str):
            return raw
        value = getattr(raw, "value", None)
        return value if isinstance(value, str) else None

    def _resolve_model(self) -> tuple[str, str, str]:
        """解析当前模型输入，返回 (provider, model_name, model_code)。"""
        raw_model = self.model_input.value.strip()
        bundle = self._config_service.get_bundle()
        if not raw_model:
            raw_model = bundle.default_model

        provider_hint = None
        model_name = raw_model
        if "::" in raw_model:
            provider_hint, model_name = raw_model.split("::", 1)
            model_name = model_name.strip()

        model_name, model_code = resolve_model_input(model_name)
        provider = provider_hint.lower() if provider_hint else get_provider_from_model(model_name)
        # 同步写回标准化的 provider::model 形式
        with suppress(Exception):
            self._set_input_value(self.model_input, f"{provider}::{model_name}")
        return provider, model_name, model_code

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------
    @property
    def input_path_input(self) -> InputPathInput:
        return self.query_one(InputPathInput)

    @property
    def output_path_input(self) -> OutputPathInput:
        return self.query_one(OutputPathInput)

    @property
    def model_input(self) -> ModelInput:
        return self.query_one(ModelInput)

    @property
    def batch_note_input(self) -> BatchNoteInput:
        return self.query_one(BatchNoteInput)

    @property
    def batch_id_input(self) -> BatchIdInput:
        return self.query_one(BatchIdInput)

    @property
    def sequence_input(self) -> SequenceInput:
        return self.query_one(SequenceInput)

    @property
    def output_filename_input(self) -> OutputFilenameInput:
        return self.query_one(OutputFilenameInput)

    @property
    def command_input(self) -> CommandInput:
        return self.query_one(CommandInput)

    @property
    def note_input(self) -> NoteInput:
        return self.query_one(NoteInput)

    @property
    def log_view(self) -> RichLog:
        return self.query_one("#log-view", RichLog)

    @property
    def action_button(self) -> Button:
        return self.query_one("#action-button", Button)

    @property
    def feature_toggles(self) -> ReanimatorFeatureToggles:
        return self.query_one("#feature-toggles", ReanimatorFeatureToggles)

    @property
    def terms_table(self) -> TermsTable:
        return self.query_one(TermsTable)

    @property
    def provider_select(self) -> ProviderSelectionInput:
        return self.query_one(ProviderSelectionInput)

    @property
    def model_select(self) -> ModelSelectionInput:
        return self.query_one(ModelSelectionInput)

    @property
    def total_progress(self) -> CustomProgressBar:
        return self.query_one("#total-progress", CustomProgressBar)

    # ------------------------------------------------------------------
    # Lifecycle / bindings
    # ------------------------------------------------------------------
    def on_mount(self) -> None:
        root_logger = logging.getLogger()
        self._log_handler = build_textual_handler(self.log_view.write)
        root_logger.addHandler(self._log_handler)
        self._database_log_handler = setup_database_logging(
            root_logger,
            self.settings.db_dir / "stat.db",
            level=logging.INFO,
        )
        self.logger.setLevel(logging.INFO)

        import threading

        self._main_thread_id = threading.get_ident()
        self.logger.info("[bold cyan]Reanimator TUI Ready[/bold cyan]")
        self.logger.info("按 [cyan]c[/cyan] 切换并发模式 | 按 [cyan]q[/cyan] 退出")
        with suppress(Exception):
            self.total_progress.reset()
        self._update_rate_limit_bar(None)

    def on_unmount(self) -> None:
        root_logger = logging.getLogger()
        if self._log_handler:
            root_logger.removeHandler(self._log_handler)
            self._log_handler = None
        if self._database_log_handler:
            root_logger.removeHandler(self._database_log_handler)
            self._database_log_handler = None

    @on(Button.Pressed, "#action-button")
    def handle_action_button(self) -> None:
        if self.action_mode == "detect":
            self.run_worker(self._run_detect(), exclusive=True)
        elif self.action_mode == "start":
            self.run_worker(self._run_start(), exclusive=True)

    @on(ProviderSelectionInput.Changed)
    def handle_provider_changed(self, event: ProviderSelectionInput.Changed) -> None:
        if event.select is not self.provider_select:
            return
        provider = self._extract_select_value(event.value)
        if not provider:
            provider = self._current_provider
        self._refresh_model_select(provider)
        self.logger.info(f"已切换厂商为 {provider}")

    @on(ModelSelectionInput.Changed)
    def handle_model_selected(self, event: ModelSelectionInput.Changed) -> None:
        if event.select is not self.model_select:
            return
        model_value = self._extract_select_value(event.value)
        self._apply_model_choice(model_value)

    @on(ReanimatorDirectoryTree.FileSelected)
    def handle_file_selected(self, event: ReanimatorDirectoryTree.FileSelected) -> None:
        path = event.path
        if not path.is_file() or path.suffix.lower() != ".csv":
            self.logger.warning("请选择 CSV 文件")
            return

        self._selected_file = path
        self._set_input_value(self.input_path_input, str(path.parent))
        try:
            sequence_preview = str(WordID(parse_word_index_from_filename(path.stem)))
            self._set_input_value(self.sequence_input, sequence_preview)
        except ValueError as exc:
            self.logger.error(str(exc))
            self._set_input_value(self.sequence_input, "")

        self.logger.info(f"已选择文件: [cyan]{path.name}[/cyan]")

    @on(Input.Changed, "#input-directory")
    async def handle_input_path_changed(self, event: Input.Changed) -> None:
        if self._suspend_change_events:
            return
        raw_value = event.value.strip()
        if not raw_value:
            self.logger.warning("输入路径不能为空")
            return
        path = Path(raw_value).expanduser()
        if not path.exists() or not path.is_dir():
            self.logger.error("输入路径无效：%s", path)
            return

        await self._swap_directory_tree(path)
        self._set_input_value(self.input_path_input, str(path.resolve()))
        self._selected_file = None
        self._set_input_value(self.sequence_input, "")
        self.logger.info("已更新输入路径至：%s", path)

    @on(Input.Submitted, "#input-directory")
    async def handle_input_path_submitted(self, event: Input.Submitted) -> None:
        await self.handle_input_path_changed(Input.Changed(event.input, event.value))

    @on(Input.Blurred, "#input-directory")
    async def handle_input_path_blur(self, event: Input.Blurred) -> None:
        value = event.value.strip()
        if value:
            normalized = str(Path(value).expanduser().resolve())
            self._set_input_value(self.input_path_input, normalized)

    @on(Input.Blurred, "#output-directory")
    def handle_output_path_blur(self, event: Input.Blurred) -> None:
        value = event.value.strip()
        if value:
            normalized = str(Path(value).expanduser().resolve())
            self._set_input_value(self.output_path_input, normalized)

    @on(Input.Changed, "#reanimator-config-default-input-dir")
    @on(Input.Changed, "#reanimator-config-default-output-dir")
    @on(Input.Changed, "#reanimator-config-default-model")
    @on(Input.Changed, "#reanimator-config-max-concurrent")
    @on(Input.Changed, "#reanimator-config-max-retries")
    @on(Input.Changed, "#reanimator-config-term-list-path")
    def handle_config_field_changed(self, event: Input.Changed) -> None:
        widget_id = event.input.id
        value = event.value.strip()
        if not value:
            self.logger.warning("配置项不能为空：%s", widget_id)
            return

        try:
            if widget_id == "reanimator-config-default-input-dir":
                normalized = str(Path(value).expanduser().resolve())
                self._config_service.update_paths(input_dir=normalized)
                self.logger.info("默认输入路径已更新为：%s", normalized)
            elif widget_id == "reanimator-config-default-output-dir":
                normalized = str(Path(value).expanduser().resolve())
                self._config_service.update_paths(output_dir=normalized)
                self.logger.info("默认输出路径已更新为：%s", normalized)
            elif widget_id == "reanimator-config-default-model":
                if "::" not in value:
                    self.logger.error("默认模型格式应为 Provider::model，例如 OpenAI::gpt-4o")
                    return
                self._config_service.set_config("default_model", value)
                self.logger.info("默认模型已更新为：%s", value)
            elif widget_id == "reanimator-config-max-concurrent":
                num = int(value)
                if num < 1 or num > 20:
                    raise ValueError("并发数必须在1-20之间")
                self._config_service.set_config("max_concurrent", str(num))
                self.logger.info("并发数已更新为：%d", num)
            elif widget_id == "reanimator-config-max-retries":
                num = int(value)
                if num < 0 or num > 10:
                    raise ValueError("重试次数必须在0-10之间")
                self._config_service.set_config("max_retries", str(num))
                self.logger.info("重试次数已更新为：%d", num)
            elif widget_id == "reanimator-config-term-list-path":
                normalized = str(Path(value).expanduser())
                self._config_service.set_config("term_list_path", normalized)
                self.logger.info("术语表路径已更新为：%s", normalized)
        except ValueError as exc:
            self.logger.error(str(exc))

    @on(ReanimatorFeatureToggles.ToggleChanged)
    def handle_toggle_changed(self, event: ReanimatorFeatureToggles.ToggleChanged) -> None:
        self._config_service.update_feature_flags(enable_concurrent=event.new_value)
        status = "已启用" if event.new_value else "已禁用"
        self.logger.info(f"并行模式{status}")

    def action_quit_app(self) -> None:
        self.app.exit()

    def action_toggle_concurrent(self) -> None:
        flags = self._config_service.get_feature_flags()
        new_value = not flags.enable_concurrent
        self._config_service.update_feature_flags(enable_concurrent=new_value)
        self.feature_toggles.update_toggle(new_value)
        status = "已启用" if new_value else "已禁用"
        self.logger.info(f"并行模式{status}")

    @on(Input.Changed, "#model-input")
    def handle_model_input_changed(self, event: Input.Changed) -> None:
        if self._suspend_change_events:
            return
        if event.input is not self.model_input:
            return
        self._refresh_detection_model()

    # ------------------------------------------------------------------
    # Detect
    # ------------------------------------------------------------------
    async def _run_detect(self) -> None:
        try:
            if not self._selected_file:
                self.logger.error("请先在右侧选择 CSV 文件")
                return

            input_path = self._selected_file
            if not input_path.exists():
                self.logger.error(f"输入文件不存在: {input_path}")
                return
            if input_path.suffix.lower() != ".csv":
                self.logger.error("仅支持 CSV 文件：%s", input_path.name)
                return

            self.logger.info("\n[bold yellow]═══ Detect 阶段开始 ═══[/bold yellow]")

            terms = CSVTermRepository.read_input(input_path)
            self.logger.info(f"共检测到 [cyan]{len(terms)}[/cyan] 个术语")

            start_word_index = parse_word_index_from_filename(input_path.stem)
            for idx, term in enumerate(terms):
                term.word_id = str(WordID(start_word_index + idx))

            batch_note = self.batch_note_input.value.strip()
            for term in terms:
                if batch_note and not term.batch_note:
                    term.batch_note = batch_note

            extra_note = self.note_input.value.strip()
            provider, model_name, model_code = self._resolve_model()

            output_dir_input = (
                self.output_path_input.value.strip()
                or str(self._config_service.get_paths().output_dir or (self.settings.db_dir.parent / "misc/output/reanimator"))
            )
            output_dir = Path(output_dir_input).expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)

            generator = BatchIDGenerator(
                output_dir=output_dir,
                timezone=self.settings.batch_timezone,
            )
            batch_id = self.batch_id_input.value.strip()
            if not batch_id:
                batch_id = generator.generate(len(terms))
            else:
                batch_id = format_batch_id(batch_id)
            self.batch_id_input.value = batch_id
            self.sequence_input.value = str(WordID(start_word_index))

            output_filename = self.output_filename_input.value.strip()
            if not output_filename:
                output_filename = generate_output_filename(batch_id, model_code, input_path.name, "csv")
                self.output_filename_input.value = output_filename

            term_rows: list[TermRow] = []
            row_map: dict[str, TermRow] = {}
            for index, term in enumerate(terms, start=1):
                row = TermRow(
                    row_key=f"row-{index}",
                    index=index,
                    word_id=term.word_id or str(WordID(start_word_index + index - 1)),
                    wm_pair=term.wm_pair,
                    field=term.field or "",
                )
                term_rows.append(row)
                row_map[row.word_id] = row

            self.terms_table.terms = term_rows
            self._rows = {row.index: row for row in term_rows}

            self._detection = DetectionResult(
                file_path=input_path,
                terms=terms,
                model=model_name,
                model_code=model_code,
                provider=provider,
                batch_id=batch_id,
                batch_note=batch_note,
                extra_note=extra_note,
                start_word_index=start_word_index,
                output_filename=output_filename,
                output_dir=output_dir,
                detected_at=datetime.now(),
                term_rows=term_rows,
                row_map=row_map,
            )

            self.action_mode = "start"
            self.action_button.label = "Start"
            self.action_button.variant = "success"
            self.logger.info("[bold green]Detect 完成，点击 Start 开始处理[/bold green]")

        except Exception as exc:  # noqa: BLE001
            self.logger.error(f"Detect 失败: {exc}")
            import traceback

            self.logger.error(traceback.format_exc())

    # ------------------------------------------------------------------
    # Start
    # ------------------------------------------------------------------
    async def _run_start(self) -> None:
        try:
            if not self._detection:
                self.logger.error("未检测到输入，请先运行 Detect")
                return

            self.logger.info("\n[bold yellow]═══ Start 阶段开始 ═══[/bold yellow]")
            self.action_mode = "running"
            self.action_button.disabled = True

            total_terms = len(self._detection.terms)
            self.total_progress.reset()
            self.total_progress.update_progress(
                current=0,
                total=total_terms,
                elapsed_time="0:00",
                remaining_time="--:--",
                tokens=0,
            )
            self._update_rate_limit_bar(None)

            flags = self._config_service.get_feature_flags()
            concurrent_enabled = flags.enable_concurrent
            mode_str = "并发" if concurrent_enabled else "串行"
            self.logger.info(f"处理模式: [cyan]{mode_str}[/cyan]")

            provider = self._create_llm_provider(
                provider=self._detection.provider,
                model=self._detection.model,
            )
            if not provider:
                self.logger.error("无法创建 LLM Provider")
                self._reset_to_detect()
                return

            llm_adapter = ReanimatorLLMAdapter(provider)
            term_list_adapter = TermListAdapter.from_settings(self.settings)

            tuning = self._config_service.get_runtime_tuning()
            max_concurrent = tuning.max_concurrent if isinstance(tuning.max_concurrent, int) else 3
            max_retries = tuning.max_retries if isinstance(tuning.max_retries, int) else 3
            retry_config = self._config_service.get_retry_config()
            extra_note = self.note_input.value.strip()
            prompt_note = self._detection.batch_note.strip()
            if extra_note:
                prompt_note = f"{prompt_note}\n{extra_note}" if prompt_note else extra_note
            self._current_prompt_note = prompt_note

            if concurrent_enabled:
                use_case = ConcurrentProcessTermsUseCase(
                    llm=llm_adapter,
                    term_list=term_list_adapter,
                    start_word_index=self._detection.start_word_index,
                    batch_id=self._detection.batch_id,
                    batch_note=prompt_note,
                    max_concurrent=max_concurrent,
                    max_retries=max_retries,
                    retry_config=retry_config,
                )
            else:
                use_case = ProcessTermsUseCase(
                    llm=llm_adapter,
                    term_list=term_list_adapter,
                    start_word_index=self._detection.start_word_index,
                    batch_id=self._detection.batch_id,
                    batch_note=prompt_note,
                    max_retries=max_retries,
                    retry_config=retry_config,
                )

            self._run_start_time = perf_counter()
            if concurrent_enabled:
                result = await use_case.execute(
                    self._detection.terms,
                    show_progress=False,
                    progress_callback=self._handle_progress_event,
                )
            else:
                result = await asyncio.to_thread(
                    use_case.execute,
                    self._detection.terms,
                    False,
                    self._handle_progress_event,
                )
            elapsed = perf_counter() - self._run_start_time
            self._total_tokens = result.token_usage

            self.logger.info(f"成功: {result.success_count}/{result.total_count}")
            self.logger.info(f"用时: {elapsed:.2f}s | Tokens: {self._total_tokens.total_tokens:,}")
            self._update_progress_summary(elapsed, result.success_count, result.total_count or total_terms)

            self._handle_outputs(result.items)

        except ValueError as exc:
            self.logger.error(str(exc))
            self._reset_to_detect()
        except Exception as exc:  # noqa: BLE001
            self.logger.error(f"Start 失败: {exc}")
            import traceback

            self.logger.error(traceback.format_exc())
            self._reset_to_detect()

    def _handle_outputs(self, outputs: list[TermOutput]) -> None:
        assert self._detection is not None

        conflicts: list[TermOutput] = []
        pending_saves: list[TermOutput] = []
        row_map = self._detection.row_map

        for term_input, output in zip(self._detection.terms, outputs, strict=False):
            row = row_map.get(output.word_id)
            note = term_input.batch_note or self._current_prompt_note

            self.terms_table.update_term_status(row.row_key, "Done", field_value=output.field) if row else None

            self._stats_repo.save_reanimator_processing_log(
                word_id=output.word_id,
                wm_pair=output.wm_pair,
                word_en=output.word_en,
                mean_zh=output.mean_zh,
                model=f"{self._detection.provider}::{self._detection.model}",
                batch_id=self._detection.batch_id,
                batch_note=note,
                have_def_en=bool(term_input.def_en),
                have_example=bool(term_input.example),
                have_rarity=bool(term_input.rarity),
                have_field=bool(term_input.field),
                note=note,
                pos=output.pos,
                ipa=output.ipa,
                etymo_en=output.etymo_en,
                etymo_zh=output.etymo_zh,
                picture=output.picture,
                input_tokens=self._total_tokens.prompt_tokens,
                output_tokens=self._total_tokens.completion_tokens,
                processing_time=None,
                has_error=False,
            )

            existing = self._stats_repo.get_reanimator_entry(output.word_id)
            if existing and existing.get("no_overwrite"):
                self.logger.warning(f"[yellow]{output.word_id} 已被锁定 (no_overwrite)，跳过写入[/yellow]")
                if row:
                    self.terms_table.update_term_status(row.row_key, "Skipped")
                continue

            if existing:
                conflicts.append(output)
                if row:
                    self.terms_table.update_term_status(row.row_key, "Conflict")
            else:
                pending_saves.append(output)

        if pending_saves:
            saved = self._save_outputs(pending_saves)
            self.logger.info(f"已保存 {saved}/{len(pending_saves)} 条记录到 Bank")

        if conflicts:
            self._conflict_terms = conflicts
            self._waiting_for_overwrite_confirmation = True
            self.logger.warning(
                f"检测到 {len(conflicts)} 个词号已存在，输入 /yes 覆盖，/no 取消"
            )
            for conflict in conflicts[:5]:
                self.logger.warning(f"  - {conflict.word_id}: {conflict.wm_pair}")

            self._write_output_file(outputs)
        else:
            self._write_output_file(outputs)
            self._reset_to_detect()

        # 在有冲突等待覆盖确认时，保持当前检测状态，避免清空 _detection。

    def _write_output_file(self, outputs: list[TermOutput]) -> None:
        assert self._detection is not None
        output_path = unique_path(self._detection.output_dir / self._detection.output_filename)
        CSVTermRepository.write_output(output_path, outputs)
        self.logger.info(f"输出文件：{output_path}")

    def _save_outputs(self, outputs: list[TermOutput]) -> int:
        assert self._detection is not None
        saved = 0
        for output in outputs:
            success = self._stats_repo.save_reanimator_bank(
                word_id=output.word_id,
                batch_id=self._detection.batch_id,
                model=f"{self._detection.provider}::{self._detection.model}",
                wm_pair=output.wm_pair,
                word_en=output.word_en,
                mean_zh=output.mean_zh,
                def_en=output.def_en,
                example=output.example,
                rarity=output.rarity,
                field=output.field,
                batch_note=self._detection.batch_note,
                ipa=output.ipa,
                pos=output.pos,
                etymo_en=output.etymo_en,
                etymo_zh=output.etymo_zh,
                picture=output.picture,
                no_overwrite=False,
            )
            if success:
                saved += 1
                row = self._detection.row_map.get(output.word_id)
                if row:
                    self.terms_table.update_term_status(row.row_key, "Saved", field_value=output.field)
        return saved

    def _reset_to_detect(self) -> None:
        self.action_mode = "detect"
        self.action_button.label = "Detect"
        self.action_button.variant = "primary"
        self.action_button.disabled = False

        self._detection = None
        self._rows.clear()
        self.terms_table.clear()
        self.total_progress.reset()
        self._update_rate_limit_bar(None)
        self._run_start_time = None
        self._total_tokens = TokenUsage()
        self.sequence_input.value = ""
        self.batch_id_input.value = ""
        self.output_filename_input.value = ""
        self._current_prompt_note = ""

        self._waiting_for_overwrite_confirmation = False
        self._conflict_terms = []

    def _log_recent_bank_entries(self, limit: int = 10) -> None:
        """输出最近的术语库记录，便于在命令面板中快速查看。"""
        entries = self._stats_repo.get_reanimator_bank(limit=limit)
        if not entries:
            self.logger.info("\n[bold cyan]术语库暂无记录[/bold cyan]")
            return

        self.logger.info("\n[bold cyan]术语库最近 %d 条[/bold cyan]", len(entries))
        for entry in entries:
            word_id = entry.get("word_id", "--")
            batch_id = entry.get("batch_id", "--")
            model = entry.get("model", "--")
            wm_pair = entry.get("wm_pair", "--")
            word_en = entry.get("word_en", "--")
            mean_zh = entry.get("mean_zh", "--")
            field = entry.get("field") or "--"
            rarity = entry.get("rarity") or "--"

            self.logger.info("  %s | 批次 %s | %s", word_id, batch_id, model)
            self.logger.info(
                "    %s -> %s | WMPair: %s | Field: %s | Rarity: %s",
                word_en,
                mean_zh,
                wm_pair,
                field,
                rarity,
            )

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------
    @on(Input.Submitted, "#command-input")
    def handle_command_submitted(self, event: Input.Submitted) -> None:
        raw_value = event.value.strip()
        self._set_input_value(self.command_input, "")
        if not raw_value:
            return

        command = raw_value.lower()
        yes_tokens = {"y", "yes", "/yes"}
        no_tokens = {"n", "no", "/no"}

        if self._waiting_for_overwrite_confirmation:
            if command in yes_tokens:
                if self._conflict_terms:
                    saved = self._save_outputs(self._conflict_terms)
                    self.logger.info(f"覆盖完成，成功 {saved}/{len(self._conflict_terms)}")
                self._waiting_for_overwrite_confirmation = False
                self._conflict_terms = []
                self._reset_to_detect()
                return
            if command in no_tokens:
                self.logger.info("[yellow]已取消覆盖[/yellow]")
                self._waiting_for_overwrite_confirmation = False
                self._conflict_terms = []
                self._reset_to_detect()
                return
            self.logger.warning("请输入 /yes (覆盖) 或 /no (跳过)")
            return

        if command == "/clear":
            self.log_view.clear()
            self.logger.info("日志已清空")
        elif command == "/bank":
            self._log_recent_bank_entries()
        elif command == "/exit":
            self.logger.info("收到退出指令，正在关闭应用…")
            self.app.exit()
        elif command in yes_tokens | no_tokens:
            self.logger.warning("当前没有需要确认的操作")
        else:
            self.logger.warning(f"未知命令: {raw_value}")

    @on(Input.Changed, "#command-input")
    def handle_command_changed(self, event: Input.Changed) -> None:
        if self._suspend_change_events:
            return
        self._set_input_value(self.command_input, event.value)

    def on_key(self, event: Key) -> None:
        if event.key == "c":
            event.stop()
            self.action_toggle_concurrent()

    async def _swap_directory_tree(self, path: Path) -> None:
        container = self.query_one("#right-col", Vertical)
        removal = self._file_tree.remove()
        if inspect.isawaitable(removal):
            await removal
        self._file_tree = ReanimatorDirectoryTree(path)
        mount_result = container.mount(self._file_tree, before=self.action_button)
        if inspect.isawaitable(mount_result):
            await mount_result

    def _set_input_value(self, widget: Input, value: str) -> None:
        self._suspend_change_events = True
        try:
            widget.value = value
        finally:
            self._suspend_change_events = False

    # ------------------------------------------------------------------
    # Helper utilities
    # ------------------------------------------------------------------
    def _create_llm_provider(self, provider: str, model: str):
        try:
            temperature = getattr(self.settings, "default_temperature", None)
            if provider == "openai":
                if not self.settings.openai_api_key:
                    self.logger.error("OpenAI API Key 未配置")
                    return None
                return OpenAIProvider(
                    model=model,
                    api_key=self.settings.openai_api_key,
                    temperature=temperature,
                )
            if provider == "anthropic":
                if not getattr(self.settings, "anthropic_api_key", ""):
                    self.logger.error("Anthropic API Key 未配置")
                    return None
                return AnthropicProvider(
                    model=model,
                    api_key=self.settings.anthropic_api_key,
                    temperature=temperature,
                )
            self.logger.error(f"暂不支持的提供商: {provider}")
            return None
        except Exception as exc:  # noqa: BLE001
            self.logger.error(f"创建 LLM Provider 失败: {exc}")
            return None


__all__ = ["ReanimatorScreen"]
