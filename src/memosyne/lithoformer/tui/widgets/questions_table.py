"""Questions table widget for Lithoformer TUI."""

from __future__ import annotations

from dataclasses import dataclass

from rich.text import Text
from textual.reactive import Reactive, reactive
from textual.widgets import DataTable


@dataclass(slots=True)
class QuestionRow:
    """Represents a single question row in the table."""

    row_key: str
    index: int
    number: str
    status: str = "Pending"
    char_count: int = 0
    qtype: str = "—"
    output_chars: int = 0
    elapsed: float = 0.0
    error: str | None = None


class QuestionsTable(DataTable):
    """Table widget that displays the list of questions and their processing status."""

    questions: Reactive[list[QuestionRow] | None] = reactive(None, always_update=True)

    def __init__(self):
        super().__init__(
            id="questions-table",
            cursor_type="row",
            zebra_stripes=True,
        )
        self.border_title = "题目列表"
        self._setup_columns()

    def _setup_columns(self) -> None:
        """Set up the table columns."""
        self.add_column("#", key="index", width=4)
        self.add_column("题号", key="number", width=14)
        self.add_column("Status", key="status", width=14)
        self.add_column("字符数", key="char", width=10)
        self.add_column("题型", key="qtype", width=10)
        self.add_column("输出字符数", key="output_chars", width=14)
        self.add_column("所用时间", key="elapsed", width=12)

    def clear(self) -> None:  # type: ignore[override]
        """Clear the table rows and reset the cursor."""
        super().clear()
        self.cursor_visible = False

    def watch_questions(self, questions: list[QuestionRow] | None = None) -> None:
        """Update the table when questions data changes."""
        if questions is None:
            return

        super().clear()
        for question in questions:
            self._add_question_row(question)
        if questions:
            self.cursor_visible = True
            self.cursor_coordinate = (0, 0)

    def _add_question_row(self, question: QuestionRow) -> None:
        """Add a single question row to the table."""
        style = self._get_status_style(question.status)

        self.add_row(
            str(question.index),
            question.number,
            Text(question.status, style=style),
            str(question.char_count),
            question.qtype,
            str(question.output_chars),
            f"{question.elapsed:.2f}s",
            key=question.row_key,
        )

    def update_question_status(
        self,
        row_key: str,
        status: str,
        qtype: str | None = None,
        output_chars: int | None = None,
        elapsed: float | None = None,
    ) -> None:
        """Update the status and other fields of a question row."""
        style = self._get_status_style(status)

        self.update_cell(row_key, "status", Text(status, style=style))

        if qtype is not None:
            self.update_cell(row_key, "qtype", qtype)

        if output_chars is not None:
            self.update_cell(row_key, "output_chars", str(output_chars))

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
        }
        return styles.get(status, "white")


__all__ = ["QuestionRow", "QuestionsTable"]
