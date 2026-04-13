"""Login dialog for the local demo account."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFormLayout, QHBoxLayout, QMessageBox, QVBoxLayout

from app.ui.fluent_compat import BodyLabel, LineEdit, PrimaryPushButton, PushButton, SubtitleLabel


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
        layout.addWidget(BodyLabel("Demo account: admin / 123456"))

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
        self.cancel_btn = PushButton("Cancel")
        self.login_btn.clicked.connect(self.handle_login)
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.login_btn)
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
