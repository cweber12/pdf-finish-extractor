"""Auto-dismissing toast notification overlaid on the main window."""

from __future__ import annotations

from PyQt6.QtCore import QPropertyAnimation, QRect, Qt, QTimer
from PyQt6.QtWidgets import QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QWidget

from src.ui import theme


class Toast(QWidget):
    """Small notification that slides in from the bottom-right and disappears."""

    def __init__(self, message: str, success: bool = True, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        accent = theme.SUCCESS if success else theme.ERROR
        icon = "✓" if success else "!"
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {theme.BG_ELEVATED};
                border: 1px solid {theme.BORDER_LIGHT};
                border-left: 4px solid {accent};
                border-radius: 10px;
            }}
            QLabel {{
                background-color: transparent;
                border: none;
            }}
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(22)
        shadow.setOffset(0, 8)
        shadow.setColor(Qt.GlobalColor.black)
        self.setGraphicsEffect(shadow)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 16, 10)
        layout.setSpacing(10)

        indicator = QLabel(icon)
        indicator.setStyleSheet(f"color: {accent}; font-size: 16px; font-weight: 800;")
        layout.addWidget(indicator)

        msg_label = QLabel(message)
        msg_label.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; font-size: {theme.FONT_MD}px; font-weight: 600;")
        layout.addWidget(msg_label)

        self.adjustSize()

    # ------------------------------------------------------------------
    # Class-level factory
    # ------------------------------------------------------------------

    @classmethod
    def show_in(cls, window: QWidget, message: str, success: bool = True, duration: int = 3000) -> None:
        """Create, position, animate, and auto-dismiss a toast on *window*."""
        toast = cls(message, success, parent=window)
        toast.adjustSize()

        margin = 22
        w = toast.width()
        h = toast.height()
        pw = window.width()
        ph = window.height()

        end_rect = QRect(pw - w - margin, ph - h - margin, w, h)
        start_rect = QRect(pw - w - margin, ph + 12, w, h)

        toast.setGeometry(start_rect)
        toast.show()
        toast.raise_()

        anim = QPropertyAnimation(toast, b"geometry", toast)
        anim.setDuration(220)
        anim.setStartValue(start_rect)
        anim.setEndValue(end_rect)
        anim.start()
        toast._anim = anim

        QTimer.singleShot(duration, toast.deleteLater)
