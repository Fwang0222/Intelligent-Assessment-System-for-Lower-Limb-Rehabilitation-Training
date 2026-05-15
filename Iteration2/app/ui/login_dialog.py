"""Login dialog for the V5 local-AI + cloud-data demo accounts."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFormLayout, QHBoxLayout, QMessageBox, QVBoxLayout

from app.ui.fluent_compat import BodyLabel, LineEdit, PrimaryPushButton, PushButton, SubtitleLabel


class RegisterDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Register User")
        self.resize(460, 420)
        self.setup_ui()

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(SubtitleLabel("Create a New Patient Account"))
        form = QFormLayout()
        self.username_edit = LineEdit()
        self.password_edit = LineEdit()
        self.password_edit.setText("123456")
        self.full_name_edit = LineEdit()
        self.gender_edit = LineEdit()
        self.age_edit = LineEdit()
        self.height_edit = LineEdit()
        self.weight_edit = LineEdit()
        self.injury_edit = LineEdit()
        self.side_edit = LineEdit()
        self.stage_edit = LineEdit()
        self.goal_edit = LineEdit()
        self.phone_edit = LineEdit()

        form.addRow("Username:", self.username_edit)
        form.addRow("Password:", self.password_edit)
        form.addRow("Full name:", self.full_name_edit)
        form.addRow("Gender:", self.gender_edit)
        form.addRow("Age:", self.age_edit)
        form.addRow("Height (cm):", self.height_edit)
        form.addRow("Weight (kg):", self.weight_edit)
        form.addRow("Injured part:", self.injury_edit)
        form.addRow("Affected side:", self.side_edit)
        form.addRow("Rehab stage:", self.stage_edit)
        form.addRow("Rehab goal:", self.goal_edit)
        form.addRow("Phone:", self.phone_edit)
        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        create_btn = PrimaryPushButton("Create")
        cancel_btn = PushButton("Cancel")
        create_btn.clicked.connect(self.create_user)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(create_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def create_user(self) -> None:
        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip() or "123456"
        full_name = self.full_name_edit.text().strip() or username
        if not username:
            QMessageBox.warning(self, "Input Error", "Username cannot be empty.")
            return
        try:
            age = int(self.age_edit.text().strip()) if self.age_edit.text().strip() else None
            height_cm = float(self.height_edit.text().strip()) if self.height_edit.text().strip() else None
            weight_kg = float(self.weight_edit.text().strip()) if self.weight_edit.text().strip() else None
        except ValueError:
            QMessageBox.warning(self, "Input Error", "Age, height and weight must be numeric.")
            return

        user_id = self.db.register_user({
            "username": username,
            "password": password,
            "full_name": full_name,
            "gender": self.gender_edit.text().strip(),
            "age": age,
            "height_cm": height_cm,
            "weight_kg": weight_kg,
            "injured_part": self.injury_edit.text().strip(),
            "affected_side": self.side_edit.text().strip(),
            "rehab_stage": self.stage_edit.text().strip(),
            "rehab_goal": self.goal_edit.text().strip(),
            "phone": self.phone_edit.text().strip(),
        })
        if user_id is None:
            QMessageBox.warning(self, "Register Failed", "Username already exists or invalid input.")
            return
        QMessageBox.information(self, "Success", f"Account created successfully. User ID: {user_id}")
        self.accept()


class LoginDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.current_user = None
        self.setWindowTitle("Login")
        self.resize(420, 260)
        self.setup_ui()

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        title = SubtitleLabel("Lower-Limb Rehabilitation Intelligent Assessment System")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        layout.addWidget(BodyLabel("Patient demo: admin / 123456"))
        layout.addWidget(BodyLabel("Doctor demo: dr_remote / 123456"))
        layout.addWidget(BodyLabel(f"Data backend: {self.db.storage_label()} | AI pipeline: local workstation"))

        form = QFormLayout()
        self.username_edit = LineEdit()
        self.username_edit.setText("admin")
        self.password_edit = LineEdit()
        self.password_edit.setText("123456")
        self.password_edit.setEchoMode(LineEdit.Password)
        form.addRow("Username:", self.username_edit)
        form.addRow("Password:", self.password_edit)
        layout.addLayout(form)

        button_layout = QHBoxLayout()
        self.login_btn = PrimaryPushButton("Login")
        self.register_btn = PushButton("Register")
        self.cancel_btn = PushButton("Cancel")
        self.login_btn.clicked.connect(self.handle_login)
        self.register_btn.clicked.connect(self.open_register_dialog)
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.login_btn)
        button_layout.addWidget(self.register_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)

    def handle_login(self) -> None:
        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()
        user = self.db.login(username, password)
        if user:
            self.current_user = user
            self.accept()
        else:
            self.password_edit.clear()
            QMessageBox.warning(self, "Login Failed", "Incorrect username or password. Please try again.")

    def open_register_dialog(self) -> None:
        dialog = RegisterDialog(self.db, self)
        if dialog.exec() == QDialog.Accepted:
            QMessageBox.information(self, "Register", "You can now log in with the new account.")
