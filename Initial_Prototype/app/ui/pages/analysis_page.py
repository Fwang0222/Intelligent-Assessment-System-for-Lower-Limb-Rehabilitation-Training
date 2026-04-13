"""Simple analysis page showing training statistics and plan changes."""

from PySide6.QtWidgets import QGridLayout, QVBoxLayout

from app.ui.base import BasePage
from app.ui.fluent_compat import BodyLabel, CardWidget, SubtitleLabel, TextEdit


class AnalysisPage(BasePage):
    def __init__(self, db, user, parent=None):
        super().__init__(db, user, parent)
        self.cards = {}
        self.setup_ui()
        self.refresh_data()

    def setup_ui(self) -> None:
        self.main_layout.addWidget(SubtitleLabel("Data Analysis"))
        grid = QGridLayout()
        for idx, (key, title) in enumerate([
            ("count", "Session Count"),
            ("avg", "Average Score"),
            ("best", "Best Score"),
            ("trend", "Trend"),
            ("completion", "Average Completion"),
            ("pain", "Average Pain Score"),
        ]):
            card = CardWidget()
            layout = QVBoxLayout(card)
            layout.addWidget(SubtitleLabel(title))
            label = BodyLabel("-")
            layout.addWidget(label)
            self.cards[key] = label
            grid.addWidget(card, idx // 3, idx % 3)
        self.main_layout.addLayout(grid)

        self.detail_text = TextEdit()
        self.detail_text.setReadOnly(True)
        self.main_layout.addWidget(self.detail_text)

    def refresh_data(self) -> None:
        info = self.db.get_analysis_summary(self.user["id"])
        self.cards["count"].setText(str(info["session_count"]))
        self.cards["avg"].setText(str(info["avg_score"]))
        self.cards["best"].setText(str(info["best_score"]))
        self.cards["trend"].setText(info["trend"])
        self.cards["completion"].setText(f"{info['avg_completion']}%")
        self.cards["pain"].setText(str(info["avg_pain"]))

        adjustments = self.db.get_plan_adjustments(self.user["id"])
        lines = [
            "Trend analysis summary:",
            f"- Recent training trend: {info['trend']}",
            f"- Average completion rate: {info['avg_completion']}%",
            f"- Average pain feedback: {info['avg_pain']}",
            "",
            "Plan adjustment history:",
        ]
        if adjustments:
            for item in adjustments[:10]:
                lines.append(f"- {item['created_at']} | {item['adjustment_reason']} | {item['adjustment_detail']}")
        else:
            lines.append("- No plan adjustment records available.")

        self.detail_text.setPlainText("\n".join(lines))
