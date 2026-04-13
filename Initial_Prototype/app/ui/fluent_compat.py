"""Stable UI compatibility layer.

This project targets PySide6 and a qfluentwidgets-like visual style, but real course
projects often fail at runtime because the constructor signatures of some Fluent
widgets differ from the native Qt widgets. To keep the project stable and easy to
submit, this module provides lightweight wrappers built on native Qt widgets.
"""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QWidget,
)


class NavigationItemPosition:
    TOP = 0
    BOTTOM = 1


class InfoBarPosition:
    TOP = 0
    BOTTOM = 1


class SubtitleLabel(QLabel):
    """Simple subtitle label used across the application."""

    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        font = QFont()
        font.setPointSize(15)
        font.setBold(True)
        self.setFont(font)
        self.setWordWrap(True)


class BodyLabel(QLabel):
    """Normal body text label."""

    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        font = QFont()
        font.setPointSize(10)
        self.setFont(font)
        self.setWordWrap(True)


class CardWidget(QFrame):
    """Card-like container used on dashboard and analysis pages."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("cardWidget")
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            """
            QFrame#cardWidget {
                background: white;
                border: 1px solid #DCDCDC;
                border-radius: 12px;
            }
            """
        )


class LineEdit(QLineEdit):
    pass


class ComboBox(QComboBox):
    pass


class PushButton(QPushButton):
    pass


class PrimaryPushButton(QPushButton):
    """Primary action button with a stronger visual emphasis."""

    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        self.setStyleSheet(
            """
            QPushButton {
                background-color: #2563EB;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 14px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #1D4ED8; }
            QPushButton:disabled {
                background-color: #94A3B8;
                color: #F8FAFC;
            }
            """
        )


class TextEdit(QPlainTextEdit):
    pass


class ProgressBar(QProgressBar):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setTextVisible(True)


class TableWidget(QTableWidget):
    """QTableWidget wrapper that accepts several constructor styles.

    Supported forms:
    - TableWidget()
    - TableWidget(rows, columns)
    - TableWidget(parent)
    - TableWidget(parent, rows, columns)
    - TableWidget(rows, columns, parent)
    """

    def __init__(self, *args: Any, **kwargs: Any):
        parent = kwargs.pop("parent", None)
        rows = kwargs.pop("rowCount", kwargs.pop("rows", 0))
        columns = kwargs.pop("columnCount", kwargs.pop("columns", 0))

        def is_parent(obj: Any) -> bool:
            return obj is None or isinstance(obj, QWidget)

        if len(args) == 1:
            if is_parent(args[0]):
                parent = args[0]
            else:
                rows = args[0]
        elif len(args) == 2:
            if is_parent(args[0]):
                parent = args[0]
                rows = args[1]
            else:
                rows, columns = args
        elif len(args) >= 3:
            if is_parent(args[0]):
                parent, rows, columns = args[:3]
            else:
                rows, columns, parent = args[:3]

        super().__init__(int(rows), int(columns), parent)
        self.setAlternatingRowColors(True)
        self.setStyleSheet(
            """
            QTableWidget {
                gridline-color: #E5E7EB;
                alternate-background-color: #F8FAFC;
                selection-background-color: #DBEAFE;
                border: 1px solid #D1D5DB;
                border-radius: 8px;
            }
            QHeaderView::section {
                background: #F3F4F6;
                border: none;
                border-bottom: 1px solid #D1D5DB;
                padding: 6px;
                font-weight: 600;
            }
            """
        )


class MessageBox(QMessageBox):
    def __init__(self, title: str, content: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setText(content)
        self.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)


class InfoBar:
    """Minimal message-box based replacement for Fluent InfoBar APIs."""

    @staticmethod
    def success(title: str, content: str, orient=None, isClosable: bool = True,
                position=None, duration: int = 2000, parent: Optional[QWidget] = None):
        QMessageBox.information(parent, title, content)

    @staticmethod
    def warning(title: str, content: str, orient=None, isClosable: bool = True,
                position=None, duration: int = 2000, parent: Optional[QWidget] = None):
        QMessageBox.warning(parent, title, content)

    @staticmethod
    def error(title: str, content: str, orient=None, isClosable: bool = True,
              position=None, duration: int = 2000, parent: Optional[QWidget] = None):
        QMessageBox.critical(parent, title, content)


class FluentWindow(QMainWindow):
    """Stable main window with a left navigation list and stacked pages."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.resize(1360, 860)

        self.nav_list = QListWidget()
        self.nav_list.setMaximumWidth(240)
        self.nav_list.setMinimumWidth(200)
        self.nav_list.setStyleSheet(
            """
            QListWidget {
                border: none;
                background: #F8FAFC;
                padding: 8px;
            }
            QListWidget::item {
                padding: 10px 12px;
                border-radius: 8px;
                margin: 2px 0;
            }
            QListWidget::item:selected {
                background: #DBEAFE;
                color: #111827;
                font-weight: 600;
            }
            """
        )

        self.stack = QStackedWidget()
        self.stack.setObjectName("mainStack")

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.nav_list)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(container)

        self._widgets = []
        self.nav_list.currentRowChanged.connect(self._on_current_row_changed)

    def _on_current_row_changed(self, index: int) -> None:
        if index >= 0:
            self.stack.setCurrentIndex(index)

    def addSubInterface(self, widget: QWidget, icon: Optional[QIcon], text: str,
                        position: int = NavigationItemPosition.TOP):
        if not widget.objectName():
            safe_name = "page_" + "_".join(text.lower().split()) if text else f"page_{len(self._widgets)}"
            widget.setObjectName(safe_name)
        self.stack.addWidget(widget)
        item = QListWidgetItem(text)
        if isinstance(icon, QIcon) and not icon.isNull():
            item.setIcon(icon)
        self.nav_list.addItem(item)
        self._widgets.append(widget)
        if self.nav_list.currentRow() < 0:
            self.nav_list.setCurrentRow(0)
        return widget


def get_icon() -> QIcon:
    """Return an empty icon placeholder for the current demo."""
    return QIcon()
