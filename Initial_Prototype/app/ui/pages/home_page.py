"""Dashboard page showing the latest high-level rehab information."""

from PySide6.QtWidgets import QGridLayout, QVBoxLayout

from app.ui.base import BasePage
from app.ui.fluent_compat import BodyLabel, CardWidget, SubtitleLabel


class HomePage(BasePage):
    def __init__(self, db, user, parent=None):
        super().__init__(db, user, parent)
        self.cards = {}
        self.setup_ui()
        self.refresh_data()

    def setup_ui(self) -> None:
        self.main_layout.addWidget(SubtitleLabel("Dashboard"))
        grid = QGridLayout()
        grid.setSpacing(16)

        for key, title in [
            ("user", "User Information"),
            ("profile", "Rehab Profile Summary"),
            ("plan", "Current Training Plan"),
            ("latest", "Latest Training Session"),
        ]:
            card = CardWidget()
            layout = QVBoxLayout(card)
            layout.addWidget(SubtitleLabel(title))
            label = BodyLabel("")
            layout.addWidget(label)
            self.cards[key] = label
            grid.addWidget(card, 0 if key in ["user", "profile"] else 1, 0 if key in ["user", "plan"] else 1)

        self.main_layout.addLayout(grid)

    def refresh_data(self) -> None:
        profile = self.db.get_user_profile(self.user["id"])
        plan = self.db.get_active_plan(self.user["id"])
        latest = self.db.get_latest_record(self.user["id"])

        self.cards["user"].setText(
            f"Full name: {self.user['full_name']}\n"
            f"Role: {self.user['role']}\n"
            f"Age: {self.user.get('age', '-') or '-'}\n"
            f"Phone: {self.user.get('phone', '-') or '-'}"
        )

        self.cards["profile"].setText(
            "No rehab profile available."
            if not profile else
            f"Diagnosis: {profile.get('diagnosis', '')}\n"
            f"Affected side: {profile.get('affected_side', '')}\n"
            f"Stage: {profile.get('rehab_stage', '')}\n"
            f"Pain score: {profile.get('pain_level', 0)}"
        )

        self.cards["plan"].setText(
            "No active training plan available."
            if not plan else
            f"Plan: {plan['plan_name']}\n"
            f"Action: {plan['target_action']}\n"
            f"Difficulty: {plan['difficulty_level']}\n"
            f"Volume: {plan['sets_count']} sets x {plan['reps_count']} reps"
        )

        self.cards["latest"].setText(
            "No training record available."
            if not latest else
            f"Action: {latest['action_name']}\n"
            f"Average score: {latest['avg_score']}\n"
            f"Completion rate: {round((latest['completion_rate'] or 0) * 100, 2)}%\n"
            f"End time: {latest['session_end']}"
        )
