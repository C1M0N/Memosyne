"""Input and helper widgets for the Lithoformer TUI."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from textual.reactive import Reactive, reactive
from textual.widgets import DirectoryTree, Input, Select


INPUT_SUBTITLE = "[dodger_blue2]输入[/]"
AUTO_SUBTITLE = "[indian_red1]自动推断[/]"


class InputPathInput(Input):
    """Input widget for selecting the input directory."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="input-directory",
            value=value or "",
            placeholder="请选择或输入包含测验 Markdown 的目录",
        )
        self.border_title = "输入路径"
        self.border_subtitle = INPUT_SUBTITLE


class OutputPathInput(Input):
    """Input widget for specifying the output directory."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="output-directory",
            value=value or "",
            placeholder="解析结果输出目录",
        )
        self.border_title = "输出路径"
        self.border_subtitle = INPUT_SUBTITLE


class ProviderSelectionInput(Select):
    """Selection widget for choosing the LLM provider."""

    def __init__(self, value: str | None = None):
        options = [
            ("OpenAI", "openai"),
            ("Anthropic", "anthropic"),
        ]
        super().__init__(
            options=options,
            value=value or "openai",
            allow_blank=False,
            id="provider-select",
            prompt="选择厂商",
            name="provider",
            tooltip="LLM 厂商",
            classes="tight-select",
        )
        self.border_title = "厂商选择"
        self.border_subtitle = "[dodger_blue2]下拉菜单[/]"


class ModelSelectionInput(Select):
    """Selection widget for choosing a specific model."""

    models: Reactive[list[tuple[str, str]] | None] = reactive(None, always_update=True)

    def __init__(self, options: list[tuple[str, str]] | None = None, value: str | None = None):
        super().__init__(
            options=options or [],
            value=value if value else Select.BLANK,
            allow_blank=True,
            id="model-select",
            prompt="选择模型",
            name="model-select",
            tooltip="从配置提供的模型中选择",
            classes="tight-select",
        )
        self.border_title = "模型选择"
        self.border_subtitle = "[dodger_blue2]下拉菜单[/]"

    def watch_models(self, models: list[tuple[str, str]] | None = None) -> None:
        """Reload the option list when the available models change."""
        self.clear()
        if models:
            self.set_options(models)


class ModelInput(Input):
    """Input widget for specifying the model to use."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="model-input",
            value=value or "",
            placeholder="可手动覆盖具体模型标识",
        )
        self.border_title = "使用模型"
        self.border_subtitle = AUTO_SUBTITLE


class TagInput(Input):
    """Input widget for specifying tags."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="tag-input",
            value=value or "",
            placeholder="自动依据检测结果填写，可手动覆盖",
        )
        self.border_title = "标签"
        self.border_subtitle = AUTO_SUBTITLE


class TitleInput(Input):
    """Input widget for specifying the title."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="title-input",
            value=value or "",
            placeholder="主标题",
        )
        self.border_title = "标题"
        self.border_subtitle = AUTO_SUBTITLE


class SequenceInput(Input):
    """Input widget for specifying sequence number."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="sequence-input",
            value=value or "",
            placeholder="序号，例如 23",
        )
        self.border_title = "序号"
        self.border_subtitle = AUTO_SUBTITLE


class BatchInput(Input):
    """Input widget for specifying batch ID."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="batch-input",
            value=value or "",
            placeholder="批次号自动生成，可覆盖",
        )
        self.border_title = "批次号"
        self.border_subtitle = AUTO_SUBTITLE


class OutputFilenameInput(Input):
    """Input widget for specifying output filename."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="output-filename-input",
            value=value or "",
            placeholder="输出文件名（含扩展名）",
        )
        self.border_title = "输出文件名"
        self.border_subtitle = AUTO_SUBTITLE


class ModelNoteInput(Input):
    """Input widget for notes to pass to the model."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="model-note-input",
            value=value or "",
            placeholder="可传给模型的额外提醒（可选）",
        )
        self.border_title = "给模型的备注"
        self.border_subtitle = INPUT_SUBTITLE


class CommandInput(Input):
    """Input widget for commands."""

    def __init__(self):
        super().__init__(
            id="command-input",
            placeholder="/clear 清空日志",
        )
        self.border_title = "指令输入区"
        self.border_subtitle = INPUT_SUBTITLE


class LithoformerDirectoryTree(DirectoryTree):
    """Directory tree widget for file selection (Markdown only)."""

    def __init__(self, root: Path):
        super().__init__(root, id="file-tree")
        self.border_title = "文件选择"
        self.border_subtitle = "[dodger_blue2]DirectoryTree[/]"

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:  # noqa: D401 - textual override
        """Keep directories and Markdown files only."""
        for path in paths:
            if path.is_dir() or path.suffix.lower() == ".md":
                yield path
