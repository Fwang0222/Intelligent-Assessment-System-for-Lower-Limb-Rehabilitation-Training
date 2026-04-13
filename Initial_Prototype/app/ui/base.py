"""Base page class shared by all page widgets."""

from PySide6.QtWidgets import QVBoxLayout, QWidget


class BasePage(QWidget):
    """Common page container with consistent margins and spacing."""

    def __init__(self, db, user, parent=None):
        super().__init__(parent)
        self.db = db
        self.user = user
        if not self.objectName():
            self.setObjectName(self.__class__.__name__)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(16)

    def refresh_data(self):
        """Refresh visible page data after a write operation."""
        pass
