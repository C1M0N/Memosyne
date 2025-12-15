"""Input and helper widgets for the Reanimator TUI."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from textual.widgets import DirectoryTree, Input, Select


INPUT_SUBTITLE = "[dodger_blue2]输入[/]"
AUTO_SUBTITLE = "[indian_red1]自动推断[/]"


class InputPathInput(Input):
    """Input widget for selecting the input directory containing CSV files."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="input-directory",
            value=value or "",
            placeholder="请选择或输入包含术语 CSV 的目录",
        )
        self.border_title = "输入路径"


class OutputPathInput(Input):
    """Input widget for specifying the output directory."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="output-directory",
            value=value or "",
            placeholder="处理结果输出目录",
        )
        self.border_title = "输出路径"


class ProviderSelectionInput(Select):
    """Selection widget for choosing the LLM provider."""

    def __init__(self, options: list[tuple[str, str]] | None = None, value: str | None = None):
        normalized = options or [("OpenAI", "openai"), ("Anthropic", "anthropic")]
        default_value = value or (normalized[0][1] if normalized else Select.BLANK)
        super().__init__(
            options=normalized,
            value=default_value,
            allow_blank=False,
            id="provider-select",
            prompt="选择厂商",
            name="provider-select",
            type_to_search=True,
            compact=True,
        )
        self.border_title = "厂商选择"


class ModelSelectionInput(Select):
    """Selection widget for choosing a concrete model."""

    def __init__(self, options: list[tuple[str, str]] | None = None, value: str | None = None):
        super().__init__(
            options=options or [],
            value=value or Select.BLANK,
            allow_blank=True,
            id="model-select",
            prompt="选择模型",
            name="model-select",
            type_to_search=True,
            compact=True,
        )
        self.border_title = "模型选择"


class ModelInput(Input):
    """Input widget for specifying the model to use."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="model-input",
            value=value or "",
            placeholder="格式：Provider::model（如 OpenAI::gpt-4o）",
        )
        self.border_title = "使用模型"


class BatchNoteInput(Input):
    """Input widget for batch note/description."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="batch-note-input",
            value=value or "",
            placeholder="可选，填写批次备注信息（会写入输出）",
        )
        self.border_title = "批次备注"


class BatchIdInput(Input):
    """Input widget for batch ID (auto-generated, can be overridden)."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="batch-input",
            value=value or "",
            placeholder="批次号自动生成（YYMMDDX###），可覆盖",
        )
        self.border_title = "批次号"


class OutputFilenameInput(Input):
    """Input widget for specifying output filename."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="output-filename-input",
            value=value or "",
            placeholder="输出文件名（含扩展名）",
        )
        self.border_title = "输出文件名"


class SequenceInput(Input):
    """Read-only input showing the derived start sequence."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="sequence-input",
            value=value or "",
            placeholder="由文件名自动推断",
            disabled=True,
        )
        self.border_title = "序号"


class NoteInput(Input):
    """Extra instruction input appended to prompts (like Lithoformer)."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="note-input",
            value=value or "",
            placeholder="可选，填写额外提示，会附加到 LLM 指令末尾",
        )
        self.border_title = "备注"


class CommandInput(Input):
    """Input widget for commands."""

    def __init__(self):
        super().__init__(
            id="command-input",
            placeholder="/clear /bank /yes /no",
        )
        self.border_title = "指令输入"


class ReanimatorDirectoryTree(DirectoryTree):
    """Directory tree widget for CSV file selection."""

    def __init__(self, root: Path):
        super().__init__(root, id="file-tree")
        self.border_title = "CSV 文件选择"

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:  # noqa: D401 - textual override
        """Keep directories and CSV files only."""
        for path in paths:
            if path.is_dir() or path.suffix.lower() == ".csv":
                yield path


# === Config Tab Widgets ===


class ConfigDefaultInputDirInput(Input):
    """Config widget for default input directory."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="reanimator-config-default-input-dir",
            value=value or "",
            placeholder="默认输入路径",
        )
        self.border_title = "默认输入路径"


class ConfigDefaultOutputDirInput(Input):
    """Config widget for default output directory."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="reanimator-config-default-output-dir",
            value=value or "",
            placeholder="默认输出路径",
        )
        self.border_title = "默认输出路径"


class ConfigDefaultModelInput(Input):
    """Config widget for default model (format: Provider::model)."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="reanimator-config-default-model",
            value=value or "",
            placeholder="格式：Provider::model（如 OpenAI::gpt-4o）",
        )
        self.border_title = "默认使用模型"


class ConfigTermListPathInput(Input):
    """Config widget for term list CSV path (legacy, now in database)."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="reanimator-config-term-list-path",
            value=value or "",
            placeholder="术语表路径（已迁移至数据库）",
        )
        self.border_title = "术语表路径"


class ConfigMaxConcurrentInput(Input):
    """Config widget for maximum concurrent tasks."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="reanimator-config-max-concurrent",
            value=value or "3",
            placeholder="并发数（1-777）",
        )
        self.border_title = "并发数"


class ConfigMaxRetriesInput(Input):
    """Config widget for maximum retries."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="reanimator-config-max-retries",
            value=value or "3",
            placeholder="重试次数（0-10）",
        )
        self.border_title = "重试次数"
