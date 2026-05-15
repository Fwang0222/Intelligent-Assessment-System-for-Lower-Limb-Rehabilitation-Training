"""Page for creating and activating training plans."""

from PySide6.QtWidgets import QFormLayout, QGridLayout, QHBoxLayout, QHeaderView, QTableWidgetItem

from app.core.rehab_actions import DEFAULT_ACTION_NAME
from app.ui.base import BasePage
from app.ui.fluent_compat import (
    BodyLabel,
    FormLabel,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    PageTitleLabel,
    PrimaryPushButton,
    TableWidget,
    TextEdit,
)


class PlanPage(BasePage):
    def __init__(self, db, user, refresh_callback=None, parent=None):
        self.refresh_callback = refresh_callback
        self.can_manage = user.get("role") == "doctor"
        super().__init__(db, user, parent)
        self.setup_ui()
        self.refresh_data()

    def setup_ui(self) -> None:
        self.main_layout.addWidget(PageTitleLabel("Training Plans"))

        form_card, form_card_layout = self.create_section_card("Plan Editor")
        self.form_card = form_card
        form_grid = QGridLayout()
        form_grid.setContentsMargins(8, 4, 8, 4)
        form_grid.setHorizontalSpacing(0)
        form_grid.setVerticalSpacing(8)
        left_form = QFormLayout()
        right_form = QFormLayout()
        for form in (left_form, right_form):
            form.setVerticalSpacing(7)
            form.setHorizontalSpacing(18)
        self.plan_name_edit = LineEdit()
        self.action_edit = LineEdit()
        self.difficulty_edit = LineEdit()
        self.sets_edit = LineEdit()
        self.reps_edit = LineEdit()
        self.duration_edit = LineEdit()
        self.rest_edit = LineEdit()
        self.desc_edit = TextEdit()
        self.desc_edit.setFixedHeight(72)

        self.plan_name_edit.setText("New Lower-Limb Plan")
        self.action_edit.setText(DEFAULT_ACTION_NAME)
        self.difficulty_edit.setText("Low")
        self.sets_edit.setText("3")
        self.reps_edit.setText("10")
        self.duration_edit.setText("15")
        self.rest_edit.setText("30")

        left_form.addRow(FormLabel("Plan name:"), self.plan_name_edit)
        left_form.addRow(FormLabel("Target action:"), self.action_edit)
        left_form.addRow(FormLabel("Difficulty:"), self.difficulty_edit)
        left_form.addRow(FormLabel("Description:"), self.desc_edit)
        right_form.addRow(FormLabel("Sets:"), self.sets_edit)
        right_form.addRow(FormLabel("Reps:"), self.reps_edit)
        right_form.addRow(FormLabel("Minutes:"), self.duration_edit)
        right_form.addRow(FormLabel("Rest sec:"), self.rest_edit)
        form_grid.addLayout(left_form, 0, 0)
        form_grid.addLayout(right_form, 0, 2)
        form_grid.setColumnStretch(0, 1)
        form_grid.setColumnMinimumWidth(1, 44)
        form_grid.setColumnStretch(1, 0)
        form_grid.setColumnStretch(2, 1)
        form_card_layout.addLayout(form_grid)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        self.create_btn = PrimaryPushButton("Create Plan")
        self.activate_btn = PrimaryPushButton("Set as Active")
        self.suggest_btn = PrimaryPushButton("Generate Adaptive Suggestion")
        self.apply_suggest_btn = PrimaryPushButton("Apply Suggested Plan")
        self.apply_suggest_btn.setEnabled(False)
        self.create_btn.clicked.connect(self.create_plan)
        self.activate_btn.clicked.connect(self.activate_plan)
        self.suggest_btn.clicked.connect(self.generate_suggestion)
        self.apply_suggest_btn.clicked.connect(self.apply_suggestion)
        button_layout.addWidget(self.create_btn)
        button_layout.addWidget(self.activate_btn)
        button_layout.addWidget(self.suggest_btn)
        button_layout.addWidget(self.apply_suggest_btn)
        button_layout.addStretch(1)
        form_card_layout.addLayout(button_layout)

        self.suggestion_text = TextEdit()
        self.suggestion_text.setReadOnly(True)
        self.suggestion_text.setFixedHeight(92)
        self.current_suggestion = None
        form_card_layout.addWidget(self.suggestion_text)
        if not self.can_manage:
            form_card.setVisible(False)
        self.main_layout.addWidget(form_card)

        table_title = "Assigned Training Plans" if not self.can_manage else "Plans Table"
        table_card, table_card_layout = self.create_section_card(table_title)
        self.table = TableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["ID", "Plan Name", "Action", "Difficulty", "Sets", "Reps", "Minutes", "Active"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setMinimumSectionSize(72)
        table_card_layout.addWidget(self.table)
        self.main_layout.addWidget(table_card, 1)

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

    def create_plan(self) -> None:
        if not self.can_manage:
            InfoBar.warning("Read Only", "Training plans are assigned by the care team.", position=InfoBarPosition.TOP, parent=self)
            return
        try:
            data = {
                "plan_name": self.plan_name_edit.text().strip() or "New Lower-Limb Plan",
                "target_action": self.action_edit.text().strip() or DEFAULT_ACTION_NAME,
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
        if not self.can_manage:
            InfoBar.warning("Read Only", "Please train from the assigned plan list.", position=InfoBarPosition.TOP, parent=self)
            return
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

    def generate_suggestion(self) -> None:
        if not self.can_manage:
            InfoBar.warning("Read Only", "Adaptive plan decisions are handled by the care team.", position=InfoBarPosition.TOP, parent=self)
            return
        suggestion = self.db.build_adaptive_plan_suggestion(self.user["id"])
        self.current_suggestion = suggestion
        self.apply_suggest_btn.setEnabled(bool(suggestion.get("new_plan")))
        lines = [
            "Adaptive plan suggestion:",
            f"- Decision: {suggestion.get('decision', '-')}",
            f"- Basis: {suggestion.get('basis', '-')}",
            "",
            "Before/After differences:",
        ]
        diff = suggestion.get("diff", [])
        if diff:
            for d in diff:
                lines.append(f"- {d}")
        else:
            lines.append("- No structural change is suggested.")
        self.suggestion_text.setPlainText("\n".join(lines))

    def apply_suggestion(self) -> None:
        if not self.can_manage:
            InfoBar.warning("Read Only", "Adaptive plan decisions are handled by the care team.", position=InfoBarPosition.TOP, parent=self)
            return
        if not self.current_suggestion:
            InfoBar.warning("No Suggestion", "Please generate an adaptive suggestion first.", position=InfoBarPosition.TOP, parent=self)
            return
        new_plan_id = self.db.apply_adaptive_plan_suggestion(self.user["id"], self.current_suggestion)
        if not new_plan_id:
            InfoBar.warning("Apply Failed", "No valid suggested plan to apply.", position=InfoBarPosition.TOP, parent=self)
            return
        self.refresh_data()
        if self.refresh_callback:
            self.refresh_callback()
        InfoBar.success("Applied", f"Adaptive plan has been applied as plan #{new_plan_id}.", position=InfoBarPosition.TOP, parent=self)
