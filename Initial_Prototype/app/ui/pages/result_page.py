"""Result page for the latest training session."""

from app.ui.base import BasePage
from app.ui.fluent_compat import BodyLabel, SubtitleLabel, TextEdit


class ResultPage(BasePage):
    def __init__(self, db, user, parent=None):
        super().__init__(db, user, parent)
        self.setup_ui()
        self.refresh_data()

    def setup_ui(self) -> None:
        self.main_layout.addWidget(SubtitleLabel("Training Results"))
        self.summary_label = BodyLabel("")
        self.main_layout.addWidget(self.summary_label)
        self.detail_text = TextEdit()
        self.detail_text.setReadOnly(True)
        self.main_layout.addWidget(self.detail_text)

    def refresh_data(self) -> None:
        latest = self.db.get_latest_record(self.user["id"])
        if not latest:
            self.summary_label.setText("No training result is available yet.")
            self.detail_text.setPlainText("")
            return

        details = self.db.get_record_details(latest["id"])
        errors = details["errors"]
        compensations = details["compensations"]
        report = details["report"]

        self.summary_label.setText(
            f"Latest action: {latest['action_name']} | "
            f"Average score: {latest['avg_score']} | "
            f"Completion rate: {round((latest['completion_rate'] or 0) * 100, 2)}%"
        )

        content = [
            f"Session start: {latest['session_start']}",
            f"Session end: {latest['session_end']}",
            f"Duration: {latest['duration_seconds']} seconds",
            f"Summary: {latest['summary']}",
            "",
            "Detected error actions:",
        ]
        if errors:
            for item in errors:
                content.append(f"- {item['error_type']} x {item['error_count']} | Suggestion: {item['suggestion']}")
        else:
            content.append("- No obvious error action detected.")

        content.append("\nDetected compensation actions:")
        if compensations:
            for item in compensations:
                content.append(f"- {item['compensation_type']} x {item['detected_count']} | Suggestion: {item['suggestion']}")
        else:
            content.append("- No obvious compensation detected.")

        if report:
            content.append("\nDoctor recommendation:")
            content.append(report.get("recommendation", "No recommendation available."))

        self.detail_text.setPlainText("\n".join(content))
