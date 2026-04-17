"""Page for editing the patient's rehab profile."""

from PySide6.QtWidgets import QFormLayout

from app.ui.base import BasePage
from app.ui.fluent_compat import BodyLabel, InfoBar, InfoBarPosition, LineEdit, PageTitleLabel, PrimaryPushButton, TextEdit


class ProfilePage(BasePage):
    def __init__(self, db, user, parent=None):
        super().__init__(db, user, parent)
        self.setup_ui()
        self.refresh_data()

    def setup_ui(self) -> None:
        self.main_layout.addWidget(PageTitleLabel("Rehab Profile"))
        card, card_layout = self.create_section_card(
            "Patient Profile Editor",
            "Maintain basic patient information and rehabilitation profile details.",
        )
        form = QFormLayout()
        form.setVerticalSpacing(6)

        self.full_name_edit = LineEdit()
        self.gender_edit = LineEdit()
        self.age_edit = LineEdit()
        self.height_edit = LineEdit()
        self.weight_edit = LineEdit()
        self.injured_part_edit = LineEdit()
        self.affected_side_user_edit = LineEdit()
        self.rehab_stage_user_edit = LineEdit()
        self.rehab_goal_user_edit = TextEdit()
        self.phone_edit = LineEdit()

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
        self.rehab_goal_user_edit.setFixedHeight(60)

        form.addRow("Full name:", self.full_name_edit)
        form.addRow("Gender:", self.gender_edit)
        form.addRow("Age:", self.age_edit)
        form.addRow("Height (cm):", self.height_edit)
        form.addRow("Weight (kg):", self.weight_edit)
        form.addRow("Injured part:", self.injured_part_edit)
        form.addRow("Affected side (user):", self.affected_side_user_edit)
        form.addRow("Rehab stage (user):", self.rehab_stage_user_edit)
        form.addRow("Rehab goal:", self.rehab_goal_user_edit)
        form.addRow("Phone:", self.phone_edit)

        form.addRow("Diagnosis:", self.diagnosis_edit)
        form.addRow("Affected side:", self.side_edit)
        form.addRow("Rehab stage:", self.stage_edit)
        form.addRow("Pain score:", self.pain_edit)
        form.addRow("ROM goal:", self.rom_goal_edit)
        form.addRow("Contraindications:", self.contra_edit)
        form.addRow("Doctor name:", self.doctor_edit)
        form.addRow("Additional notes:", self.notes_edit)
        card_layout.addLayout(form)

        self.save_btn = PrimaryPushButton("Save Profile")
        self.save_btn.clicked.connect(self.save_profile)
        card_layout.addWidget(self.save_btn)
        self.main_layout.addWidget(card, 1)

    def refresh_data(self) -> None:
        self.full_name_edit.setText(self.user.get("full_name", ""))
        self.gender_edit.setText(self.user.get("gender", ""))
        self.age_edit.setText("" if self.user.get("age") is None else str(self.user.get("age")))
        self.height_edit.setText("" if self.user.get("height_cm") is None else str(self.user.get("height_cm")))
        self.weight_edit.setText("" if self.user.get("weight_kg") is None else str(self.user.get("weight_kg")))
        self.injured_part_edit.setText(self.user.get("injured_part", "") or "")
        self.affected_side_user_edit.setText(self.user.get("affected_side", "") or "")
        self.rehab_stage_user_edit.setText(self.user.get("rehab_stage", "") or "")
        self.rehab_goal_user_edit.setPlainText(self.user.get("rehab_goal", "") or "")
        self.phone_edit.setText(self.user.get("phone", "") or "")

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
            age = int(self.age_edit.text().strip()) if self.age_edit.text().strip() else None
            height_cm = float(self.height_edit.text().strip()) if self.height_edit.text().strip() else None
            weight_kg = float(self.weight_edit.text().strip()) if self.weight_edit.text().strip() else None
        except ValueError:
            InfoBar.warning(
                "Input Error",
                "Pain must be integer, age integer, height/weight numeric.",
                position=InfoBarPosition.TOP,
                parent=self,
            )
            return

        basic_data = {
            "full_name": self.full_name_edit.text().strip(),
            "gender": self.gender_edit.text().strip(),
            "age": age,
            "height_cm": height_cm,
            "weight_kg": weight_kg,
            "injured_part": self.injured_part_edit.text().strip(),
            "affected_side": self.affected_side_user_edit.text().strip(),
            "rehab_stage": self.rehab_stage_user_edit.text().strip(),
            "rehab_goal": self.rehab_goal_user_edit.toPlainText().strip(),
            "phone": self.phone_edit.text().strip(),
        }
        self.db.update_user_basic_info(self.user["id"], basic_data)
        self.user.update({k: v for k, v in basic_data.items()})

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
        InfoBar.success("Saved", "Basic information and rehab profile have been updated.", position=InfoBarPosition.TOP, parent=self)
