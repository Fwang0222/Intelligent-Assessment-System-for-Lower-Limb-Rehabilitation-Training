"""History page for browsing previous training sessions."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter, QTableWidgetItem

from app.ui.base import BasePage
from app.ui.fluent_compat import BodyLabel, SubtitleLabel, TableWidget, TextEdit


class HistoryPage(BasePage):
    def __init__(self, db, user, parent=None):
        super().__init__(db, user, parent)
        self.records = []
        self.setup_ui()
        self.refresh_data()

    def setup_ui(self) -> None:
        self.main_layout.addWidget(SubtitleLabel("History Records"))
        self.main_layout.addWidget(BodyLabel("Review previous training sessions and their detailed outputs."))

        splitter = QSplitter(Qt.Horizontal)
        self.table = TableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Record ID", "Action", "Avg Score", "Completion", "Pain", "End Time"])
        self.table.cellClicked.connect(self.show_record_detail)
        self.detail_text = TextEdit()
        self.detail_text.setReadOnly(True)
        splitter.addWidget(self.table)
        splitter.addWidget(self.detail_text)
        splitter.setSizes([600, 500])
        self.main_layout.addWidget(splitter)

    def refresh_data(self) -> None:
        self.records = self.db.get_records(self.user["id"], limit=50)
        self.table.setRowCount(len(self.records))
        for row, record in enumerate(self.records):
            values = [
                record["id"],
                record["action_name"],
                record["avg_score"],
                f"{round((record['completion_rate'] or 0) * 100, 2)}%",
                record["pain_feedback"],
                record["session_end"],
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(str(value)))
        self.table.resizeColumnsToContents()
        if self.records:
            self.show_record_detail(0, 0)
        else:
            self.detail_text.setPlainText("No historical training records are available.")

    def show_record_detail(self, row: int, column: int) -> None:
        if not self.records or row < 0 or row >= len(self.records):
            return

        record_id = self.records[row]["id"]
        details = self.db.get_record_details(record_id)
        record = details["record"]
        errors = details["errors"]
        compensations = details["compensations"]
        feedbacks = details["feedbacks"]

        if not record:
            self.detail_text.setPlainText("This record does not exist.")
            return

        lines = [
            f"Record ID: {record['id']}",
            f"Action: {record['action_name']}",
            f"Average score: {record['avg_score']}",
            f"Completion rate: {round((record['completion_rate'] or 0) * 100, 2)}%",
            f"Summary: {record['summary']}",
            "\nError actions:",
        ]
        for item in errors:
            lines.append(f"- {item['error_type']} x {item['error_count']}")
        if not errors:
            lines.append("- None")

        lines.append("\nCompensation actions:")
        for item in compensations:
            lines.append(f"- {item['compensation_type']} x {item['detected_count']}")
        if not compensations:
            lines.append("- None")

        lines.append("\nFeedback records:")
        for item in feedbacks[-5:]:
            lines.append(f"- {item['feedback_content']}")
        if not feedbacks:
            lines.append("- No feedback available.")

        self.detail_text.setPlainText("\n".join(lines))
