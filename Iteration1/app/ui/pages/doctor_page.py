"""Doctor dashboard page for decision support."""

from PySide6.QtWidgets import QGridLayout

from app.ui.base import BasePage
from app.ui.fluent_compat import BodyLabel, PageTitleLabel, PrimaryPushButton, TextEdit


class DoctorPage(BasePage):
    def __init__(self, db, user, parent=None):
        super().__init__(db, user, parent)
        self.setup_ui()
        self.refresh_data()

    def setup_ui(self) -> None:
        self.main_layout.addWidget(PageTitleLabel("Doctor Decision Support"))
        overview_card, overview_layout = self.create_section_card(
            "Clinical Summary",
            "Patient profile, trends, high-frequency errors, and adjustment recommendation.",
        )
        self.refresh_btn = PrimaryPushButton("Refresh Doctor Summary")
        self.refresh_btn.clicked.connect(self.refresh_data)
        overview_layout.addWidget(self.refresh_btn)
        summary_grid = QGridLayout()
        summary_grid.setContentsMargins(0, 0, 0, 0)
        summary_grid.setHorizontalSpacing(10)
        summary_grid.setVerticalSpacing(10)
        self.patient_label = self._create_summary_card(summary_grid, 0, 0, "Patient")
        self.trend_label = self._create_summary_card(summary_grid, 0, 1, "Trend")
        self.risk_label = self._create_summary_card(summary_grid, 1, 0, "Risk Focus")
        self.recommendation_label = self._create_summary_card(summary_grid, 1, 1, "Decision")
        overview_layout.addLayout(summary_grid)
        self.main_layout.addWidget(overview_card)

        card, layout = self.create_section_card("Detailed Clinical Notes")
        self.report_text = TextEdit()
        self.report_text.setReadOnly(True)
        layout.addWidget(self.report_text)
        self.main_layout.addWidget(card, 1)

    def _create_summary_card(self, grid: QGridLayout, row: int, column: int, title: str):
        card, layout = self.create_section_card(title)
        label = BodyLabel("-")
        label.setWordWrap(True)
        label.setStyleSheet("font-weight: 600; color: #0F172A; background: transparent; border: none; line-height: 1.45;")
        layout.addWidget(label)
        grid.addWidget(card, row, column)
        return label

    def refresh_data(self) -> None:
        info = self.db.get_doctor_dashboard(self.user["id"])
        user = info.get("user") or {}
        profile = info.get("profile") or {}
        summary = info.get("summary") or {}
        recent = info.get("recent_records") or []
        errors = info.get("errors") or []
        comps = info.get("compensations") or []

        top_error = errors[0]["label"] if errors else "None"
        top_comp = comps[0]["label"] if comps else "None"
        latest = recent[0] if recent else None
        self.patient_label.setText(
            f"{user.get('full_name', '-')}\n"
            f"Stage: {user.get('rehab_stage', '-')}\n"
            f"Diagnosis: {profile.get('diagnosis', '-')}"
        )
        self.trend_label.setText(
            f"Trend: {summary.get('trend', '-')}\n"
            f"Avg Score: {summary.get('avg_score', 0)}\n"
            f"Completion: {summary.get('avg_completion', 0)}%"
        )
        self.risk_label.setText(
            f"Top error: {top_error}\n"
            f"Top compensation: {top_comp}"
        )
        self.recommendation_label.setText(info.get("recommendation", "No recommendation available."))
        lines = [
            "[Clinical Highlights]",
            f"- Patient: {user.get('full_name', '-')} | Stage: {user.get('rehab_stage', '-')}",
            f"- Diagnosis: {profile.get('diagnosis', '-')}",
            f"- Trend: {summary.get('trend', '-')} | Avg Score: {summary.get('avg_score', 0)} | Completion: {summary.get('avg_completion', 0)}%",
            f"- Risk Focus: Error({top_error}) / Compensation({top_comp})",
            "",
            "[Latest Session]",
            "- No recent session." if not latest else
            f"- #{latest['id']} | {latest['action_name']} | Score {latest['avg_score']} | Completion {round((latest['completion_rate'] or 0) * 100, 2)}%",
            "",
            "[Decision Suggestion]",
            f"- {info.get('recommendation', 'No recommendation available.')}",
        ]
        self.report_text.setPlainText("\n".join(lines))
