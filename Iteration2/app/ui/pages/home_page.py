"""Dashboard page showing compact high-level rehab information."""

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout

from app.ui.base import BasePage
from app.ui.fluent_compat import BodyLabel, CardWidget, PageTitleLabel, SubtitleLabel


class HomePage(BasePage):
    def __init__(self, db, user, parent=None):
        super().__init__(db, user, parent)
        self.cards = {}
        self.card_titles = {}
        self.setup_ui()
        self.refresh_data()

    def setup_ui(self) -> None:
        self.main_layout.setContentsMargins(14, 8, 14, 10)
        self.main_layout.setSpacing(5)
        title = PageTitleLabel("Dashboard")
        title.setFixedHeight(20)
        self.main_layout.addWidget(title)

        self.hero_card = CardWidget()
        hero_layout = QHBoxLayout(self.hero_card)
        hero_layout.setContentsMargins(12, 8, 12, 8)
        self.welcome_label = SubtitleLabel("Welcome")
        self.quick_label = BodyLabel("")
        hero_layout.addWidget(self.welcome_label, 1)
        hero_layout.addWidget(self.quick_label, 2)
        self.main_layout.addWidget(self.hero_card)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)
        for key, title in [
            ("user", "User Information"),
            ("profile", "Rehab Profile Summary"),
            ("plan", "Current Training Plan"),
            ("latest", "Latest Training Session"),
        ]:
            card = CardWidget()
            layout = QVBoxLayout(card)
            layout.setContentsMargins(10, 8, 10, 8)
            title_label = BodyLabel(title)
            title_label.setStyleSheet("font-weight: 700; color: #1F2937;")
            layout.addWidget(title_label)
            label = BodyLabel("")
            layout.addWidget(label)
            self.card_titles[key] = title_label
            self.cards[key] = label
            grid.addWidget(card, 0 if key in ["user", "profile"] else 1, 0 if key in ["user", "plan"] else 1)
        self.main_layout.addLayout(grid, 1)

    def refresh_data(self) -> None:
        security = self.db.get_security_overview(self.user["id"])
        storage_text = security.get("storage_backend", self.db.storage_label())
        profile = self.db.get_user_profile(self.user["id"])
        plan = self.db.get_active_plan(self.user["id"])
        latest = self.db.get_latest_record(self.user["id"])
        summary_score = "-" if not latest else str(latest.get("avg_score", "-"))
        summary_completion = "-" if not latest else f"{round((latest.get('completion_rate') or 0) * 100, 2)}%"

        if self.user.get("role") == "doctor":
            linked_patients = self.db.get_patient_list_for_doctor(self.user["id"])
            audits = self.db.get_audit_logs(actor_user_id=self.user["id"], limit=3)
            self.card_titles["profile"].setText("Remote Access Summary")
            self.card_titles["plan"].setText("Cloud Security")
            self.card_titles["latest"].setText("Recent Audit Activity")
            self.welcome_label.setText(f"Welcome, {self.user.get('full_name', 'Doctor')}")
            self.quick_label.setText(
                f"Remote patients: {len(linked_patients)}"
                f"   |   Storage: {storage_text}"
                f"   |   AI policy: {security.get('ai_policy', 'Local YOLO + Local/edge Qwen')}"
            )
            self.cards["user"].setText(
                f"Full name: {self.user['full_name']}\n"
                f"Role: {self.user['role']}\n"
                f"Phone: {self.user.get('phone', '-') or '-'}\n"
                f"Workstation: {self.db.config.workstation_id}"
            )
            self.cards["profile"].setText(
                f"Linked patients: {len(linked_patients)}\n"
                f"Remote doctor access: {'Enabled' if security.get('remote_doctor_access') else 'Disabled'}\n"
                f"Latest backup: {security.get('latest_backup_at', '-')}"
            )
            self.cards["plan"].setText(
                f"Storage backend: {storage_text}\n"
                f"DB/TLS mode: {security.get('ssl_mode', '-')}\n"
                f"Audit events tracked: {security.get('audit_event_count', 0)}"
            )
            if audits:
                self.cards["latest"].setText(
                    "\n".join(
                        [
                            f"{item.get('created_at', '-')}: {item.get('action_type', '-')}"
                            for item in audits[:3]
                        ]
                    )
                )
            else:
                self.cards["latest"].setText("No recent audit activity.")
            return

        self.card_titles["profile"].setText("Rehab Profile Summary")
        self.card_titles["plan"].setText("Current Training Plan")
        self.card_titles["latest"].setText("Latest Training Session")
        self.welcome_label.setText(f"Welcome, {self.user.get('full_name', 'User')}")
        self.quick_label.setText(
            f"Current action: {(plan or {}).get('target_action', '-')}"
            f"   |   Latest score: {summary_score}"
            f"   |   Completion: {summary_completion}"
            f"   |   Storage: {storage_text}"
        )

        self.cards["user"].setText(
            f"Full name: {self.user['full_name']}\n"
            f"Role: {self.user['role']}\n"
            f"Age: {self.user.get('age', '-') or '-'}\n"
            f"Height/Weight: {self.user.get('height_cm', '-') or '-'} cm / {self.user.get('weight_kg', '-') or '-'} kg\n"
            f"Injured part: {self.user.get('injured_part', '-') or '-'}\n"
            f"Affected side: {self.user.get('affected_side', '-') or '-'}\n"
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
