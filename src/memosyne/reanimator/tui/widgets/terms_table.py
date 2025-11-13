"""Terms table widget for Reanimator TUI."""

from __future__ import annotations

from dataclasses import dataclass

from rich.text import Text
from textual.message import Message
from textual.reactive import Reactive, reactive
from textual.widgets import DataTable


@dataclass(slots=True)
class TermRow:
    """Represents a single term row in the table."""

    row_key: str
    index: int
    word_id: str
    wm_pair: str
    field: str = "—"
    status: str = "Pending"
    elapsed: float = 0.0
    error: str | None = None


class TermsTable(DataTable):
    """Table widget that displays the list of terms and their processing status."""

    class RowHighlighted(Message):
        """Message emitted when a row highlight/selection changes."""

        def __init__(self, row_key: str, row_index: int) -> None:
            super().__init__()
            self.row_key = row_key
            self.row_index = row_index

    terms: Reactive[list[TermRow] | None] = reactive(None, always_update=True)

    def __init__(self):
        super().__init__(
            id="questions-table",
            cursor_type="row",
            zebra_stripes=True,
        )
        # 禁用边框，占满空间
        self.show_header = True
        self.styles.border = ("none", "transparent")
        self.styles.height = "1fr"
        self._setup_columns()

    def _setup_columns(self) -> None:
        """Set up the table columns."""
        self.add_column("#", key="index", width=3)
        self.add_column("Word ID", key="word_id", width=10)
        self.add_column("词义对", key="wm_pair", width=40)
        self.add_column("领域", key="field", width=12)
        self.add_column("Status", key="status", width=11)
        self.add_column("时间", key="elapsed", width=8)

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        """禁用列标题点击排序功能。"""
        event.prevent_default()
        event.stop()

    def clear(self) -> None:  # type: ignore[override]
        """Clear the table rows and reset the cursor."""
        super().clear()
        self.cursor_visible = False

    def watch_terms(self, terms: list[TermRow] | None = None) -> None:
        """Update the table when terms data changes."""
        if terms is None:
            return

        super().clear()
        for term in terms:
            self._add_term_row(term)
        if terms:
            self.cursor_visible = True
            self.cursor_coordinate = (0, 0)

    def _add_term_row(self, term: TermRow) -> None:
        """Add a single term row to the table."""
        style = self._get_status_style(term.status)

        # 截断过长的 wm_pair
        wm_pair_display = term.wm_pair
        if len(wm_pair_display) > 33:
            wm_pair_display = wm_pair_display[:30] + "..."

        self.add_row(
            str(term.index),
            term.word_id,
            wm_pair_display,
            term.field or "—",
            Text(term.status, style=style),
            f"{term.elapsed:.2f}s" if term.elapsed > 0 else "—",
            key=term.row_key,
        )

    def update_term_status(
        self,
        row_key: str,
        status: str | Text,
        field_value: str | None = None,
        elapsed: float | None = None,
    ) -> None:
        """Update the status and other fields of a term row."""
        # 如果status已经是Text对象，直接使用；否则应用样式
        if isinstance(status, Text):
            status_text = status
        else:
            style = self._get_status_style(status)
            status_text = Text(status, style=style)

        self.update_cell(row_key, "status", status_text)

        if field_value is not None:
            self.update_cell(row_key, "field", field_value)

        if elapsed is not None:
            self.update_cell(row_key, "elapsed", f"{elapsed:.2f}s")

    @staticmethod
    def _get_status_style(status: str) -> str:
        """Get the Rich style for a given status."""
        styles = {
            "Pending": "orange3",
            "In Progress": "medium_purple3",
            "Done": "green3",
            "ERROR": "red",
            "Conflict": "yellow",  # 冲突状态
            "Saved": "cyan",  # 已保存到库
        }
        return styles.get(status, "white")

    def on_data_table_row_selected(self, event) -> None:  # type: ignore[override]
        """Forward row selection events as high-level messages."""
        info = self._extract_row_info(event)
        if info is not None:
            row_key, row_index = info
            self.post_message(self.RowHighlighted(row_key, row_index))

    def on_data_table_row_highlighted(self, event) -> None:  # type: ignore[override]
        """Forward highlight changes as messages so the preview can sync."""
        info = self._extract_row_info(event)
        if info is not None:
            row_key, row_index = info
            self.post_message(self.RowHighlighted(row_key, row_index))

    def _extract_row_info(self, event) -> tuple[str, int] | None:
        """Extract row key and 1-based index from a DataTable event."""
        row_key = getattr(event, "row_key", None)

        row_index = getattr(event, "row_index", None)
        if row_index is None:
            row_index = getattr(event, "cursor_row", None)
        if row_index is None:
            row_index = getattr(event, "row", None)

        row_index_int: int | None
        if row_index is not None:
            try:
                row_index_int = int(row_index)
            except (TypeError, ValueError):
                row_index_int = None
        else:
            row_index_int = None

        if row_key is None and row_index_int is not None:
            row_key = f"row-{row_index_int + 1}"

        if row_key is None:
            return None

        if row_index_int is None:
            if isinstance(row_key, str) and row_key.startswith("row-"):
                try:
                    row_index_int = int(row_key.split('-', 1)[1]) - 1
                except ValueError:
                    row_index_int = None

        if row_index_int is None:
            return None

        return str(row_key), row_index_int + 1


__all__ = ["TermRow", "TermsTable"]
