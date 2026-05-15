"""Base page class shared by all page widgets."""

from PySide6.QtWidgets import QVBoxLayout, QWidget

from app.ui.fluent_compat import BodyLabel, CardWidget


class BasePage(QWidget):
    """Common page container with consistent margins and spacing."""

    def __init__(self, db, user, parent=None):
        super().__init__(parent)
        self.db = db
        self.user = user
        if not self.objectName():
            self.setObjectName(self.__class__.__name__)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(14, 10, 14, 10)
        self.main_layout.setSpacing(8)

    def create_section_card(self, title: str = "", note: str = ""):
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        if title:
            title_label = BodyLabel(title)
            title_label.setStyleSheet("font-weight: 700; color: #0F172A; background: transparent; border: none;")
            layout.addWidget(title_label)
        if note:
            note_label = BodyLabel(note)
            note_label.setStyleSheet("color: #475569; background: transparent; border: none;")
            layout.addWidget(note_label)
        return card, layout

    def refresh_data(self):
        """Refresh visible page data after a write operation."""
        pass
