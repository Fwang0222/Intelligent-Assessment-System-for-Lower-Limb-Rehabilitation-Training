"""Stable Fluent-style UI compatibility layer built on PySide6 widgets."""

from __future__ import annotations

import os
from typing import Any, Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QStyledItemDelegate,
    QStyle,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

try:
    from qfluentwidgets import BodyLabel as QFBodyLabel  # type: ignore
    from qfluentwidgets import FluentIcon as FIcon  # type: ignore
    from qfluentwidgets import InfoBar as QFInfoBar  # type: ignore
    from qfluentwidgets import InfoBarPosition as QFInfoBarPosition  # type: ignore
    from qfluentwidgets import SubtitleLabel as QFSubtitleLabel  # type: ignore
except Exception:
    FIcon = None
    QFInfoBar = None
    QFInfoBarPosition = None
    QFBodyLabel = None
    QFSubtitleLabel = None


class NavigationItemPosition:
    TOP = 0
    BOTTOM = 1


class InfoBarPosition:
    TOP = 0
    BOTTOM = 1


_SubtitleBase = QFSubtitleLabel if QFSubtitleLabel is not None else QLabel
_BodyBase = QFBodyLabel if QFBodyLabel is not None else QLabel


GLOBAL_APP_STYLE = """
QWidget {
    font-family: "Segoe UI", "Microsoft YaHei", Arial;
    font-size: 10pt;
    color: #1E293B;
}
QLabel {
    background: transparent;
    border: none;
}
QDialog {
    background: #F3F7FC;
}
QToolTip {
    background: #0F172A;
    color: #FFFFFF;
    border: none;
    border-radius: 4px;
    padding: 5px 7px;
}
"""


def _apply_shadow(widget: QWidget, blur: int = 18, alpha: int = 28) -> None:
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur)
    shadow.setOffset(0, 6)
    shadow.setColor(QColor(15, 23, 42, alpha))
    widget.setGraphicsEffect(shadow)


class SubtitleLabel(_SubtitleBase):
    """Section subtitle in a Fluent-like typography scale."""

    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        if QFSubtitleLabel is None:
            super().__init__(text, parent)
        else:
            super().__init__(parent)
            self.setText(text)
        if QFSubtitleLabel is None:
            font = QFont("Segoe UI", 12)
            font.setBold(True)
            self.setFont(font)
        self.setWordWrap(True)
        self.setAutoFillBackground(False)
        self.setStyleSheet("background: transparent; border: none; color: #0F172A;")


class PageTitleLabel(SubtitleLabel):
    """Compact page title used as the first visual anchor on each page."""

    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        font = self.font()
        font.setPointSize(18)
        font.setBold(True)
        self.setFont(font)
        self.setWordWrap(False)
        self.setFixedHeight(30)
        self.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.setStyleSheet("background: transparent; border: none; color: #0F172A;")


class BodyLabel(_BodyBase):
    """Normal body text label."""

    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        if QFBodyLabel is None:
            super().__init__(text, parent)
        else:
            super().__init__(parent)
            self.setText(text)
        if QFBodyLabel is None:
            font = QFont("Segoe UI", 10)
            self.setFont(font)
        self.setWordWrap(True)
        self.setAutoFillBackground(False)
        self.setStyleSheet("background: transparent; border: none; color: #334155;")


class CaptionLabel(BodyLabel):
    """Muted helper text."""

    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        font = self.font()
        font.setPointSize(9)
        self.setFont(font)
        self.setStyleSheet("background: transparent; border: none; color: #64748B;")


class FormLabel(QLabel):
    """Form field label that blends into white card surfaces."""

    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.setAutoFillBackground(False)
        self.setMinimumWidth(92)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        font = QFont("Segoe UI", 10)
        self.setFont(font)
        self.setStyleSheet(
            """
            QLabel {
                background-color: transparent;
                border: none;
                color: #334155;
                padding: 0;
                margin: 0;
            }
            """
        )


class ValueLabel(BodyLabel):
    """Large numeric/value label for KPI cards."""

    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        font = self.font()
        font.setPointSize(17)
        font.setBold(True)
        self.setFont(font)
        self.setStyleSheet("background: transparent; border: none; color: #0F172A;")


class PillLabel(QLabel):
    """Small tone-aware status pill."""

    _tone_map = {
        "neutral": ("#EEF2FF", "#3730A3"),
        "blue": ("#E0F2FE", "#075985"),
        "green": ("#DCFCE7", "#166534"),
        "orange": ("#FFEDD5", "#9A3412"),
        "red": ("#FEE2E2", "#991B1B"),
        "slate": ("#E2E8F0", "#334155"),
    }

    def __init__(self, text: str = "", tone: str = "neutral", parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        self.setObjectName("pillLabel")
        self.setAlignment(Qt.AlignCenter)
        font = QFont("Segoe UI", 9)
        font.setBold(True)
        self.setFont(font)
        self.setMinimumHeight(24)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.setContentsMargins(10, 0, 10, 0)
        self.setTone(tone)

    def setTone(self, tone: str) -> None:
        bg, fg = self._tone_map.get(tone, self._tone_map["neutral"])
        self.setStyleSheet(
            f"""
            QLabel {{
                background: {bg};
                color: {fg};
                border: 1px solid rgba(15, 23, 42, 0.05);
                border-radius: 12px;
                padding: 2px 10px;
            }}
            """
        )


class CardWidget(QFrame):
    """Card-like container with Fluent-style layered surface."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("cardWidget")
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(
            """
            QFrame#cardWidget {
                background: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
            }
            QFrame#cardWidget:hover {
                border: 1px solid #CBD5E1;
            }
            QFrame#cardWidget QLabel {
                background-color: transparent;
                border: none;
            }
            """
        )
        _apply_shadow(self, blur=16, alpha=24)


class LineEdit(QLineEdit):
    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        self.setMinimumHeight(34)
        self.setStyleSheet(
            """
            QLineEdit {
                border: 1px solid #D7DFEA;
                border-radius: 8px;
                padding: 6px 10px;
                background: #FCFDFF;
                selection-background-color: #BFDBFE;
            }
            QLineEdit:focus {
                border: 1px solid #2563EB;
                background: #FFFFFF;
            }
            """
        )


class ComboBox(QComboBox):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumHeight(34)
        self.setStyleSheet(
            """
            QComboBox {
                border: 1px solid #D7DFEA;
                border-radius: 8px;
                padding: 6px 10px;
                background: #FCFDFF;
            }
            QComboBox:focus {
                border: 1px solid #2563EB;
                background: #FFFFFF;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            """
        )


class PushButton(QPushButton):
    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        self.setMinimumHeight(34)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            """
            QPushButton {
                background: #F8FAFC;
                color: #1E293B;
                border: 1px solid #D7DFEA;
                border-radius: 8px;
                padding: 7px 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #F1F5F9;
                border: 1px solid #C7D2E0;
            }
            QPushButton:pressed {
                background: #E2E8F0;
            }
            QPushButton:disabled {
                background: #F8FAFC;
                color: #94A3B8;
                border: 1px solid #E2E8F0;
            }
            """
        )


class PrimaryPushButton(QPushButton):
    """Primary action button with Fluent-like accent styling."""

    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        self.setMinimumHeight(34)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            """
            QPushButton {
                background-color: #2563EB;
                color: #FFFFFF;
                border: 1px solid #2563EB;
                border-radius: 8px;
                padding: 7px 14px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #1D4ED8;
                border: 1px solid #1D4ED8;
            }
            QPushButton:pressed {
                background-color: #1E40AF;
                border: 1px solid #1E40AF;
            }
            QPushButton:disabled {
                background-color: #93C5FD;
                border: 1px solid #93C5FD;
                color: #EFF6FF;
            }
            """
        )


class TextEdit(QPlainTextEdit):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setStyleSheet(
            """
            QPlainTextEdit {
                border: 1px solid #D7DFEA;
                border-radius: 8px;
                background: #FCFDFF;
                padding: 8px;
                selection-background-color: #BFDBFE;
            }
            QPlainTextEdit:focus {
                border: 1px solid #2563EB;
                background: #FFFFFF;
            }
            """
        )


class ProgressBar(QProgressBar):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setTextVisible(True)
        self.setMinimumHeight(22)
        self.setStyleSheet(
            """
            QProgressBar {
                border: 1px solid #D7DFEA;
                border-radius: 8px;
                text-align: center;
                background: #EFF6FF;
                color: #0F172A;
                font-weight: 600;
            }
            QProgressBar::chunk {
                border-radius: 7px;
                background-color: #2563EB;
            }
            """
        )


class TableWidget(QTableWidget):
    """QTableWidget wrapper that accepts several constructor styles."""

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
        self.setItemDelegate(_RowSelectionDelegate(self))
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setWordWrap(False)
        self.setShowGrid(False)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(34)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.horizontalHeader().setMinimumSectionSize(64)
        self.setStyleSheet(
            """
            QTableWidget {
                gridline-color: #E5EAF2;
                alternate-background-color: #F8FAFC;
                selection-background-color: #DBEAFE;
                border: 1px solid #D7DFEA;
                border-radius: 8px;
                background: #FFFFFF;
                outline: 0;
            }
            QHeaderView::section {
                background: #F8FAFC;
                color: #334155;
                border: none;
                border-bottom: 1px solid #E2E8F0;
                padding: 7px;
                font-weight: 700;
            }
            QTableWidget::item {
                padding: 5px 7px;
                border: none;
            }
            QTableWidget::item:selected {
                background: #DBEAFE;
                color: #0F172A;
                border: none;
            }
            """
        )


class _RowSelectionDelegate(QStyledItemDelegate):
    """Draw one left accent for selected rows instead of per-cell borders."""

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        if index.column() == 0 and option.state & QStyle.State_Selected:
            painter.save()
            painter.fillRect(option.rect.left(), option.rect.top() + 4, 3, option.rect.height() - 8, QColor("#2563EB"))
            painter.restore()


class ListWidget(QListWidget):
    """Styled list widget used for worklists and navigation-like side panels."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.NoFocus)
        self.setSpacing(4)
        self.setStyleSheet(
            """
            QListWidget {
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                background: #FFFFFF;
                padding: 6px;
                outline: 0;
            }
            QListWidget::item {
                padding: 10px 12px;
                border-radius: 8px;
                margin: 1px 0;
                color: #0F172A;
            }
            QListWidget::item:hover {
                background: #F8FAFC;
            }
            QListWidget::item:selected {
                background: #DBEAFE;
                color: #0F172A;
                border: 1px solid #BFDBFE;
                font-weight: 700;
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
    """Fallback InfoBar implementation when qfluentwidgets is unavailable."""

    @staticmethod
    def success(title: str, content: str, orient=None, isClosable: bool = True,
                position=None, duration: int = 2000, parent: Optional[QWidget] = None):
        if QFInfoBar is not None:
            try:
                qf_pos = QFInfoBarPosition.TOP if position == InfoBarPosition.TOP else QFInfoBarPosition.BOTTOM
                QFInfoBar.success(title=title, content=content, orient=Qt.Horizontal, isClosable=isClosable, position=qf_pos, duration=duration, parent=parent)
                return
            except Exception:
                pass
        QMessageBox.information(parent, title, content)

    @staticmethod
    def warning(title: str, content: str, orient=None, isClosable: bool = True,
                position=None, duration: int = 2000, parent: Optional[QWidget] = None):
        if QFInfoBar is not None:
            try:
                qf_pos = QFInfoBarPosition.TOP if position == InfoBarPosition.TOP else QFInfoBarPosition.BOTTOM
                QFInfoBar.warning(title=title, content=content, orient=Qt.Horizontal, isClosable=isClosable, position=qf_pos, duration=duration, parent=parent)
                return
            except Exception:
                pass
        QMessageBox.warning(parent, title, content)

    @staticmethod
    def error(title: str, content: str, orient=None, isClosable: bool = True,
              position=None, duration: int = 2000, parent: Optional[QWidget] = None):
        if QFInfoBar is not None:
            try:
                qf_pos = QFInfoBarPosition.TOP if position == InfoBarPosition.TOP else QFInfoBarPosition.BOTTOM
                QFInfoBar.error(title=title, content=content, orient=Qt.Horizontal, isClosable=isClosable, position=qf_pos, duration=duration, parent=parent)
                return
            except Exception:
                pass
        QMessageBox.critical(parent, title, content)


class FluentWindow(QMainWindow):
    """Stable main window with a Fluent-inspired navigation rail and page stack."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.resize(1400, 900)

        app = QApplication.instance()
        user_role = "Patient"
        user_name = "Rehab User"
        if app is not None:
            user_role = str(app.property("rehab_role") or user_role).title()
            user_name = str(app.property("rehab_user_name") or user_name)

        self.nav_brand = QLabel("Rehab Intelligence")
        self.nav_brand.setObjectName("navBrand")
        self.nav_tagline = QLabel("Lower-Limb Recovery")
        self.nav_tagline.setObjectName("navTagline")
        self.nav_role = QLabel(user_role)
        self.nav_role.setObjectName("navRole")
        self.nav_user = QLabel(user_name)
        self.nav_user.setObjectName("navUser")

        self.nav_list = QListWidget()
        self.nav_list.setMaximumWidth(264)
        self.nav_list.setMinimumWidth(236)
        self.nav_list.setFocusPolicy(Qt.NoFocus)
        self.nav_list.setIconSize(QSize(22, 22))
        self.nav_list.setStyleSheet(
            """
            QListWidget {
                border: none;
                background: transparent;
                padding: 6px 12px;
                outline: 0;
            }
            QListWidget::item {
                min-height: 42px;
                padding: 13px 16px;
                border-radius: 10px;
                margin: 3px 0;
                color: #D7E3F3;
                font-size: 14px;
            }
            QListWidget::item:hover {
                background: rgba(148, 163, 184, 0.14);
                color: #FFFFFF;
            }
            QListWidget::item:selected {
                background: #EAF2FF;
                color: #0F172A;
                border: 1px solid rgba(255, 255, 255, 0.35);
                font-weight: 700;
            }
            QListWidget::item:focus {
                outline: none;
            }
            """
        )

        nav_shell = QFrame()
        nav_shell.setObjectName("navShell")
        nav_shell.setStyleSheet(
            """
            QFrame#navShell {
                background: #0F172A;
                border-right: 1px solid #1E293B;
            }
            QLabel#navBrand {
                color: #FFFFFF;
                font-size: 18px;
                font-weight: 800;
                background: transparent;
                border: none;
                letter-spacing: 0;
            }
            QLabel#navTagline {
                color: #93A4B8;
                font-size: 11px;
                font-weight: 600;
                background: transparent;
                border: none;
                letter-spacing: 0;
            }
            QLabel#navRole {
                color: #BFDBFE;
                background: rgba(37, 99, 235, 0.20);
                border: 1px solid rgba(147, 197, 253, 0.22);
                border-radius: 11px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 800;
            }
            QLabel#navUser {
                color: #E2E8F0;
                background: rgba(15, 23, 42, 0.72);
                border: 1px solid rgba(148, 163, 184, 0.20);
                border-radius: 10px;
                padding: 10px 12px;
                font-size: 12px;
                font-weight: 700;
            }
            """
        )
        nav_layout = QVBoxLayout(nav_shell)
        nav_layout.setContentsMargins(14, 18, 14, 14)
        nav_layout.setSpacing(10)
        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(0, 0, 0, 0)
        brand_row.setSpacing(8)
        mark = QLabel()
        mark.setAlignment(Qt.AlignCenter)
        mark.setFixedSize(34, 34)
        brand_icon_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "assets",
            "nav_icons",
            "icon.png",
        )
        if os.path.exists(brand_icon_path):
            mark.setPixmap(
                QPixmap(brand_icon_path).scaled(
                    24,
                    24,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )
        mark.setStyleSheet(
            """
            QLabel {
                color: #0F172A;
                background: #EAF2FF;
                border-radius: 10px;
                font-size: 17px;
                font-weight: 900;
            }
            """
        )
        brand_text = QVBoxLayout()
        brand_text.setContentsMargins(0, 0, 0, 0)
        brand_text.setSpacing(0)
        brand_text.addWidget(self.nav_brand)
        brand_text.addWidget(self.nav_tagline)
        brand_row.addWidget(mark)
        brand_row.addLayout(brand_text, 1)
        nav_layout.addLayout(brand_row)
        nav_layout.addWidget(self.nav_role, 0, Qt.AlignLeft)
        nav_layout.addWidget(self.nav_list, 1)
        nav_layout.addWidget(self.nav_user)

        self.stack = QStackedWidget()
        self.stack.setObjectName("mainStack")
        self.stack.setStyleSheet("background: #F3F7FC;")

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(nav_shell)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(container)

        self._widgets = []
        self.nav_list.currentRowChanged.connect(self._on_current_row_changed)
        self.setStyleSheet("QMainWindow { background: #F3F7FC; }")

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


def get_icon(name: str = "home") -> QIcon:
    """Return a two-tone navigation icon for dark sidebar and light selection."""
    icon_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "nav_icons")
    file_map = {
        "home": "Home",
        "profile": "Heart",
        "realtime": "Camera",
        "result": "CheckBox",
        "plan": "Document",
        "history": "History",
        "analysis": "PieSingle",
        "doctor": "People",
    }
    base_name = file_map.get(name, "Home")
    white_path = os.path.join(icon_dir, f"{base_name}_white.svg")
    black_path = os.path.join(icon_dir, f"{base_name}_black.svg")
    if os.path.exists(white_path) and os.path.exists(black_path):
        icon = QIcon()
        size = QSize(22, 22)
        icon.addFile(white_path, size, QIcon.Normal, QIcon.Off)
        icon.addFile(white_path, size, QIcon.Active, QIcon.Off)
        icon.addFile(white_path, size, QIcon.Disabled, QIcon.Off)
        icon.addFile(black_path, size, QIcon.Selected, QIcon.Off)
        icon.addFile(black_path, size, QIcon.Selected, QIcon.On)
        return icon

    if FIcon is not None:
        try:
            icon_map = {
                "home": "HOME",
                "profile": "CONTACT",
                "realtime": "CAMERA",
                "result": "CHECKBOX",
                "plan": "DOCUMENT",
                "history": "HISTORY",
                "analysis": "PIE_SINGLE",
                "doctor": "PEOPLE",
            }
            key = icon_map.get(name, "HOME")
            fluent_icon = getattr(FIcon, key, None)
            if fluent_icon is not None:
                return fluent_icon.icon()
            return FIcon.HOME.icon()
        except Exception:
            return QIcon()
    return QIcon()
