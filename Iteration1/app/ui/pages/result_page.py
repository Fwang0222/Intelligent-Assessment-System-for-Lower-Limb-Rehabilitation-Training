"""Result page for the latest training session."""

from PySide6.QtWidgets import QGridLayout

from app.ui.base import BasePage
from app.ui.fluent_compat import BodyLabel, PageTitleLabel, TextEdit


class ResultPage(BasePage):
    def __init__(self, db, user, parent=None):
        super().__init__(db, user, parent)
        self.setup_ui()
        self.refresh_data()

    def setup_ui(self) -> None:
        self.main_layout.addWidget(PageTitleLabel("Training Results"))
        summary_grid = QGridLayout()
        summary_grid.setContentsMargins(0, 0, 0, 0)
        summary_grid.setHorizontalSpacing(10)
        summary_grid.setVerticalSpacing(10)
        self.session_label = self._create_metric_card(summary_grid, 0, 0, "Session")
        self.score_metric_label = self._create_metric_card(summary_grid, 0, 1, "Score")
        self.risk_metric_label = self._create_metric_card(summary_grid, 1, 0, "Risk Focus")
        self.plan_metric_label = self._create_metric_card(summary_grid, 1, 1, "Recommendation")
        self.main_layout.addLayout(summary_grid)

        detail_card, detail_layout = self.create_section_card("Detailed Report", "Structured summary for the latest completed session.")
        self.detail_text = TextEdit()
        self.detail_text.setReadOnly(True)
        detail_layout.addWidget(self.detail_text)
        self.main_layout.addWidget(detail_card, 1)

    def _create_metric_card(self, grid: QGridLayout, row: int, column: int, title: str):
        card, layout = self.create_section_card(title)
        label = BodyLabel("-")
        label.setWordWrap(True)
        label.setStyleSheet("font-weight: 600; color: #0F172A; background: transparent; border: none; line-height: 1.45;")
        layout.addWidget(label)
        grid.addWidget(card, row, column)
        return label

    def refresh_data(self) -> None:
        latest = self.db.get_latest_record(self.user["id"])
        if not latest:
            self.session_label.setText("No training result is available yet.")
            self.score_metric_label.setText("-")
            self.risk_metric_label.setText("-")
            self.plan_metric_label.setText("-")
            self.detail_text.setPlainText("")
            return

        details = self.db.get_record_details(latest["id"])
        errors = details["errors"]
        compensations = details["compensations"]
        report = details["report"]

        top_error = errors[0]["error_type"] if errors else "None"
        top_comp = compensations[0]["compensation_type"] if compensations else "None"
        error_count = sum(item.get("error_count", 0) for item in errors) if errors else 0
        comp_count = sum(item.get("detected_count", 0) for item in compensations) if compensations else 0
        recommendation = report.get("recommendation", "No recommendation available.") if report else "No recommendation available."
        self.session_label.setText(
            f"{latest['action_name']}\n"
            f"{latest['session_start']} -> {latest['session_end']}"
        )
        self.score_metric_label.setText(
            f"Avg Score: {latest['avg_score']}\n"
            f"Completion: {round((latest['completion_rate'] or 0) * 100, 2)}%\n"
            f"Reps: {latest.get('total_reps', '-')}"
        )
        self.risk_metric_label.setText(
            f"Top error: {top_error} ({error_count})\n"
            f"Top compensation: {top_comp} ({comp_count})"
        )
        self.plan_metric_label.setText(recommendation)
        content = [
            "[Session Highlights]",
            f"- Time: {latest['session_start']} -> {latest['session_end']}",
            f"- Duration: {latest['duration_seconds']} sec | Reps: {latest.get('total_reps', '-')}",
            f"- Avg Score: {latest['avg_score']} | Completion: {round((latest['completion_rate'] or 0) * 100, 2)}%",
            "",
            "[Quality Risks]",
            f"- Top error: {top_error}",
            f"- Error count: {error_count}",
            f"- Top compensation: {top_comp}",
            f"- Compensation count: {comp_count}",
            "",
            "[Session Summary]",
            f"- {latest['summary']}",
        ]
        if report:
            content.extend(["", "[Doctor Recommendation]", f"- {recommendation}"])

        self.detail_text.setPlainText("\n".join(content))
