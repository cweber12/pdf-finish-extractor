from __future__ import annotations

from PyQt6.QtCore import QEasingCurve, QEvent, QPropertyAnimation, QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QMouseEvent
from PyQt6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QLabel, QToolButton, QWidget

from src.ui import theme


class GlowIconButton(QToolButton):
    """Icon-only action button with an animated outer glow."""

    _IDLE_BLUR = 0.0
    _HOVER_BLUR = 18.0
    _PRESS_BLUR = 28.0
    _CHECKED_BLUR = 14.0

    def __init__(
        self,
        icon_name: str,
        tooltip: str,
        glow_color: QColor | None = None,
        checkable: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setIcon(QIcon(theme.icon_path(icon_name)))
        self.setIconSize(QSize(18, 18))
        self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAutoRaise(True)
        self.setCheckable(checkable)
        self.setProperty("class", "iconAction")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        base = QColor(glow_color) if glow_color is not None else QColor(theme.ACCENT)
        base.setAlpha(220)
        self._glow_color = base

        self._glow = QGraphicsDropShadowEffect(self)
        self._glow.setColor(self._glow_color)
        self._glow.setBlurRadius(self._IDLE_BLUR)
        self._glow.setOffset(0, 0)
        self.setGraphicsEffect(self._glow)

        self._anim = QPropertyAnimation(self._glow, b"blurRadius", self)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._hovered = False
        self._pressed = False

        if checkable:
            self.toggled.connect(self._on_toggled)

    def _target_blur(self) -> float:
        if not self.isEnabled():
            return self._IDLE_BLUR
        if self._pressed:
            return self._PRESS_BLUR
        if self._hovered:
            return self._HOVER_BLUR
        if self.isChecked():
            return self._CHECKED_BLUR
        return self._IDLE_BLUR

    def _animate_to(self, target: float, duration: int = 180) -> None:
        self._anim.stop()
        self._anim.setDuration(duration)
        self._anim.setStartValue(self._glow.blurRadius())
        self._anim.setEndValue(target)
        self._anim.start()

    def _on_toggled(self, _checked: bool) -> None:
        self._animate_to(self._target_blur())

    def enterEvent(self, event) -> None:  # noqa: ANN001
        self._hovered = True
        self._animate_to(self._target_blur())
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: ANN001
        self._hovered = False
        self._animate_to(self._target_blur())
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            self._animate_to(self._target_blur(), duration=80)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = False
            self._animate_to(self._target_blur(), duration=140)
        super().mouseReleaseEvent(event)

    def changeEvent(self, event) -> None:  # noqa: ANN001
        super().changeEvent(event)
        if event.type() == QEvent.Type.EnabledChange:
            if not self.isEnabled():
                self._hovered = False
                self._pressed = False
            self._animate_to(self._target_blur(), duration=120)


def make_separator() -> QFrame:
    sep = QFrame()
    sep.setObjectName("toolbarSeparator")
    sep.setFrameShape(QFrame.Shape.NoFrame)
    sep.setFixedWidth(1)
    sep.setFixedHeight(22)
    return sep


def make_status_chip(initial: str = "") -> QLabel:
    label = QLabel(initial)
    label.setProperty("class", "statusChip")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return label

