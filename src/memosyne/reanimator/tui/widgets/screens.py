"""Main screen implementation for the Reanimator TUI."""

from __future__ import annotations

import asyncio
import csv
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter

from rich.markup import escape
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import Screen
# Note: ReanimatorContainer is used as a widget in TabPane, not a Screen
from textual.widgets import Button, Footer, Input, Label, RichLog, Static

from ....core.models import TokenUsage
from ....shared.config import get_settings
from ....shared.infrastructure.reanimator_config_service import get_reanimator_config_service
from ....shared.infrastructure.reanimator_db import get_reanimator_repository
from ....shared.infrastructure.llm import OpenAIProvider
from ....shared.utils import BatchIDGenerator, unique_path
from ...application.concurrent_use_case import ConcurrentProcessTermsUseCase
from ...domain.models import TermInput
from ...infrastructure.llm_adapter import ReanimatorLLMAdapter
from ...infrastructure.term_list_adapter import TermListAdapter
from ..constants import ASCII_LOGO
from ..logging_utils import build_textual_handler
from .feature_toggles import FeatureTogglesWidget
from .filters import (
    BatchIdInput,
    BatchNoteInput,
    CommandInput,
    InputPathInput,
    ModelInput,
    OutputFilenameInput,
    OutputPathInput,
    ReanimatorDirectoryTree,
    StartMemoIndexInput,
)
from .terms_table import TermRow, TermsTable


@dataclass(slots=True)
class DetectionResult:
    """Aggregate data produced by the Detect phase."""

    file_path: Path
    terms: list[TermInput]
    model: str
    batch_id: str
    batch_note: str
    start_memo_index: int
    output_filename: str
    detected_at: datetime
    term_rows: list[TermRow]


class ReanimatorScreen(Screen):
    """Main screen of the Reanimator TUI application."""

    DEFAULT_CSS = """
    #reanimator-left-col {
        height: 100%;
        width: 45%;
    }

    #reanimator-header-area {
        height: auto;
    }

    #reanimator-terms-area {
        height: 1fr;
        border: round $primary;
        padding: 0;
    }

    #reanimator-right-area {
        height: 100%;
        width: 55%;
    }

    #reanimator-inputs-container {
        height: auto;
        border: round $primary;
        padding: 1;
    }

    #reanimator-log-view {
        height: 1fr;
        border: round $primary;
    }

    #reanimator-command-input {
        height: auto;
    }

    #reanimator-action-row {
        height: auto;
        align: center middle;
    }
    """

    BINDINGS = [
        Binding("q", "quit_app", "Quit", show=True, priority=True),
        Binding("c", "toggle_concurrent", "并发", show=True, priority=False),
    ]

    action_mode = reactive("detect")  # detect | start | running

    def __init__(self) -> None:
        super().__init__()
        self.settings = get_settings()
        self.settings.ensure_dirs()

        self._detection: DetectionResult | None = None
        self._rows: dict[int, TermRow] = {}
        self._manual_overrides: set[str] = set()
        self._auto_values: dict[str, str] = {}
        self._suspend_change_events = False

        self._main_thread_id: int | None = None
        self._log_handler = None

        # 初始化配置服务
        config_db = self.settings.db_dir / "config.db"
        self._config_service = get_reanimator_config_service(config_db)
        config_bundle = self._config_service.get_config_bundle()

        # 初始化数据库仓储
        stat_db = self.settings.db_dir / "stat.db"
        self._repo = get_reanimator_repository(stat_db)

        # 设置文件树根目录
        input_dir = config_bundle.paths.input_dir or self.settings.db_dir.parent / "misc/input/reanimator"
        input_dir.mkdir(parents=True, exist_ok=True)
        self._file_tree = ReanimatorDirectoryTree(input_dir)
        self._selected_file: Path | None = None

        self._run_start_time: float | None = None
        self._total_tokens: TokenUsage = TokenUsage()
        self._processed_count: int = 0

        self._run_task: asyncio.Task[None] | None = None

        # 冲突确认状态
        self._waiting_for_overwrite_confirmation: bool = False
        self._conflict_terms: list[dict] = []

        self.logger = logging.getLogger("memosyne.reanimator.tui")

    # region convenience accessors -------------------------------------------------
    @property
    def terms_table(self) -> TermsTable:
        return self.query_one(TermsTable)

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
    def start_memo_input(self) -> StartMemoIndexInput:
        return self.query_one(StartMemoIndexInput)

    @property
    def output_filename_input(self) -> OutputFilenameInput:
        return self.query_one(OutputFilenameInput)

    @property
    def command_input(self) -> CommandInput:
        return self.query_one(CommandInput)

    @property
    def log_view(self) -> RichLog:
        return self.query_one("#reanimator-log-view", RichLog)

    @property
    def action_button(self) -> Button:
        return self.query_one("#reanimator-action-button", Button)

    @property
    def feature_toggles(self) -> FeatureTogglesWidget:
        return self.query_one("#reanimator-feature-toggles", FeatureTogglesWidget)

    # endregion -------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        """Compose the main screen layout."""
        # 从数据库读取当前功能开关状态
        flags = self._config_service.get_feature_flags()
        config = self._config_service.get_all_config()

        # 主容器：左列 + 右列
        with Horizontal(id="reanimator-main-container"):
            # 左列: LOGO + 功能开关 + 术语列表
            with Vertical(id="reanimator-left-col"):
                # LOGO 和开关区
                with Vertical(id="reanimator-header-area"):
                    yield Static(ASCII_LOGO, id="reanimator-logo-panel")
                    yield FeatureTogglesWidget(
                        concurrent=flags.enable_concurrent,
                        id="reanimator-feature-toggles"
                    )

                # 术语列表区域
                terms_area = Vertical(id="reanimator-terms-area")
                terms_area.border_title = "术语列表"
                with terms_area:
                    yield TermsTable()

            # 右列: 输入区 + 文件树 + 按钮 + 日志
            with Vertical(id="reanimator-right-area"):
                # 输入配置区
                inputs_container = Vertical(id="reanimator-inputs-container")
                inputs_container.border_title = "配置"
                with inputs_container:
                    yield InputPathInput(value=config.reanimator_input_dir)
                    yield OutputPathInput(value=config.reanimator_output_dir)
                    yield ModelInput(value=config.default_model)
                    yield BatchNoteInput()
                    with Horizontal(id="reanimator-batch-memo-row"):
                        yield BatchIdInput()
                        yield StartMemoIndexInput()
                    yield OutputFilenameInput()

                # 文件树
                yield self._file_tree

                # 按钮区
                with Horizontal(id="reanimator-action-row"):
                    yield Button("Detect", id="reanimator-action-button", variant="primary")

                # 日志区
                log_view = RichLog(id="reanimator-log-view", highlight=True, markup=True)
                log_view.border_title = "控制台"
                if hasattr(log_view, "max_lines"):
                    log_view.max_lines = 999
                yield log_view

                yield CommandInput()

        # Footer：显示快捷键
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the screen after mounting."""
        # 设置日志handler
        self._log_handler = build_textual_handler(self.log_view.write)
        self.logger.addHandler(self._log_handler)
        self.logger.setLevel(logging.INFO)

        # 记录线程ID
        import threading
        self._main_thread_id = threading.get_ident()

        self.logger.info(f"[bold cyan]Reanimator TUI v0.16.0[/bold cyan]")
        self.logger.info("按 [cyan]c[/cyan] 切换并发模式 | 按 [cyan]q[/cyan] 退出")

    @on(Button.Pressed, "#reanimator-action-button")
    def handle_action_button(self) -> None:
        """Handle the Detect/Start button press."""
        if self.action_mode == "detect":
            self.run_worker(self._run_detect(), exclusive=True)
        elif self.action_mode == "start":
            self.run_worker(self._run_start(), exclusive=True)

    @on(ReanimatorDirectoryTree.FileSelected)
    def handle_file_selected(self, event: ReanimatorDirectoryTree.FileSelected) -> None:
        """Handle file selection from the directory tree."""
        path = event.path
        if path.is_file() and path.suffix.lower() == ".csv":
            self._selected_file = path
            self.input_path_input.value = str(path)
            self.logger.info(f"已选择文件: [cyan]{path.name}[/cyan]")

    @on(FeatureTogglesWidget.ToggleChanged)
    def handle_toggle_changed(self, event: FeatureTogglesWidget.ToggleChanged) -> None:
        """Handle feature toggle changes."""
        if event.toggle_name == "concurrent":
            self._config_service.update_feature_flags(enable_concurrent=event.new_value)
            status = "启用" if event.new_value else "禁用"
            self.logger.info(f"并发模式已{status}")

    async def _run_detect(self) -> None:
        """Run the Detect phase: validate CSV and prepare processing."""
        try:
            self.logger.info("\n[bold yellow]═══ Detect 阶段开始 ═══[/bold yellow]")

            # 1. 验证输入文件
            input_path = Path(self.input_path_input.value.strip())
            if not input_path.exists() or not input_path.is_file():
                self.logger.error(f"输入文件不存在: {input_path}")
                return

            if input_path.suffix.lower() != ".csv":
                self.logger.error("只支持 CSV 文件")
                return

            self.logger.info(f"检测到 CSV 文件: [cyan]{input_path.name}[/cyan]")

            # 2. 解析 CSV 文件
            terms = self._parse_csv_file(input_path)
            if not terms:
                self.logger.error("CSV 文件为空或格式错误")
                return

            self.logger.info(f"共检测到 [cyan]{len(terms)}[/cyan] 个术语")

            # 3. 获取配置
            model = self.model_input.value.strip() or self._config_service.get_all_config().default_model
            batch_note = self.batch_note_input.value.strip()

            # 4. 生成 Batch ID
            batch_id = self.batch_id_input.value.strip()
            if not batch_id:
                batch_id = BatchIDGenerator.generate()
                self.batch_id_input.value = batch_id

            # 5. 获取起始 Memo ID
            start_memo = self.start_memo_input.value.strip()
            if not start_memo:
                # 从数据库获取最大 Memo ID
                max_memo = self._repo.get_max_memo_id()
                if max_memo:
                    # 格式: M000123 -> 123
                    start_index = int(max_memo[1:]) + 1
                else:
                    start_index = 1
                self.start_memo_input.value = str(start_index)
            else:
                start_index = int(start_memo)

            # 6. 生成输出文件名
            output_filename = self.output_filename_input.value.strip()
            if not output_filename:
                output_filename = f"reanimator_{batch_id}.csv"
                self.output_filename_input.value = output_filename

            # 7. 创建 TermRow 列表
            term_rows = []
            for idx, term in enumerate(terms):
                memo_id = f"M{start_index + idx:06d}"
                wm_pair = f"{term.word} - {term.zh_def}"
                term_rows.append(TermRow(
                    row_key=f"row-{idx + 1}",
                    index=idx + 1,
                    memo_id=memo_id,
                    wm_pair=wm_pair,
                    status="Pending"
                ))

            # 8. 显示术语表格
            self.terms_table.terms = term_rows
            self._rows = {row.index: row for row in term_rows}

            # 9. 保存检测结果
            self._detection = DetectionResult(
                file_path=input_path,
                terms=terms,
                model=model,
                batch_id=batch_id,
                batch_note=batch_note,
                start_memo_index=start_index,
                output_filename=output_filename,
                detected_at=datetime.now(),
                term_rows=term_rows
            )

            # 10. 切换到 Start 模式
            self.action_mode = "start"
            self.action_button.label = "Start"
            self.action_button.variant = "success"

            self.logger.info("[bold green]Detect 完成，点击 Start 开始处理[/bold green]")

        except Exception as e:
            self.logger.error(f"Detect 失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    def _parse_csv_file(self, file_path: Path) -> list[TermInput]:
        """Parse CSV file and return list of TermInput objects."""
        terms = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # CSV格式：word, zh_def
                    word = row.get('word', '').strip()
                    zh_def = row.get('zh_def', '').strip()
                    if word and zh_def:
                        terms.append(TermInput(word=word, zh_def=zh_def))
        except Exception as e:
            self.logger.error(f"解析 CSV 文件失败: {e}")
            return []
        return terms

    async def _run_start(self) -> None:
        """Run the Start phase: process terms using LLM."""
        try:
            if not self._detection:
                self.logger.error("未检测到输入，请先运行 Detect")
                return

            self.logger.info("\n[bold yellow]═══ Start 阶段开始 ═══[/bold yellow]")
            self.action_mode = "running"
            self.action_button.disabled = True

            # 1. 检查并发模式
            flags = self._config_service.get_feature_flags()
            concurrent_enabled = flags.enable_concurrent
            mode_str = "并发" if concurrent_enabled else "串行"
            self.logger.info(f"处理模式: [cyan]{mode_str}[/cyan]")

            # 2. 创建 LLM Provider
            provider = self._create_llm_provider(self._detection.model)
            if not provider:
                self.logger.error(f"不支持的模型: {self._detection.model}")
                self._reset_to_detect()
                return

            # 3. 创建 Adapter
            llm_adapter = ReanimatorLLMAdapter(provider, self._repo)
            term_list_adapter = TermListAdapter(self._repo)

            # 4. 执行处理
            self._run_start_time = perf_counter()
            self._total_tokens = TokenUsage()
            self._processed_count = 0

            config = self._config_service.get_all_config()

            if concurrent_enabled:
                # 并发模式
                use_case = ConcurrentProcessTermsUseCase(
                    llm=llm_adapter,
                    term_list=term_list_adapter,
                    start_memo_index=self._detection.start_memo_index,
                    batch_id=self._detection.batch_id,
                    batch_note=self._detection.batch_note,
                    max_concurrent=config.max_concurrent
                )
                result = use_case.execute(self._detection.terms, show_progress=False)
            else:
                # 串行模式（简化实现）
                self.logger.warning("串行模式尚未实现，使用并发模式（max_concurrent=1）")
                use_case = ConcurrentProcessTermsUseCase(
                    llm=llm_adapter,
                    term_list=term_list_adapter,
                    start_memo_index=self._detection.start_memo_index,
                    batch_id=self._detection.batch_id,
                    batch_note=self._detection.batch_note,
                    max_concurrent=1
                )
                result = use_case.execute(self._detection.terms, show_progress=False)

            # 5. 更新统计
            elapsed = perf_counter() - self._run_start_time
            self._total_tokens = result.token_usage
            self._processed_count = result.success_count

            self.logger.info(f"\n[bold green]处理完成！[/bold green]")
            self.logger.info(f"成功: {result.success_count}/{result.total_count}")
            self.logger.info(f"用时: {elapsed:.2f}s")
            self.logger.info(f"Tokens: {self._total_tokens.total_tokens:,}")

            # 6. 更新表格
            for idx, term_output in enumerate(result.items):
                row_key = f"row-{idx + 1}"
                self.terms_table.update_term_status(
                    row_key=row_key,
                    status="Done",
                    pos=term_output.pos,
                    tag=term_output.tag_cn
                )

            # 7. 检查冲突并保存到 Bank
            await self._check_conflicts_and_save(result.items)

        except Exception as e:
            self.logger.error(f"Start 失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            self._reset_to_detect()

    def _create_llm_provider(self, model: str):
        """Create LLM provider from model string (format: Provider::model)."""
        try:
            if "::" not in model:
                self.logger.error(f"模型格式错误，应为 Provider::model，实际: {model}")
                return None

            provider_str, model_id = model.split("::", 1)
            provider_str = provider_str.lower()

            if provider_str == "openai":
                return OpenAIProvider(model=model_id)
            else:
                self.logger.error(f"暂不支持的提供商: {provider_str}")
                return None
        except Exception as e:
            self.logger.error(f"创建 LLM Provider 失败: {e}")
            return None

    async def _check_conflicts_and_save(self, term_outputs: list) -> None:
        """Check for conflicts and save terms to bank."""
        conflicts = []
        for term_output in term_outputs:
            if self._repo.check_bank_exists(term_output.wm_pair):
                existing = self._repo.get_existing_term(term_output.wm_pair)
                conflicts.append({
                    "wm_pair": term_output.wm_pair,
                    "existing_memo_id": existing["memo_id"] if existing else "Unknown",
                    "new_memo_id": term_output.memo_id
                })

        if conflicts:
            self.logger.warning(f"\n[bold yellow]检测到 {len(conflicts)} 个冲突的 wm_pair[/bold yellow]")
            for conf in conflicts[:5]:  # 只显示前5个
                self.logger.warning(f"  - {conf['wm_pair']}: 已存在 {conf['existing_memo_id']}")
            if len(conflicts) > 5:
                self.logger.warning(f"  ... 还有 {len(conflicts) - 5} 个冲突")

            self.logger.info("\n[cyan]是否覆盖现有数据？输入 /yes 确认，/no 取消[/cyan]")
            self._waiting_for_overwrite_confirmation = True
            self._conflict_terms = term_outputs
        else:
            # 无冲突，直接保存
            await self._save_to_bank(term_outputs)

    async def _save_to_bank(self, term_outputs: list) -> None:
        """Save term outputs to reanimator_bank."""
        saved_count = 0
        for term_output in term_outputs:
            success = self._repo.save_to_bank(
                wm_pair=term_output.wm_pair,
                memo_id=term_output.memo_id,
                word=term_output.word,
                zh_def=term_output.zh_def,
                model=self._detection.model,
                ipa=term_output.ipa,
                pos=term_output.pos,
                tag=term_output.tag_cn,
                rarity=term_output.rarity,
                en_def=term_output.en_def,
                example=term_output.example,
                pp_fix=term_output.pp_fix,
                pp_means=term_output.pp_means,
                batch_id=self._detection.batch_id,
                batch_note=self._detection.batch_note
            )
            if success:
                saved_count += 1

        self.logger.info(f"\n[bold green]已保存 {saved_count}/{len(term_outputs)} 个术语到 Bank[/bold green]")
        self._reset_to_detect()

    def _reset_to_detect(self) -> None:
        """Reset the screen to Detect mode."""
        self.action_mode = "detect"
        self.action_button.label = "Detect"
        self.action_button.variant = "primary"
        self.action_button.disabled = False

    @on(Input.Submitted, "#reanimator-command-input")
    def handle_command_submitted(self, event: Input.Submitted) -> None:
        """Handle command input submission."""
        command = event.value.strip().lower()
        self.command_input.value = ""

        if not command:
            return

        if command == "/clear":
            self.log_view.clear()
            self.logger.info("日志已清空")
        elif command == "/yes":
            if self._waiting_for_overwrite_confirmation:
                self._waiting_for_overwrite_confirmation = False
                self.run_worker(self._save_to_bank(self._conflict_terms), exclusive=False)
            else:
                self.logger.warning("当前没有需要确认的操作")
        elif command == "/no":
            if self._waiting_for_overwrite_confirmation:
                self._waiting_for_overwrite_confirmation = False
                self.logger.info("[yellow]已取消保存[/yellow]")
                self._reset_to_detect()
            else:
                self.logger.warning("当前没有需要确认的操作")
        elif command == "/bank":
            terms = self._repo.get_all_terms_from_bank(limit=10)
            self.logger.info(f"\n[bold cyan]术语库（最近 10 条）[/bold cyan]")
            for term in terms:
                self.logger.info(f"  {term['memo_id']}: {term['wm_pair']}")
        else:
            self.logger.warning(f"未知命令: {command}")

    def action_toggle_concurrent(self) -> None:
        """Toggle concurrent mode (keyboard shortcut 'c')."""
        current = self.feature_toggles.concurrent_enabled
        self.feature_toggles.update_toggle("concurrent", not current)
        self._config_service.update_feature_flags(enable_concurrent=not current)
        status = "启用" if not current else "禁用"
        self.logger.info(f"并发模式已{status}")

    def action_quit_app(self) -> None:
        """Quit the application."""
        self.app.exit()


class ReanimatorContainer(Vertical):
    """Reanimator UI as a container widget (for embedding in TabPane)."""

    DEFAULT_CSS = """
    ReanimatorContainer {
        width: 100%;
        height: 100%;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        # Reuse ReanimatorScreen for standalone mode
        self._screen = ReanimatorScreen()

    def compose(self) -> ComposeResult:
        """Compose the Reanimator UI (delegates to ReanimatorScreen)."""
        # Delegate composition to ReanimatorScreen
        yield from self._screen.compose()


__all__ = ["ReanimatorScreen", "ReanimatorContainer"]
