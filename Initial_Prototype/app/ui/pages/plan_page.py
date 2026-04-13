"""Page for creating and activating training plans."""

from PySide6.QtWidgets import QFormLayout, QHBoxLayout, QTableWidgetItem

from app.ui.base import BasePage
from app.ui.fluent_compat import (
    BodyLabel,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    PrimaryPushButton,
    SubtitleLabel,
    TableWidget,
    TextEdit,
)


class PlanPage(BasePage):
    def __init__(self, db, user, refresh_callback=None, parent=None):
        self.refresh_callback = refresh_callback
        super().__init__(db, user, parent)
        self.setup_ui()
        self.refresh_data()

    def setup_ui(self) -> None:
        self.main_layout.addWidget(SubtitleLabel("Training Plans"))
        self.main_layout.addWidget(BodyLabel("Create a plan and set one plan as the current active program."))

        form = QFormLayout()
        self.plan_name_edit = LineEdit()
        self.action_edit = LineEdit()
        self.difficulty_edit = LineEdit()
        self.sets_edit = LineEdit()
        self.reps_edit = LineEdit()
        self.duration_edit = LineEdit()
        self.rest_edit = LineEdit()
        self.desc_edit = TextEdit()
        self.desc_edit.setFixedHeight(90)

        self.plan_name_edit.setText("New Lower-Limb Plan")
        self.action_edit.setText("Seated Knee Raise")
        self.difficulty_edit.setText("Low")
        self.sets_edit.setText("3")
        self.reps_edit.setText("10")
        self.duration_edit.setText("15")
        self.rest_edit.setText("30")

        form.addRow("Plan name:", self.plan_name_edit)
        form.addRow("Target action:", self.action_edit)
        form.addRow("Difficulty level:", self.difficulty_edit)
        form.addRow("Number of sets:", self.sets_edit)
        form.addRow("Repetitions per set:", self.reps_edit)
        form.addRow("Duration (minutes):", self.duration_edit)
        form.addRow("Rest between sets (seconds):", self.rest_edit)
        form.addRow("Description:", self.desc_edit)
        self.main_layout.addLayout(form)

        button_layout = QHBoxLayout()
        self.create_btn = PrimaryPushButton("Create Plan")
        self.activate_btn = PrimaryPushButton("Set as Active")
        self.create_btn.clicked.connect(self.create_plan)
        self.activate_btn.clicked.connect(self.activate_plan)
        button_layout.addWidget(self.create_btn)
        button_layout.addWidget(self.activate_btn)
        button_layout.addStretch(1)
        self.main_layout.addLayout(button_layout)

        self.table = TableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["ID", "Plan Name", "Action", "Difficulty", "Sets", "Reps", "Minutes", "Active"])
        self.main_layout.addWidget(self.table)

    def refresh_data(self) -> None:
        plans = self.db.get_plans(self.user["id"])
        self.table.setRowCount(len(plans))
        for row, plan in enumerate(plans):
            values = [
                plan["id"],
                plan["plan_name"],
                plan["target_action"],
                plan["difficulty_level"],
                plan["sets_count"],
                plan["reps_count"],
                plan["duration_minutes"],
                "Yes" if plan["is_active"] else "No",
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(str(value)))
        self.table.resizeColumnsToContents()

    def create_plan(self) -> None:
        try:
            data = {
                "plan_name": self.plan_name_edit.text().strip() or "New Lower-Limb Plan",
                "target_action": self.action_edit.text().strip() or "Seated Knee Raise",
                "difficulty_level": self.difficulty_edit.text().strip() or "Low",
                "sets_count": int(self.sets_edit.text().strip() or 3),
                "reps_count": int(self.reps_edit.text().strip() or 10),
                "duration_minutes": int(self.duration_edit.text().strip() or 15),
                "rest_seconds": int(self.rest_edit.text().strip() or 30),
                "description": self.desc_edit.toPlainText().strip(),
                "is_active": 0,
            }
        except ValueError:
            InfoBar.warning(
                "Input Error",
                "Sets, repetitions, duration, and rest time must be numeric values.",
                position=InfoBarPosition.TOP,
                parent=self,
            )
            return

        self.db.create_plan(self.user["id"], data)
        self.refresh_data()
        if self.refresh_callback:
            self.refresh_callback()
        InfoBar.success("Created", "The training plan has been created.", position=InfoBarPosition.TOP, parent=self)

    def activate_plan(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            InfoBar.warning("Notice", "Please select a training plan first.", position=InfoBarPosition.TOP, parent=self)
            return
        plan_id_item = self.table.item(row, 0)
        if plan_id_item is None:
            return
        plan_id = int(plan_id_item.text())
        self.db.activate_plan(self.user["id"], plan_id)
        self.refresh_data()
        if self.refresh_callback:
            self.refresh_callback()
        InfoBar.success("Updated", "The active training plan has been updated.", position=InfoBarPosition.TOP, parent=self)
