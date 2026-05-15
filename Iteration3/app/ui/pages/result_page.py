"""Result page redesigned around score, risk, and doctor follow-up."""

from PySide6.QtWidgets import QGridLayout, QHBoxLayout

from app.services.report_export_service import ReportExportService
from app.ui.base import BasePage
from app.ui.fluent_compat import (
    BodyLabel,
    CaptionLabel,
    InfoBar,
    InfoBarPosition,
    PageTitleLabel,
    PillLabel,
    PrimaryPushButton,
    PushButton,
    TextEdit,
    ValueLabel,
)


class ResultPage(BasePage):
    def __init__(self, db, user, parent=None):
        super().__init__(db, user, parent)
        self.can_export = user.get("role") == "doctor"
        self.export_service = ReportExportService(db)
        self.latest_record_id = None
        self.setup_ui()
        self.refresh_data()

    def setup_ui(self) -> None:
        self.main_layout.setContentsMargins(18, 14, 18, 14)
        self.main_layout.setSpacing(12)
        self.main_layout.addWidget(PageTitleLabel("Training Results"))

        hero_card, hero_layout = self.create_section_card()
        hero_top = QHBoxLayout()
        hero_top.setContentsMargins(0, 0, 0, 0)
        hero_top.setSpacing(10)
        self.session_title = ValueLabel("Latest Session")
        self.review_badge = PillLabel("Awaiting Review", "orange")
        hero_top.addWidget(self.session_title, 1)
        hero_top.addWidget(self.review_badge)
        hero_layout.addLayout(hero_top)
        self.hero_note = BodyLabel("")
        hero_layout.addWidget(self.hero_note)

        if self.can_export:
            toolbar = QHBoxLayout()
            toolbar.setContentsMargins(0, 0, 0, 0)
            toolbar.setSpacing(8)
            self.export_pdf_btn = PrimaryPushButton("Export PDF")
            self.export_json_btn = PushButton("Export JSON")
            self.export_pdf_btn.clicked.connect(self.export_pdf)
            self.export_json_btn.clicked.connect(self.export_json)
            toolbar.addWidget(self.export_pdf_btn)
            toolbar.addWidget(self.export_json_btn)
            toolbar.addStretch(1)
            hero_layout.addLayout(toolbar)
        self.main_layout.addWidget(hero_card)

        metric_grid = QGridLayout()
        metric_grid.setContentsMargins(0, 0, 0, 0)
        metric_grid.setHorizontalSpacing(10)
        metric_grid.setVerticalSpacing(10)
        self.metric_blocks = {}
        for idx, (key, title) in enumerate(
            [
                ("score", "Score"),
                ("completion", "Completion"),
                ("risk", "Risk Focus"),
                ("review", "Care Review"),
            ]
        ):
            card, layout = self.create_section_card()
            title_label = BodyLabel(title)
            title_label.setStyleSheet("font-weight: 700; color: #0F172A; background: transparent; border: none;")
            value_label = ValueLabel("-")
            note_label = CaptionLabel("-")
            layout.addWidget(title_label)
            layout.addWidget(value_label)
            layout.addWidget(note_label)
            self.metric_blocks[key] = (value_label, note_label)
            metric_grid.addWidget(card, 0, idx)
        self.main_layout.addLayout(metric_grid)

        detail_grid = QGridLayout()
        detail_grid.setContentsMargins(0, 0, 0, 0)
        detail_grid.setHorizontalSpacing(10)
        detail_grid.setVerticalSpacing(10)

        performance_card, performance_layout = self.create_section_card("Performance Snapshot")
        self.performance_text = BodyLabel("")
        performance_layout.addWidget(self.performance_text)
        detail_grid.addWidget(performance_card, 0, 0)

        risk_card, risk_layout = self.create_section_card("Risk Board")
        self.risk_text = BodyLabel("")
        risk_layout.addWidget(self.risk_text)
        detail_grid.addWidget(risk_card, 0, 1)

        process_card, process_layout = self.create_section_card("Care Process", "Result, review status, and next management step.")
        self.process_text = BodyLabel("")
        process_layout.addWidget(self.process_text)
        detail_grid.addWidget(process_card, 1, 0)

        plan_card, plan_layout = self.create_section_card("Recommendation")
        self.plan_text = BodyLabel("")
        plan_layout.addWidget(self.plan_text)
        detail_grid.addWidget(plan_card, 1, 1)

        self.main_layout.addLayout(detail_grid)

        note_card, note_layout = self.create_section_card("Detailed Notes")
        self.detail_text = TextEdit()
        self.detail_text.setReadOnly(True)
        note_layout.addWidget(self.detail_text)
        self.main_layout.addWidget(note_card, 1)

    def _set_metric(self, key: str, value: str, note: str) -> None:
        self.metric_blocks[key][0].setText(value)
        self.metric_blocks[key][1].setText(note)

    @staticmethod
    def _short(text, limit: int = 110) -> str:
        text = str(text or "-").replace("\n", " ").strip()
        return text if len(text) <= limit else text[: limit - 1].rstrip() + "..."

    def refresh_data(self) -> None:
        latest = self.db.get_latest_record(self.user["id"])
        if not latest:
            self.latest_record_id = None
            self.session_title.setText("Latest Session")
            self.review_badge.setText("No Data")
            self.review_badge.setTone("slate")
            self.hero_note.setText("No training result is available yet.")
            for key in self.metric_blocks:
                self._set_metric(key, "-", "No data")
            self.performance_text.setText("No session summary.")
            self.risk_text.setText("No risk summary.")
            self.process_text.setText("Complete a session first.")
            self.plan_text.setText("No recommendation.")
            self.detail_text.setPlainText("")
            return

        self.latest_record_id = int(latest["id"])
        details = self.db.get_record_details(self.latest_record_id)
        errors = details.get("errors", [])
        compensations = details.get("compensations", [])
        report = details.get("report") or {}
        interventions = details.get("interventions", [])
        latest_intervention = interventions[0] if interventions else None

        top_error = errors[0]["error_type"] if errors else "None"
        top_comp = compensations[0]["compensation_type"] if compensations else "None"
        error_count = sum(item.get("error_count", 0) for item in errors)
        comp_count = sum(item.get("detected_count", 0) for item in compensations)
        total_score = round(float(latest.get("avg_score", 0) or 0), 1)
        completion_pct = round((latest.get("completion_rate", 0) or 0) * 100, 1)

        review_status = latest_intervention.get("review_status", "pending") if latest_intervention else "pending"
        review_text = {
            "approved": "Reviewed",
            "needs_review": "Needs Review",
            "adjusted": "Plan Adjusted",
            "pending": "Awaiting Review",
        }.get(review_status, "Awaiting Review")
        review_tone = {
            "approved": "green",
            "needs_review": "red",
            "adjusted": "blue",
            "pending": "orange",
        }.get(review_status, "orange")

        self.session_title.setText(latest.get("action_name", "Latest Session"))
        self.review_badge.setText(review_text)
        self.review_badge.setTone(review_tone)
        self.hero_note.setText(
            f"{latest.get('session_start', '-')} -> {latest.get('session_end', '-')} | "
            f"Duration {latest.get('duration_seconds', '-')} sec | "
            f"Pain {latest.get('pain_feedback', 0)}"
        )

        self._set_metric("score", str(total_score), "Average quality score")
        self._set_metric("completion", f"{completion_pct}%", "Target volume completed")
        self._set_metric("risk", top_error if top_error != "None" else top_comp, "Main issue detected")
        self._set_metric("review", review_text, "Latest care-team review status")

        self.performance_text.setText(
            "\n".join(
                [
                    f"Action: {latest.get('action_name', '-')}",
                    f"Score: {total_score} | Completion: {completion_pct}%",
                    f"Duration: {latest.get('duration_seconds', '-')} sec | Pain: {latest.get('pain_feedback', 0)}",
                    f"Summary: {self._short(latest.get('summary', '-'))}",
                ]
            )
        )
        self.risk_text.setText(
            "\n".join(
                [
                    f"Top error: {top_error} ({error_count})",
                    f"Top compensation: {top_comp} ({comp_count})",
                    "Main focus: reduce asymmetry, instability, or trunk compensation first.",
                ]
            )
        )
        self.process_text.setText(
            "\n".join(
                [
                    f"Session result: score {total_score}",
                    f"Care review: {review_text}",
                    f"Record status: {latest.get('status', 'completed')}",
                    "Next step: continue, adjust plan, or request reassessment.",
                ]
            )
        )

        recommendation = report.get("recommendation", "No recommendation available.")
        if latest_intervention and latest_intervention.get("note"):
            recommendation = latest_intervention.get("note")
        self.plan_text.setText(
            "\n".join(
                [
                    f"Recommendation: {self._short(recommendation)}",
                    "Plan changes are managed by the care team.",
                ]
            )
        )

        notes = [
            "[Session]",
            f"- Time: {latest.get('session_start', '-')} -> {latest.get('session_end', '-')}",
            f"- Score: {total_score} | Completion: {completion_pct}%",
            f"- Duration: {latest.get('duration_seconds', '-')} sec | Pain: {latest.get('pain_feedback', 0)}",
            "",
            "[Main Risk]",
            f"- Error: {top_error}",
            f"- Compensation: {top_comp}",
            f"- Error count: {error_count} | Compensation count: {comp_count}",
            "",
            "[Recommendation]",
            f"- {recommendation}",
        ]
        if latest_intervention:
            notes.extend(
                [
                    "",
                    "[Care Team Review]",
                    f"- Status: {review_text}",
                    f"- Note: {latest_intervention.get('note', '-') or '-'}",
                    f"- Time: {latest_intervention.get('created_at', '-')}",
                ]
            )
        self.detail_text.setPlainText("\n".join(notes))

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
            InfoBar.success("Exported", f"JSON exported to: {result['path']}", position=InfoBarPosition.TOP, parent=self)
        except Exception as exc:
            InfoBar.error("Export Failed", str(exc), position=InfoBarPosition.TOP, parent=self)
