"""Page for editing the patient's rehab profile."""

from PySide6.QtWidgets import QFormLayout

from app.ui.base import BasePage
from app.ui.fluent_compat import BodyLabel, InfoBar, InfoBarPosition, LineEdit, PrimaryPushButton, SubtitleLabel, TextEdit


class ProfilePage(BasePage):
    def __init__(self, db, user, parent=None):
        super().__init__(db, user, parent)
        self.setup_ui()
        self.refresh_data()

    def setup_ui(self) -> None:
        self.main_layout.addWidget(SubtitleLabel("Rehab Profile"))
        self.main_layout.addWidget(BodyLabel("Maintain diagnosis, stage, ROM goals, doctor notes, and safety constraints."))
        form = QFormLayout()

        self.diagnosis_edit = LineEdit()
        self.side_edit = LineEdit()
        self.stage_edit = LineEdit()
        self.pain_edit = LineEdit()
        self.rom_goal_edit = TextEdit()
        self.contra_edit = TextEdit()
        self.doctor_edit = LineEdit()
        self.notes_edit = TextEdit()

        self.rom_goal_edit.setFixedHeight(70)
        self.contra_edit.setFixedHeight(70)
        self.notes_edit.setFixedHeight(70)

        form.addRow("Diagnosis:", self.diagnosis_edit)
        form.addRow("Affected side:", self.side_edit)
        form.addRow("Rehab stage:", self.stage_edit)
        form.addRow("Pain score:", self.pain_edit)
        form.addRow("ROM goal:", self.rom_goal_edit)
        form.addRow("Contraindications:", self.contra_edit)
        form.addRow("Doctor name:", self.doctor_edit)
        form.addRow("Additional notes:", self.notes_edit)
        self.main_layout.addLayout(form)

        self.save_btn = PrimaryPushButton("Save Profile")
        self.save_btn.clicked.connect(self.save_profile)
        self.main_layout.addWidget(self.save_btn)
        self.main_layout.addStretch(1)

    def refresh_data(self) -> None:
        profile = self.db.get_user_profile(self.user["id"])
        if not profile:
            return
        self.diagnosis_edit.setText(profile.get("diagnosis", ""))
        self.side_edit.setText(profile.get("affected_side", ""))
        self.stage_edit.setText(profile.get("rehab_stage", ""))
        self.pain_edit.setText(str(profile.get("pain_level", 0)))
        self.rom_goal_edit.setPlainText(profile.get("rom_goal", ""))
        self.contra_edit.setPlainText(profile.get("contraindications", ""))
        self.doctor_edit.setText(profile.get("doctor_name", ""))
        self.notes_edit.setPlainText(profile.get("notes", ""))

    def save_profile(self) -> None:
        try:
            pain_level = int(self.pain_edit.text().strip() or 0)
        except ValueError:
            InfoBar.warning("Input Error", "Pain score must be an integer.", position=InfoBarPosition.TOP, parent=self)
            return

        data = {
            "diagnosis": self.diagnosis_edit.text().strip(),
            "affected_side": self.side_edit.text().strip(),
            "rehab_stage": self.stage_edit.text().strip(),
            "pain_level": pain_level,
            "rom_goal": self.rom_goal_edit.toPlainText().strip(),
            "contraindications": self.contra_edit.toPlainText().strip(),
            "doctor_name": self.doctor_edit.text().strip(),
            "notes": self.notes_edit.toPlainText().strip(),
        }
        self.db.save_user_profile(self.user["id"], data)
        InfoBar.success("Saved", "The rehab profile has been updated.", position=InfoBarPosition.TOP, parent=self)
