"""Auto-dismissing toast notification overlaid on the main window."""

from __future__ import annotations

from PyQt6.QtCore import QPropertyAnimation, QRect, Qt, QTimer
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from src.ui import theme


class Toast(QWidget):
    """Small notification that slides in from the bottom-right and disappears.

    Usage::

        Toast.show_in(self.window(), "12 swatches uploaded", success=True)
    """

    def __init__(self, message: str, success: bool = True, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        accent = theme.SUCCESS if success else theme.ERROR
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {theme.BG_ELEVATED};
                border: 1px solid {accent};
                border-radius: 8px;
            }}
            QLabel {{
                background-color: transparent;
                border: none;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 9, 16, 9)
        layout.setSpacing(8)

        indicator = QLabel("✓" if success else "✗")
        indicator.setStyleSheet(f"color: {accent}; font-size: 15px; font-weight: 700;")
        layout.addWidget(indicator)

        msg_label = QLabel(message)
        msg_label.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; font-size: {theme.FONT_MD}px;")
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

        margin = 20
        w = toast.width()
        h = toast.height()
        pw = window.width()
        ph = window.height()

        end_rect = QRect(pw - w - margin, ph - h - margin, w, h)
        start_rect = QRect(pw - w - margin, ph + 10, w, h)

        toast.setGeometry(start_rect)
        toast.show()
        toast.raise_()

        anim = QPropertyAnimation(toast, b"geometry", toast)
        anim.setDuration(220)
        anim.setStartValue(start_rect)
        anim.setEndValue(end_rect)
        anim.start()
        toast._anim = anim  # keep reference alive

        QTimer.singleShot(duration, toast.deleteLater)
