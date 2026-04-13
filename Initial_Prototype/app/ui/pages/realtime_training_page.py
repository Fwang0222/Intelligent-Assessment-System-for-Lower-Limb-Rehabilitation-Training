"""Real-time training page using a mock algorithm pipeline."""

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout

from app.services.training_service import TrainingSessionManager
from app.ui.base import BasePage
from app.ui.fluent_compat import (
    BodyLabel,
    ComboBox,
    InfoBar,
    InfoBarPosition,
    PrimaryPushButton,
    ProgressBar,
    SubtitleLabel,
    TextEdit,
)


class RealtimeTrainingPage(BasePage):
    def __init__(self, db, user, refresh_callback=None, parent=None):
        self.refresh_callback = refresh_callback
        super().__init__(db, user, parent)
        self.session_manager = TrainingSessionManager()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_timer_tick)
        self.latest_session_payload = None
        self.setup_ui()
        self.refresh_data()

    def setup_ui(self) -> None:
        self.main_layout.addWidget(SubtitleLabel("Real-Time Training"))
        self.main_layout.addWidget(
            BodyLabel(
                "This version uses a simulated algorithm pipeline. It can later be replaced "
                "with camera input, YOLO-based motion analysis, and LLM-generated feedback."
            )
        )

        top_layout = QHBoxLayout()
        self.action_combo = ComboBox()
        self.start_btn = PrimaryPushButton("Start Training")
        self.stop_btn = PrimaryPushButton("Stop and Save")
        self.stop_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.start_training)
        self.stop_btn.clicked.connect(self.stop_training)
        top_layout.addWidget(BodyLabel("Target action:"))
        top_layout.addWidget(self.action_combo)
        top_layout.addWidget(self.start_btn)
        top_layout.addWidget(self.stop_btn)
        top_layout.addStretch(1)
        self.main_layout.addLayout(top_layout)

        grid = QGridLayout()
        self.camera_label = QLabel(
            "Camera stream placeholder\n"
            "You can connect OpenCV / MediaPipe / YOLO video processing here later."
        )
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setMinimumHeight(260)
        self.camera_label.setStyleSheet("border: 1px dashed #999; font-size: 16px; padding: 16px;")

        right_widget = QVBoxLayout()
        self.current_action_label = BodyLabel("Recognized action: -")
        self.score_label = BodyLabel("Current score: -")
        self.progress = ProgressBar()
        self.progress.setRange(0, 100)
        self.error_text = TextEdit()
        self.error_text.setReadOnly(True)
        self.feedback_text = TextEdit()
        self.feedback_text.setReadOnly(True)

        right_widget.addWidget(self.current_action_label)
        right_widget.addWidget(self.score_label)
        right_widget.addWidget(BodyLabel("Motion quality score:"))
        right_widget.addWidget(self.progress)
        right_widget.addWidget(BodyLabel("Detected errors / compensations:"))
        right_widget.addWidget(self.error_text)
        right_widget.addWidget(BodyLabel("Real-time coaching feedback:"))
        right_widget.addWidget(self.feedback_text)

        grid.addWidget(self.camera_label, 0, 0)
        grid.addLayout(right_widget, 0, 1)
        self.main_layout.addLayout(grid)
        self.main_layout.addStretch(1)

    def refresh_data(self) -> None:
        self.action_combo.clear()
        plans = self.db.get_plans(self.user["id"])
        if plans:
            for plan in plans:
                self.action_combo.addItem(f"{plan['plan_name']} - {plan['target_action']}", plan)
            active_plan = self.db.get_active_plan(self.user["id"])
            if active_plan:
                for i, plan in enumerate(plans):
                    if plan["id"] == active_plan["id"]:
                        self.action_combo.setCurrentIndex(i)
                        break
        else:
            self.action_combo.addItem("Default Plan - Seated Knee Raise", {"id": None, "target_action": "Seated Knee Raise"})

    def start_training(self) -> None:
        plan = self.action_combo.currentData()
        expected_action = plan["target_action"] if plan else "Seated Knee Raise"
        self.session_manager.start(expected_action)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.error_text.setPlainText("")
        self.feedback_text.setPlainText("")
        self.current_action_label.setText(f"Recognized action: {expected_action}")
        self.score_label.setText("Current score: collecting data...")
        self.progress.setValue(0)
        self.timer.start(1000)
        InfoBar.success("Training Started", f"Training has started for {expected_action}.", position=InfoBarPosition.TOP, parent=self)

    def on_timer_tick(self) -> None:
        result = self.session_manager.process_next_step()
        self.current_action_label.setText(f"Recognized action: {result['action_label']}  |  Time: {result['timestamp']}")
        self.score_label.setText(
            f"Current score: {result['total_score']}  "
            f"(Accuracy {result['accuracy_score']}, Stability {result['stability_score']})"
        )
        self.progress.setValue(int(result["total_score"]))

        lines = []
        for err in result["errors"]:
            lines.append(f"Error action: {err['error_type']} | Suggestion: {err['suggestion']}")
        for comp in result["compensations"]:
            lines.append(f"Compensation action: {comp['compensation_type']} | Suggestion: {comp['suggestion']}")
        if not lines:
            lines.append("No obvious error or compensation has been detected so far.")
        self.error_text.setPlainText("\n".join(lines))
        self.feedback_text.setPlainText("\n".join(result["feedbacks"]))

    def stop_training(self) -> None:
        self.timer.stop()
        payload = self.session_manager.stop()
        self.latest_session_payload = payload

        selected_plan = self.action_combo.currentData()
        plan_id = selected_plan["id"] if selected_plan else None
        record_id = self.db.save_training_session(self.user["id"], plan_id, payload)

        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.score_label.setText(f"Training saved. Record ID: {record_id}, average score: {payload['avg_score']}")
        self.feedback_text.setPlainText(payload["summary"] + "\n\nDoctor recommendation:\n" + payload["doctor_recommendation"])
        if self.refresh_callback:
            self.refresh_callback()
        InfoBar.success("Saved", f"Training record #{record_id} has been saved.", position=InfoBarPosition.TOP, parent=self)
