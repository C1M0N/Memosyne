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

class OutputPathInput(Input):
    """Input widget for specifying the output directory."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="output-directory",
            value=value or "",
            placeholder="解析结果输出目录",
        )
        self.border_title = "输出路径"

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
            type_to_search=True,
            compact=True,
            classes="tight-select jira-selector",
        )
        self.border_title = "厂商选择"
        self.border_subtitle = "(p)"

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
            type_to_search=True,
            compact=True,
            classes="tight-select jira-selector",
        )
        self.border_title = "模型选择"
        self.border_subtitle = "(m)"

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

class NoteInput(Input):
    """Input widget for optional model notes."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="note-input",
            value=value or "",
            placeholder="可选，填写内容会附加到 user prompt 末尾",
        )
        self.border_title = "备注"

class TitleInput(Input):
    """Input widget for specifying the title."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="title-input",
            value=value or "",
            placeholder="使用\\n表示换行，\\n前加粗，后不加粗",
        )
        self.border_title = "标题"

class SequenceInput(Input):
    """Input widget for specifying sequence number."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="sequence-input",
            value=value or "",
            placeholder="序号，例如 23",
        )
        self.border_title = "序号"

class BatchInput(Input):
    """Input widget for specifying batch ID."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="batch-input",
            value=value or "",
            placeholder="批次号自动生成，可覆盖",
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

class CommandInput(Input):
    """Input widget for commands."""

    def __init__(self):
        super().__init__(
            id="command-input",
            placeholder="/clear 清空日志",
        )
        self.border_title = "指令输入"

class LithoformerDirectoryTree(DirectoryTree):
    """Directory tree widget for file selection (Markdown only)."""

    def __init__(self, root: Path):
        super().__init__(root, id="file-tree")
        self.border_title = "文件选择"
    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:  # noqa: D401 - textual override
        """Keep directories and Markdown files only."""
        for path in paths:
            if path.is_dir() or path.suffix.lower() == ".md":
                yield path


# === Config Tab Widgets ===

class ConfigDefaultInputDirInput(Input):
    """Config widget for default input directory."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="config-default-input-dir",
            value=value or "",
            placeholder="默认输入路径",
        )
        self.border_title = "默认输入路径"


class ConfigDefaultOutputDirInput(Input):
    """Config widget for default output directory."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="config-default-output-dir",
            value=value or "",
            placeholder="默认输出路径",
        )
        self.border_title = "默认输出路径"


class ConfigDefaultModelInput(Input):
    """Config widget for default model (format: Provider::model)."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="config-default-model",
            value=value or "",
            placeholder="格式：Provider::model（如 OpenAI::gpt-4o-mini）",
        )
        self.border_title = "默认使用模型"


class ConfigReserved1Input(Input):
    """Config widget for reserved configuration 1."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="config-reserved-1",
            value=value or "",
            placeholder="预留配置1",
        )
        self.border_title = "预留配置1"


class ConfigReserved2Input(Input):
    """Config widget for reserved configuration 2."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="config-reserved-2",
            value=value or "",
            placeholder="预留配置2",
        )
        self.border_title = "预留配置2"


class ConfigReserved3Input(Input):
    """Config widget for reserved configuration 3."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="config-reserved-3",
            value=value or "",
            placeholder="预留配置3",
        )
        self.border_title = "预留配置3"


class ConfigReserved4Input(Input):
    """Config widget for reserved configuration 4."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="config-reserved-4",
            value=value or "",
            placeholder="预留配置4",
        )
        self.border_title = "预留配置4"


class ConfigReserved5Input(Input):
    """Config widget for reserved configuration 5."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="config-reserved-5",
            value=value or "",
            placeholder="预留配置5",
        )
        self.border_title = "预留配置5"


class ConfigReserved6Input(Input):
    """Config widget for reserved configuration 6."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="config-reserved-6",
            value=value or "",
            placeholder="预留配置6",
        )
        self.border_title = "预留配置6"


class ConfigReserved7Input(Input):
    """Config widget for reserved configuration 7."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="config-reserved-7",
            value=value or "",
            placeholder="预留配置7",
        )
        self.border_title = "预留配置7"


# === Feature Tab Widgets ===

from textual.widgets import Checkbox


class FeatureTranslationCheckbox(Checkbox):
    """功能Tab - 翻译功能开关"""

    def __init__(self, value: bool = True):
        super().__init__(
            "翻译功能",
            value=value,
            id="feature-translation",
        )


class FeatureParsingCheckbox(Checkbox):
    """功能Tab - 解析功能开关"""

    def __init__(self, value: bool = True):
        super().__init__(
            "解析功能",
            value=value,
            id="feature-parsing",
        )


class FeatureConcurrentCheckbox(Checkbox):
    """功能Tab - 并发处理开关"""

    def __init__(self, value: bool = False):
        super().__init__(
            "并发处理",
            value=value,
            id="feature-concurrent",
        )


class Feature001Checkbox(Checkbox):
    """功能Tab - 预留功能001"""

    def __init__(self, value: bool = False):
        super().__init__(
            "预留功能001",
            value=value,
            id="feature-001",
        )


class Feature002Checkbox(Checkbox):
    """功能Tab - 预留功能002"""

    def __init__(self, value: bool = False):
        super().__init__(
            "预留功能002",
            value=value,
            id="feature-002",
        )


class Feature003Checkbox(Checkbox):
    """功能Tab - 预留功能003"""

    def __init__(self, value: bool = False):
        super().__init__(
            "预留功能003",
            value=value,
            id="feature-003",
        )


# === Config Tab - 新增并发配置 ===

class ConfigMaxConcurrentInput(Input):
    """Config widget for maximum concurrent tasks."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="config-max-concurrent",
            value=value or "10",
            placeholder="并发数（1-100）",
        )
        self.border_title = "并发数"


class ConfigMaxRetriesInput(Input):
    """Config widget for maximum retries."""

    def __init__(self, value: str | None = None):
        super().__init__(
            id="config-max-retries",
            value=value or "1",
            placeholder="重试次数（0-10）",
        )
        self.border_title = "重试次数"
