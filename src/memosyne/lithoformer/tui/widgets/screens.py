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
from textual.widgets import Button, Input, ProgressBar, RichLog, Static, TabbedContent, TabPane, TextArea

from ....core.models import TokenUsage
from ....shared.config import get_settings
from .... import __version__
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
    ConfigDefaultInputDirInput,
    ConfigDefaultModelInput,
    ConfigDefaultOutputDirInput,
    ConfigMaxConcurrentInput,
    ConfigMaxRetriesInput,
    ConfigReserved3Input,
    ConfigReserved4Input,
    ConfigReserved5Input,
    ConfigReserved6Input,
    ConfigReserved7Input,
    Feature001Checkbox,
    Feature002Checkbox,
    Feature003Checkbox,
    FeatureConcurrentCheckbox,
    FeatureParsingCheckbox,
    FeatureTranslationCheckbox,
    InputPathInput,
    LithoformerDirectoryTree,
    ModelInput,
    ModelSelectionInput,
    OutputFilenameInput,
    OutputPathInput,
    ProviderSelectionInput,
    SequenceInput,
    NoteInput,
    TitleInput,
)
from .questions_table import QuestionRow, QuestionsTable
from .custom_progress import CustomProgressBar


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
    question_seed: int
    batch_id: str
    output_filename: str
    detected_at: datetime
    questions: list[QuestionRow]


class MainScreen(Screen):
    """Main screen of the Lithoformer TUI application."""

    AUTO_INPUT_IDS = {
        "model-input",
        "note-input",
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
        self._suspend_model_select_events = False
        self._selected_row_index: int | None = None

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
    def note_input(self) -> NoteInput:
        return self.query_one(NoteInput)

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
    def command_input(self) -> CommandInput:
        return self.query_one(CommandInput)

    @property
    def log_view(self) -> RichLog:
        return self.query_one(RichLog)

    @property
    def action_button(self) -> Button:
        return self.query_one("#action-button", Button)

    @property
    def total_progress(self) -> CustomProgressBar:
        return self.query_one("#total-progress", CustomProgressBar)

    @property
    def preview_area(self) -> TextArea:
        return self.query_one("#preview-area", TextArea)

    # endregion -------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        """Compose the main screen layout (完全基于 layout.xml)."""
        # 获取当前日期和时间
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M:%S")
        info_text = f"[b]Memosyne v{__version__}[/] | {date_str} {time_str}"

        # 主容器：左列 + 右侧区域
        with Horizontal(id="main-container"):
            # 左列 (0-760px): LOGO + 信息区 + 题目列表
            with Vertical(id="left-col"):
                # LOGO 和信息区合并在一个容器中
                with Vertical(id="header-area"):
                    yield Static(ASCII_LOGO, id="logo-panel")
                    yield Static(info_text, id="info-panel")
                yield QuestionsTable()

            # 右侧区域 (760-1600px): 包含中列、右列和控制台
            with Vertical(id="right-area"):
                # 顶部：中列 + 右列
                with Horizontal(id="top-section"):
                    # 中列 (760-1320px): 选项卡式内容区
                    with Vertical(id="middle-col"):
                        with TabbedContent(id="main-tabs"):
                            # 第一个选项卡：输入配置
                            with TabPane(title="输入", id="tab-inputs"):
                                yield InputPathInput(value=str(self.settings.lithoformer_input_dir))
                                yield OutputPathInput(value=str(self.settings.lithoformer_output_dir))

                                with Horizontal(id="provider-model-row"):
                                    yield ProviderSelectionInput(value=self.settings.default_llm_provider)
                                    yield ModelSelectionInput()

                                yield ModelInput()
                                yield TitleInput()

                                with Horizontal(id="seq-batch-row"):
                                    yield SequenceInput()
                                    yield BatchInput()

                                yield OutputFilenameInput()
                                yield NoteInput()

                            # 第二个选项卡：预览展示
                            with TabPane(title="预览", id="tab-preview"):
                                preview = TextArea(id="preview-area", read_only=True)
                                preview.border_title = "检测结果预览"
                                yield preview

                            # 第三个选项卡：配置管理
                            with TabPane(title="配置", id="tab-config"):
                                # 从数据库读取配置值
                                config_repo = self.settings._config_repo
                                default_input = config_repo.get("lithoformer_input_dir") if config_repo else ""
                                default_output = config_repo.get("lithoformer_output_dir") if config_repo else ""
                                default_model = config_repo.get("default_model") if config_repo else ""
                                max_concurrent = config_repo.get("max_concurrent") if config_repo else "10"
                                max_retries = config_repo.get("max_retries") if config_repo else "1"
                                reserved_3 = config_repo.get("reserved_config_3") if config_repo else ""
                                reserved_4 = config_repo.get("reserved_config_4") if config_repo else ""
                                reserved_5 = config_repo.get("reserved_config_5") if config_repo else ""
                                reserved_6 = config_repo.get("reserved_config_6") if config_repo else ""
                                reserved_7 = config_repo.get("reserved_config_7") if config_repo else ""

                                yield ConfigDefaultInputDirInput(value=default_input)
                                yield ConfigDefaultOutputDirInput(value=default_output)
                                yield ConfigDefaultModelInput(value=default_model)
                                yield ConfigMaxConcurrentInput(value=max_concurrent)
                                yield ConfigMaxRetriesInput(value=max_retries)
                                yield ConfigReserved3Input(value=reserved_3)
                                yield ConfigReserved4Input(value=reserved_4)
                                yield ConfigReserved5Input(value=reserved_5)
                                yield ConfigReserved6Input(value=reserved_6)
                                yield ConfigReserved7Input(value=reserved_7)

                            # 第四个选项卡：功能开关
                            with TabPane(title="功能", id="tab-features"):
                                # 从数据库读取功能配置
                                from ....shared.infrastructure.config_db import get_feature_config_repository
                                feature_repo = get_feature_config_repository(self.settings.db_dir / "config.db")
                                feature_config = feature_repo.get()

                                # 2x3网格布局
                                with Horizontal(id="feature-row-1"):
                                    yield FeatureTranslationCheckbox(value=feature_config.get("enable_translation", True))
                                    yield FeatureParsingCheckbox(value=feature_config.get("enable_parsing", True))
                                    yield Feature001Checkbox(value=feature_config.get("feature_001", False))

                                with Horizontal(id="feature-row-2"):
                                    yield FeatureConcurrentCheckbox(value=feature_config.get("enable_concurrent", False))
                                    yield Feature002Checkbox(value=feature_config.get("feature_002", False))
                                    yield Feature003Checkbox(value=feature_config.get("feature_003", False))

                    # 右列 (1320-1600px): 文件树 + 按钮
                    with Vertical(id="right-col"):
                        yield self._file_tree
                        yield Button("Detect", id="action-button", variant="primary")

                # 控制台区 (横跨整个右侧区域，760-1600px)
                log_view = RichLog(id="log-view", highlight=True, markup=True)
                log_view.border_title = "控制台"
                if hasattr(log_view, "max_lines"):
                    log_view.max_lines = 999
                yield log_view

                yield CommandInput()

        # 底部：进度条区（使用新的自定义进度条）
        yield CustomProgressBar(total=1, id="total-progress")

    @staticmethod
    def _extract_select_value(raw: object) -> str | None:
        """Extract string value from Textual Select event payloads."""
        if isinstance(raw, str):
            return raw
        value = getattr(raw, "value", None)
        return value if isinstance(value, str) else None

    def _apply_model_select_value(self, value: str) -> None:
        """Set model select value while suppressing change side-effects."""
        self._suspend_model_select_events = True
        try:
            if hasattr(self.model_select, "set_value"):
                try:
                    self.model_select.set_value(value)
                    return
                except Exception:
                    pass
            try:
                self.model_select.action_select(value)
            except Exception:
                self.model_select.value = value
        finally:
            self._suspend_model_select_events = False

    # region lifecycle ------------------------------------------------------------
    async def on_mount(self) -> None:
        """Handle mount event."""
        self._main_thread_id = threading.get_ident()

        handler = build_textual_handler(self._write_log)
        self._log_handler = handler
        logging.getLogger().addHandler(handler)

        # 从数据库读取默认模型并设置provider
        default_model_str = self.settings.get_default_model()
        from memosyne.core.models import Configuration
        config = Configuration(default_model=default_model_str)
        provider, model = config.parse_model()

        # 设置provider选择（会触发Changed事件，自动调用_refresh_model_options）
        self.provider_select.value = provider

        # 注意：不需要显式调用_refresh_model_options，
        # 因为设置provider_select.value会触发handle_provider_changed事件处理器

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
        if event.select is not self.provider_select:
            return
        provider = self._extract_select_value(event.value)
        if not provider:
            provider = self._extract_select_value(getattr(self.provider_select, "value", None)) or "openai"
        # 切换厂商时允许默认模型覆盖先前的手动输入
        self._manual_overrides.discard("model-input")
        self._refresh_model_options(provider)
        self.logger.info("已切换厂商为 %s", provider)

    @on(ModelSelectionInput.Changed)
    async def handle_model_selected(self, event: ModelSelectionInput.Changed) -> None:
        """Populate model input when a model is picked from the dropdown."""
        if event.select is not self.model_select:
            return
        if self._suspend_model_select_events:
            return

        selected_value = self._extract_select_value(event.value)
        if not selected_value:
            return

        provider_raw = getattr(self.provider_select, "value", None)
        provider = self._extract_select_value(provider_raw) or "openai"

        from memosyne.core.models import Configuration

        if selected_value == "others":
            provider_map = {"openai": "OpenAI", "anthropic": "Anthropic"}
            provider_formatted = provider_map.get(provider, provider.capitalize())
            model_display = f"{provider_formatted}::"
            self._set_input_value(self.model_input, model_display)
            log_value = f"{provider_formatted}:: (手动输入)"
            should_refresh_detection = False
        else:
            model_display = Configuration.format_model(provider, selected_value)
            self._set_input_value(self.model_input, model_display)
            log_value = model_display
            should_refresh_detection = True

        # 标记为手动覆盖，防止自动流程覆盖用户的选择
        self._manual_overrides.add(self.model_input.id)
        self.logger.info("已切换模型为 %s", log_value)
        if should_refresh_detection:
            self._refresh_detection_model()

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
        elif command == "/exit":
            self.logger.info("收到退出指令，正在关闭应用…")
            self._set_input_value(self.command_input, "")
            await self.app.action_quit()
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
    @on(Input.Changed, "#note-input")
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

        if widget_id == "sequence-input":
            seed = infer_question_seed(event.value.strip()) if event.value else 0
            self._reassign_question_codes(seed)
        elif widget_id == "model-input":
            self._refresh_detection_model()

    @on(Input.Changed, "#config-default-input-dir")
    @on(Input.Changed, "#config-default-output-dir")
    @on(Input.Changed, "#config-default-model")
    @on(Input.Changed, "#config-max-concurrent")
    @on(Input.Changed, "#config-max-retries")
    @on(Input.Changed, "#config-reserved-3")
    @on(Input.Changed, "#config-reserved-4")
    @on(Input.Changed, "#config-reserved-5")
    @on(Input.Changed, "#config-reserved-6")
    @on(Input.Changed, "#config-reserved-7")
    async def handle_config_changed(self, event: Input.Changed) -> None:
        """Save configuration changes to database (real-time with validation)."""
        widget_id = event.input.id
        value = event.value.strip()

        # 映射widget ID到配置键
        config_key_map = {
            "config-default-input-dir": "lithoformer_input_dir",
            "config-default-output-dir": "lithoformer_output_dir",
            "config-default-model": "default_model",
            "config-max-concurrent": "max_concurrent",
            "config-max-retries": "max_retries",
            "config-reserved-3": "reserved_config_3",
            "config-reserved-4": "reserved_config_4",
            "config-reserved-5": "reserved_config_5",
            "config-reserved-6": "reserved_config_6",
            "config-reserved-7": "reserved_config_7",
        }

        config_key = config_key_map.get(widget_id)
        if not config_key:
            return

        # 验证逻辑
        is_valid = True
        error_message = ""

        if config_key == "max_concurrent":
            if value:
                try:
                    num = int(value)
                    if num < 1 or num > 100:
                        is_valid = False
                        error_message = "并发数必须在1-100之间"
                except ValueError:
                    is_valid = False
                    error_message = "并发数必须为整数"
        elif config_key == "max_retries":
            if value:
                try:
                    num = int(value)
                    if num < 0 or num > 10:
                        is_valid = False
                        error_message = "重试次数必须在0-10之间"
                except ValueError:
                    is_valid = False
                    error_message = "重试次数必须为整数"

        # 更新输入框样式（红色高亮表示无效）
        if not is_valid:
            event.input.add_class("validation-error")
            self.log_view.write(f"[red]验证失败: {error_message}[/red]")
            # 禁用按钮
            self.action_button.disabled = True
            return
        else:
            event.input.remove_class("validation-error")
            # 检查其他输入是否都有效，如果都有效则启用按钮
            self._check_all_validations()

        # 保存到数据库
        if self.settings._config_repo:
            self.settings.save_config(config_key, value)
            self.settings.reload_from_db()

            # 特殊处理：如果修改的是默认模型，同步更新"输入"tab（仅当用户未手动修改时）
            if config_key == "default_model" and value and "model-input" not in self._manual_overrides:
                from memosyne.core.models import Configuration
                config = Configuration(default_model=value)
                provider, model = config.parse_model()

                # 更新provider选择（如果provider改变了）
                current_provider = self._extract_select_value(getattr(self.provider_select, "value", None))
                if current_provider != provider:
                    self.provider_select.value = provider
                    self._refresh_model_options(provider)

                # 更新模型下拉框（如果模型在列表中）
                if model in self._model_option_values:
                    self._apply_model_select_value(model)

                # 更新模型输入框
                self._set_auto_field(self.model_input, value)

            # 记录日志
            self.log_view.write(f"[dim]配置已保存: {config_key} = {value}[/dim]")

    def _check_all_validations(self) -> None:
        """检查所有配置输入是否有效，如果都有效则启用按钮"""
        try:
            # 检查并发数
            max_concurrent_widget = self.query_one("#config-max-concurrent", Input)
            if max_concurrent_widget.value.strip():
                num = int(max_concurrent_widget.value.strip())
                if num < 1 or num > 100:
                    self.action_button.disabled = True
                    return

            # 检查重试次数
            max_retries_widget = self.query_one("#config-max-retries", Input)
            if max_retries_widget.value.strip():
                num = int(max_retries_widget.value.strip())
                if num < 0 or num > 10:
                    self.action_button.disabled = True
                    return

            # 所有验证通过，启用按钮
            self.action_button.disabled = False
        except (ValueError, Exception):
            # 任何异常都禁用按钮
            self.action_button.disabled = True

    @on(FeatureTranslationCheckbox.Changed)
    @on(FeatureParsingCheckbox.Changed)
    @on(FeatureConcurrentCheckbox.Changed)
    @on(Feature001Checkbox.Changed)
    @on(Feature002Checkbox.Changed)
    @on(Feature003Checkbox.Changed)
    async def handle_feature_changed(self, event) -> None:
        """保存功能配置到数据库（实时）"""
        from textual.widgets import Checkbox
        from ....shared.infrastructure.config_db import get_feature_config_repository

        if not isinstance(event.checkbox, Checkbox):
            return

        widget_id = event.checkbox.id
        is_checked = event.value

        # 映射widget ID到功能字段
        feature_key_map = {
            "feature-translation": "enable_translation",
            "feature-parsing": "enable_parsing",
            "feature-concurrent": "enable_concurrent",
            "feature-001": "feature_001",
            "feature-002": "feature_002",
            "feature-003": "feature_003",
        }

        feature_key = feature_key_map.get(widget_id)
        if feature_key:
            # 保存到数据库
            feature_repo = get_feature_config_repository(self.settings.db_dir / "config.db")
            feature_repo.update(**{feature_key: is_checked})

            # 记录日志
            status = "启用" if is_checked else "禁用"
            self.log_view.write(f"[dim]功能已更新: {feature_key} = {status}[/dim]")

    @on(QuestionsTable.RowHighlighted)
    def handle_question_row_highlighted(self, event: QuestionsTable.RowHighlighted) -> None:
        """Update the preview area when the highlighted row changes."""
        index = event.row_index or self._index_from_row_key(event.row_key)
        if index:
            self._show_question_preview(index)

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

        # 在Start开始时就记录备注值，帮助调试
        current_note = self.note_input.value.strip()
        if current_note:
            self.logger.info("START开始 - 当前备注框内容：%s", current_note)
        else:
            self.logger.info("START开始 - 备注框为空")

        detection = self._detection

        # 读取功能配置
        from ....shared.infrastructure.config_db import get_feature_config_repository, get_stats_repository
        from ...domain.models import FeatureConfig

        feature_repo = get_feature_config_repository(self.settings.db_dir / "config.db")
        feature_dict = feature_repo.get()

        # 读取并发配置
        config_repo = self.settings._config_repo
        max_concurrent = int(config_repo.get("max_concurrent") or "10") if config_repo else 10
        max_retries = int(config_repo.get("max_retries") or "1") if config_repo else 1

        # 构建FeatureConfig
        feature_config = FeatureConfig(
            enable_translation=feature_dict.get("enable_translation", True),
            enable_parsing=feature_dict.get("enable_parsing", True),
            enable_concurrent=feature_dict.get("enable_concurrent", False),
            max_concurrent=max_concurrent,
            max_retries=max_retries,
            feature_001=feature_dict.get("feature_001", False),
            feature_002=feature_dict.get("feature_002", False),
            feature_003=feature_dict.get("feature_003", False),
        )

        # 获取stats repository（使用独立的stat.db）
        stats_repo = get_stats_repository(self.settings.db_dir / "stat.db")

        # 构建模型标识（格式：Provider::model）
        from memosyne.core.models import Configuration
        model_identifier = Configuration.format_model(detection.provider, detection.model_id)

        try:
            adapter = self._create_llm_adapter(detection.provider, detection.model_id, feature_config)
        except Exception as exc:
            self.logger.error("创建 LLM Provider 失败：%s", exc)
            return

        self.action_mode = "running"
        self._set_action_state("running")
        self._set_status("状态：解析中…")
        self._run_start_time = perf_counter()
        self._processed_count = 0
        self._total_tokens = 0

        # 根据并发开关选择UseCase
        if feature_config.enable_concurrent:
            from ...application.use_cases import ConcurrentParseQuizUseCase
            use_case = ConcurrentParseQuizUseCase(
                llm=adapter,
                feature_config=feature_config,
                stats_repo=stats_repo,
                model_identifier=model_identifier,
                output_filename=detection.output_filename,
            )
            self.logger.info(f"使用并发处理模式（并发数：{feature_config.max_concurrent}，重试次数：{feature_config.max_retries}）")
        else:
            use_case = ParseQuizUseCase(
                llm=adapter,
                stats_repo=stats_repo,
                feature_config=feature_config,
                model_identifier=model_identifier,
                output_filename=detection.output_filename,
            )
            self.logger.info("使用顺序处理模式")

        formatter = FormatterAdapter.create()
        file_adapter = FileAdapter.create()

        if self._run_task:
            self.logger.warning("解析任务仍在运行，忽略新的 START 请求")
            return

        self._run_task = asyncio.create_task(
            self._process_questions(detection, use_case, formatter, file_adapter, feature_config),
            name="LithoformerRunTask",
        )

    async def _process_questions(
        self,
        detection: DetectionResult,
        use_case,  # ParseQuizUseCase or ConcurrentParseQuizUseCase
        formatter: FormatterAdapter,
        file_adapter: FileAdapter,
        feature_config,
    ) -> None:
        """Background task that processes questions (sequential or concurrent)."""
        try:
            items: list = []
            total_questions = len(detection.questions)
            running_tokens = TokenUsage()

            # 从title_input读取用户可能修改过的标题
            title_from_input = self.title_input.value.strip()
            if title_from_input:
                # 将\\n转换为真正的\n
                title_from_input = title_from_input.replace("\\n", "\n")
                # 分割为main和sub
                title_lines = [line.strip() for line in title_from_input.split("\n") if line.strip()]
                if len(title_lines) >= 2:
                    final_title_main = title_lines[0]
                    final_title_sub = "\n".join(title_lines[1:])
                elif len(title_lines) == 1:
                    final_title_main = title_lines[0]
                    final_title_sub = ""
                else:
                    final_title_main = detection.title_main
                    final_title_sub = detection.title_sub
            else:
                final_title_main = detection.title_main
                final_title_sub = detection.title_sub

            # 读取备注（用户自定义的额外说明，会附加到user prompt）
            user_note = self.note_input.value.strip()
            if user_note:
                self.logger.info("读取到用户备注：%s", user_note)

            # 并发模式：使用回调实时更新UI
            if feature_config.enable_concurrent:
                from ...application.use_cases import ConcurrentParseQuizUseCase
                if isinstance(use_case, ConcurrentParseQuizUseCase):
                    self.logger.info("并发处理中，请稍候...")
                    self._set_status(f"状态：并发解析中（{feature_config.max_concurrent}线程）...")

                    # 构建markdown（需要note注入到每个block）
                    markdown_content = self._reconstruct_markdown(detection.blocks)

                    # 定义回调函数，用于实时更新UI
                    def on_event(event: QuizProcessingEvent):
                        """每个题目处理完成时的回调"""
                        # 更新row状态
                        self._apply_event_to_row(event, formatter, final_title_main, final_title_sub)

                        # 更新items列表（只保存成功的）
                        if event.status == "success" and event.item:
                            items.append(event.item)

                        # 累计tokens
                        nonlocal running_tokens
                        running_tokens = running_tokens + event.tokens

                        # 更新计数和UI
                        self._processed_count += 1
                        self._total_tokens = running_tokens.total_tokens
                        self._update_total_progress(self._processed_count, total_questions)
                        self._refresh_stats(total_questions)

                    try:
                        result = await use_case.execute_async(
                            markdown_content,
                            show_progress=False,
                            on_event_callback=on_event
                        )

                        # execute_async完成后，items已经通过回调填充
                        running_tokens = result.token_usage

                        self.logger.info(f"并发处理完成：成功 {result.success_count}/{result.total_count} 题")

                    except Exception as exc:
                        self.logger.error(f"并发处理失败：{exc}")
                        self._set_status("状态：并发解析失败")
                        self.action_mode = "detect"
                        self._set_action_state("detect")
                        return

                    # 跳过循环，直接到写入文件阶段
                else:
                    self.logger.error("并发模式但UseCase类型不匹配")
                    return
            else:
                # 顺序模式：原有逻辑
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
                            note=user_note,
                            show_spinner=False,
                        )
                    except Exception as exc:  # pragma: no cover - defensive
                        self.logger.error("解析过程中发生错误：%s", exc)
                        self._set_status("状态：解析失败")
                        self.action_mode = "detect"
                        self._set_action_state("detect")
                        return

                    self._apply_event_to_row(event, formatter, final_title_main, final_title_sub)
                    if event.status == "success" and event.item:
                        items.append(event.item)

                    self._processed_count += 1
                    self._total_tokens = running_tokens.total_tokens
                    self._update_single_progress(done=True)
                    self._update_total_progress(self._processed_count, total_questions)
                    self._refresh_stats(total_questions)
                    await asyncio.sleep(0)

            try:
                output_dir_raw = self.output_path_input.value.strip()
                output_dir = Path(output_dir_raw) if output_dir_raw else self.settings.lithoformer_output_dir
                if not output_dir.is_absolute():
                    output_dir = Path.cwd() / output_dir

                if self.settings.is_sample_path(output_dir):
                    self.logger.error("当前输出目录位于 misc 示例资源中（只读）。请在输入框或 config/paths.json 中指定可写目录。")
                    self._set_status("状态：输出路径不可写")
                    self.action_mode = "detect"
                    self._set_action_state("detect")
                    return

                output_dir.mkdir(parents=True, exist_ok=True)
                output_path = unique_path(output_dir / detection.output_filename)
                sequence_source = self.sequence_input.value.strip() or detection.sequence

                # 使用之前解析好的final_title_main和final_title_sub
                output_text = formatter.format(
                    items,
                    final_title_main,
                    final_title_sub,
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
        question_seed = infer_question_seed(sequence) if sequence else infer_question_seed(file_path)

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
            number = self._format_question_code(question_seed, index)
            if not number:
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
            question_seed=question_seed,
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

        self._reassign_question_codes(detection.question_seed)

        if detection.questions:
            self._selected_row_index = 1
            self._show_question_preview(1)
        else:
            self._selected_row_index = None
            self._set_preview_text("")

        self._set_meta_title(detection.title_main or "—")

        # 组合完整标题：title_main + \n + title_sub
        title_parts = []
        if detection.title_main:
            title_parts.append(detection.title_main)
        if detection.title_sub:
            title_parts.append(detection.title_sub)
        full_title = "\\n".join(title_parts)  # 使用 \\n 作为换行标记

        self._set_auto_field(self.title_input, full_title)
        # 备注字段默认为空（不再填入title_sub）
        # self._set_auto_field(self.note_input, "")  # 不需要设置，保持用户输入
        self._set_auto_field(self.sequence_input, detection.sequence or "")
        self._set_auto_field(self.batch_input, detection.batch_id)
        self._set_auto_field(self.output_filename_input, detection.output_filename)

        if detection.model_code:
            self._set_auto_field(self.model_input, detection.model_code)
            # 如果model_code在下拉列表中，也更新下拉选择
            if detection.model_code in self._model_option_values:
                self._apply_model_select_value(detection.model_code)

        self._update_analysis_summary(detection)

        # 确保检测结果的模型配置与当前输入保持同步
        self._refresh_detection_model()

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

        self._selected_row_index = None
        self._set_preview_text("")

        # 清理手动覆盖标记和自动值缓存，让新文件可以正确更新字段
        self._manual_overrides.clear()
        self._auto_values.clear()

    def _update_analysis_summary(self, detection: DetectionResult | None) -> None:
        """Render a compact summary of the detection outcome (deprecated)."""
        # analysis_panel 已被移除，解析摘要现在通过日志显示
        if detection is None:
            return

        provider_label = detection.provider.title() if detection.provider else "—"
        summary_lines = [
            f"文件: {detection.file_path.name}",
            f"题目数: {len(detection.questions)}",
            f"厂商: {provider_label}",
            f"主标题: {detection.title_main or '—'}",
            f"副标题: {detection.title_sub or '—'}",
            f"模型: {detection.model_id}",
            f"批次号: {detection.batch_id}",
            f"输出文件: {detection.output_filename}",
            f"检测时间: {detection.detected_at.strftime('%H:%M:%S')}",
        ]
        # 输出到日志
        self.logger.info("检测摘要:\n" + "\n".join(summary_lines))

    def _refresh_detection_model(self) -> None:
        """Update detection model info and output filename based on current input."""
        if not self._detection:
            return
        try:
            provider, model_id, model_code = self._resolve_model()
        except Exception as exc:
            self.logger.debug("解析模型输入失败，保持原配置：%s", exc)
            return

        detection = self._detection
        old_code = detection.model_code
        old_filename = detection.output_filename

        detection.provider = provider
        detection.model_id = model_id
        detection.model_code = model_code
        new_output_filename = generate_output_filename(
            batch_id=detection.batch_id,
            model_code=model_code,
            input_filename=detection.file_path.name,
            ext="txt",
        )
        detection.output_filename = new_output_filename
        self._set_auto_field(self.output_filename_input, detection.output_filename)

        if old_code != model_code or old_filename != new_output_filename:
            self.logger.info(
                "检测配置已更新：模型 %s，输出文件名调整为 %s",
                model_code,
                detection.output_filename,
            )

    # endregion ------------------------------------------------------------------

    # region parsing helpers ------------------------------------------------------
    def _reassign_question_codes(self, seed: int) -> None:
        """Recalculate display question codes based on the provided seed."""
        if not self._detection or not self._rows:
            return

        effective_seed = seed if seed and seed > 0 else 0
        for index in sorted(self._rows):
            row = self._rows[index]
            if effective_seed > 0:
                number = self._format_question_code(effective_seed, index)
            else:
                block = self._detection.blocks[index - 1]
                number = self._guess_question_number(block, index)
            row.number = number
            self.questions_table.update_cell(row.row_key, "number", number)

        self._detection.question_seed = effective_seed

        if self._selected_row_index:
            self._show_question_preview(self._selected_row_index)

    def _show_question_preview(self, row_index: int) -> None:
        """Render the full original question markdown in the preview tab."""
        if not self._detection or row_index < 1 or row_index > len(self._detection.blocks):
            self._set_preview_text("")
            self._selected_row_index = None
            return

        self._selected_row_index = row_index

        block = self._detection.blocks[row_index - 1]
        preview_text = self._compose_block_preview(block)
        row = self._rows.get(row_index)
        number = row.number if row else ""
        if number:
            preview_text = f"{number}\n\n{preview_text}" if preview_text else number

        self._set_preview_text(preview_text)

    @staticmethod
    def _compose_block_preview(block: dict[str, str]) -> str:
        """Compose a readable preview string from the original block data."""
        context = (block.get("context") or "").strip()
        question = block.get("question") or ""
        answer = block.get("answer") or ""

        lines: list[str] = []
        if context:
            lines.append(context)
        if question:
            lines.append("```Question")
            lines.append(question.rstrip())
            lines.append("```")
        if answer:
            lines.append("```Answer")
            lines.append(answer.rstrip())
            lines.append("```")

        return "\n".join(lines)

    def _set_preview_text(self, text: str) -> None:
        """Safely update the preview widget text across Textual versions."""
        preview = self.preview_area
        if hasattr(preview, "value"):
            preview.value = text
        elif hasattr(preview, "load_text"):
            preview.load_text(text)
        else:
            preview.update(text)

    @staticmethod
    def _index_from_row_key(row_key: str | None) -> int:
        """Extract the numeric index from a DataTable row key."""
        if not row_key:
            return 0
        if row_key.startswith("row-"):
            _, _, suffix = row_key.partition("-")
            try:
                return int(suffix)
            except ValueError:
                return 0
        try:
            return int(row_key)
        except ValueError:
            return 0

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

    def _mark_row_success(self, index: int) -> None:
        """Mark the row as successfully processed."""
        row = self._rows.get(index)
        if not row:
            return
        row.status = "Done"
        self.questions_table.update_question_status(row.row_key, "Done")

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
        """Reset progress bar."""
        self.total_progress.reset()
        if total > 0:
            self.total_progress._total = total

    def _update_single_progress(self, *, reset: bool = False, done: bool = False) -> None:
        """Deprecated: Single progress bar no longer exists."""
        pass

    def _update_total_progress(self, completed: int, total: int) -> None:
        """Update the total progress indicator."""
        elapsed = (perf_counter() - self._run_start_time) if self._run_start_time else 0.0
        remaining = self._estimate_remaining_time(elapsed, completed, total)

        self.total_progress.update_progress(
            current=completed,
            total=total,
            elapsed_time=self._format_seconds(elapsed),
            remaining_time=remaining,
            tokens=self._total_tokens
        )

    def _set_status(self, text: str) -> None:
        """Update status message (deprecated: status is shown in progress bar)."""
        # 状态信息现在显示在进度条中，这里只记录日志
        pass

    def _refresh_stats(self, total: int) -> None:
        """Refresh statistics display based on current counters."""
        # 统计信息现在在 _update_total_progress 中更新
        pass

    def _set_stats_text(self, completed: int, total: int, elapsed: float, remaining: str, tokens: int) -> None:
        """Render the stats text (deprecated: stats are shown in progress bar)."""
        # 统计信息现在显示在进度条中
        pass

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
        container = self.query_one("#right-col", Vertical)
        removal = self._file_tree.remove()
        if inspect.isawaitable(removal):
            await removal
        self._file_tree = LithoformerDirectoryTree(path)
        action_button = self.action_button
        mount_result = container.mount(self._file_tree, before=action_button)
        if inspect.isawaitable(mount_result):
            await mount_result

    def _set_meta_title(self, title: str) -> None:
        # Meta title removed in new layout
        pass

    def _update_meta_file(self, path: Path) -> None:
        # Meta file removed in new layout
        pass

    def _update_selected_file_display(self, path: Path) -> None:
        # Selected file display removed in new layout
        pass

    # endregion ------------------------------------------------------------------

    # region validation & utility helpers ---------------------------------------
    def _validate_before_start(self) -> bool:
        """Ensure all required fields are populated before START."""
        required = {
            "输入路径": self.input_path_input.value.strip(),
            "输出路径": self.output_path_input.value.strip(),
            "模型": self.model_input.value.strip(),
            "标题": self.title_input.value.strip(),
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
        provider_models = models.get(provider)
        if provider_models is None:
            self.logger.warning("未知厂商 %s，保持现有模型列表", provider)
            return

        # 添加所有模型选项 + "Others"选项
        options = [(model, model) for model in provider_models]
        options.append(("Others (手动输入)", "others"))

        # 从数据库读取默认模型
        default_model_str = self.settings.get_default_model()  # 格式：Provider::model
        from memosyne.core.models import Configuration
        config = Configuration(default_model=default_model_str)
        db_provider, db_model = config.parse_model()

        # 如果数据库中的provider与当前provider匹配，则使用数据库中的模型
        if db_provider == provider:
            default_model = db_model
        else:
            # 否则使用环境变量中的默认模型
            default_model = (
                self.settings.default_openai_model if provider == "openai" else self.settings.default_anthropic_model
            )

        # 设置选项（会触发watch_models清除并重新设置）
        self.model_select.models = options
        self._model_option_values = {value for _, value in options}

        # 如果默认模型不在候选列表，回退到 Others
        if default_model not in self._model_option_values:
            default_model = "others"

        # 等待Textual更新后，设置默认值
        self.call_after_refresh(self._set_default_model, provider, default_model)

    def _set_default_model(self, provider: str, default_model: str) -> None:
        """Set the default model after options are refreshed."""
        from memosyne.core.models import Configuration

        if default_model not in self._model_option_values:
            self.logger.warning("默认模型 %s 不在可选列表中", default_model)

        self._apply_model_select_value(default_model)

        current_value = self._extract_select_value(getattr(self.model_select, "value", None))
        if not current_value:
            self.model_select.prompt = default_model

        # 设置输入框的值（使用新格式）
        model_display = Configuration.format_model(provider, default_model)
        self._set_auto_field(self.model_input, model_display)
        self._refresh_detection_model()

    def _resolve_model(self) -> tuple[str, str, str]:
        """
        Resolve model string to provider, model_id, and model_code.

        支持格式：
        - Provider::model (如 OpenAI::gpt-4o-mini)
        - 旧格式 provider:model (如 openai:gpt-4o-mini)
        - 纯模型名 (如 gpt-4o-mini)
        - 4位代码 (如 o4oo)
        """
        value = self.model_input.value.strip()
        if not value:
            raise ValueError("模型输入不能为空")

        # 如果是新格式（Provider::model），提取model部分
        from memosyne.core.models import Configuration
        if "::" in value:
            parts = value.split("::", 1)
            provider = parts[0].lower()
            model_part = parts[1]
        # 如果是旧格式（provider:model），提取model部分
        elif ":" in value:
            parts = value.split(":", 1)
            provider = parts[0].lower()
            model_part = parts[1]
        else:
            # 纯模型名或代码，需要通过工具函数推断provider
            model_part = value
            provider = None

        # 使用工具函数解析模型名/代码
        model_id, model_code = resolve_model_input(model_part)

        # 如果provider未指定，从model_id推断
        if provider is None:
            provider = get_provider_from_model(model_id)

        return provider, model_id, model_code

    def _create_llm_adapter(
        self,
        provider: str,
        model_id: str,
        feature_config=None,
    ) -> LithoformerLLMAdapter:
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
        return LithoformerLLMAdapter.from_provider(llm_provider, feature_config=feature_config)

    @staticmethod
    def _format_question_code(seed: int, index: int) -> str:
        """Format the canonical question code (e.g., L000255)."""
        if seed <= 0:
            return ""
        return f"L{seed + index:06d}"

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
    def _reconstruct_markdown(blocks: list[dict[str, str]]) -> str:
        """
        重建markdown内容（用于并发处理）

        Args:
            blocks: 题目块列表

        Returns:
            重建的markdown字符串
        """
        parts = []
        for block in blocks:
            if block.get("context"):
                parts.append(f"```Context\n{block['context']}\n```\n")
            parts.append(f"```Question\n{block.get('question', '')}\n```\n")
            parts.append(f"```Answer\n{block.get('answer', '')}\n```\n")
            parts.append("\n---\n\n")
        return "".join(parts)

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
