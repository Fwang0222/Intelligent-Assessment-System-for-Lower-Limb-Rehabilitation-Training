import sys
from PySide6.QtWidgets import QApplication

from app.core.database import DatabaseManager
from app.ui.login_dialog import LoginDialog
from app.ui.main_window import RehabMainWindow
import seaborn as sns


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Lower-Limb Rehabilitation Intelligent Assessment System")

    db = DatabaseManager()
    db.initialize()
    db.seed_demo_data()

    login = LoginDialog(db)
    if login.exec() != LoginDialog.Accepted or login.current_user is None:
        sys.exit(0)

    window = RehabMainWindow(db, login.current_user)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
