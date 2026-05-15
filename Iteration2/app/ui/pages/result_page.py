"""Result page for the latest training session."""

from PySide6.QtWidgets import QGridLayout, QHBoxLayout

from app.services.report_export_service import ReportExportService
from app.ui.base import BasePage
from app.ui.fluent_compat import (
    BodyLabel,
    InfoBar,
    InfoBarPosition,
    PageTitleLabel,
    PrimaryPushButton,
    PushButton,
    TextEdit,
)


class ResultPage(BasePage):
    def __init__(self, db, user, parent=None):
        super().__init__(db, user, parent)
        self.export_service = ReportExportService(db)
        self.latest_record_id = None
        self.setup_ui()
        self.refresh_data()

    def setup_ui(self) -> None:
        self.main_layout.addWidget(PageTitleLabel("Training Results"))

        toolbar_card, toolbar_layout = self.create_section_card(
            "Report Actions",
            "Export the latest structured training report for doctor review, archive, or API integration.",
        )
        toolbar_row = QHBoxLayout()
        toolbar_row.setContentsMargins(0, 0, 0, 0)
        toolbar_row.setSpacing(8)
        self.export_pdf_btn = PrimaryPushButton("Export PDF")
        self.export_json_btn = PushButton("Export API JSON")
        self.export_pdf_btn.clicked.connect(self.export_pdf)
        self.export_json_btn.clicked.connect(self.export_json)
        toolbar_row.addWidget(self.export_pdf_btn)
        toolbar_row.addWidget(self.export_json_btn)
        toolbar_row.addStretch(1)
        toolbar_layout.addLayout(toolbar_row)
        self.main_layout.addWidget(toolbar_card)

        summary_grid = QGridLayout()
        summary_grid.setContentsMargins(0, 0, 0, 0)
        summary_grid.setHorizontalSpacing(10)
        summary_grid.setVerticalSpacing(10)
        self.session_label = self._create_metric_card(summary_grid, 0, 0, "Session")
        self.score_metric_label = self._create_metric_card(summary_grid, 0, 1, "Score")
        self.risk_metric_label = self._create_metric_card(summary_grid, 1, 0, "Risk Focus")
        self.plan_metric_label = self._create_metric_card(summary_grid, 1, 1, "Recommendation")
        self.main_layout.addLayout(summary_grid)

        detail_card, detail_layout = self.create_section_card(
            "Detailed Report",
            "Structured summary for the latest completed session, suitable for doctor-side follow-up and export.",
        )
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
            self.latest_record_id = None
            self.session_label.setText("No training result is available yet.")
            self.score_metric_label.setText("-")
            self.risk_metric_label.setText("-")
            self.plan_metric_label.setText("-")
            self.detail_text.setPlainText("")
            return

        self.latest_record_id = int(latest["id"])
        details = self.db.get_record_details(self.latest_record_id)
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
            f"Duration: {latest.get('duration_seconds', '-') } sec"
        )
        self.risk_metric_label.setText(
            f"Top error: {top_error} ({error_count})\n"
            f"Top compensation: {top_comp} ({comp_count})"
        )
        self.plan_metric_label.setText(recommendation)
        content = [
            "[Session Highlights]",
            f"- Time: {latest['session_start']} -> {latest['session_end']}",
            f"- Duration: {latest['duration_seconds']} sec",
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

    def export_pdf(self) -> None:
        if not self.latest_record_id:
            InfoBar.warning("No Record", "No training record is available for export.", position=InfoBarPosition.TOP, parent=self)
            return
        try:
            result = self.export_service.export_pdf(
                viewer_user_id=self.user["id"],
                training_record_id=self.latest_record_id,
            )
            InfoBar.success("Exported", f"PDF report exported to: {result['path']}", position=InfoBarPosition.TOP, parent=self)
        except Exception as exc:
            InfoBar.error("Export Failed", str(exc), position=InfoBarPosition.TOP, parent=self)

    def export_json(self) -> None:
        if not self.latest_record_id:
            InfoBar.warning("No Record", "No training record is available for export.", position=InfoBarPosition.TOP, parent=self)
            return
        try:
            result = self.export_service.export_json(
                viewer_user_id=self.user["id"],
                training_record_id=self.latest_record_id,
                include_full_history=False,
            )
            InfoBar.success("Exported", f"API JSON exported to: {result['path']}", position=InfoBarPosition.TOP, parent=self)
        except Exception as exc:
            InfoBar.error("Export Failed", str(exc), position=InfoBarPosition.TOP, parent=self)
