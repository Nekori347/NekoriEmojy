"""One display deadline over the owner's existing timeout timer.

The finite animation only requests paints. Only QTimer.timeout expires a notice.
"""
from PySide6.QtCore import QObject, Signal, QElapsedTimer, Qt, QVariantAnimation, QRectF
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import QWidget
from fluent_ui import visual


class DisplayDeadline(QObject):
    changed = Signal()
    expired = Signal()

    def __init__(self, timer, parent, motion=visual.animations_enabled):
        super().__init__(parent)
        self.timer = timer
        timer.setSingleShot(True)
        timer.setTimerType(Qt.PreciseTimer)
        timer.timeout.connect(self._timeout)
        self.clock = QElapsedTimer()
        self.total = self._remaining = 0
        self.active = self.paused = self.presented = False
        self.key = None
        self.generation = 0
        self.motion = motion
        self.paint_motion = QVariantAnimation(self)
        self.paint_motion.setStartValue(0.0)
        self.paint_motion.setEndValue(1.0)
        self.paint_motion.valueChanged.connect(lambda _: self.changed.emit())
        visual.theme.motion_changed.connect(self.sync_visual)

    @property
    def remaining(self):
        if not self.active:
            return 0
        return max(0, self._remaining - (self.clock.elapsed() if not self.paused and self.clock.isValid() else 0))

    @property
    def fraction(self):
        return self.remaining / self.total if self.active and self.total else 0.0

    def start(self, duration, key=None):
        self.stop()
        self.generation += 1
        self.key = key
        self.total = self._remaining = max(1, int(duration))
        self.active = True
        self.clock.start()
        self.timer.start(self._remaining)
        self.sync_visual()

    def pause(self):
        if self.active and not self.paused:
            self._remaining = self.remaining
            self.paused = True
            self.timer.stop()
            self.clock.invalidate()
            self.sync_visual()

    def resume(self):
        if self.active and self.paused:
            self.paused = False
            self.clock.start()
            self.timer.start(max(1, self._remaining))
            self.sync_visual()

    def stop(self):
        self.timer.stop()
        self.paint_motion.stop()
        self.active = self.paused = False
        self._remaining = 0
        self.key = None
        self.clock.invalidate()
        self.changed.emit()

    def set_presented(self, presented):
        if self.presented != presented:
            self.presented = presented
            self.sync_visual()

    def sync_visual(self):
        if not (self.active and self.presented and not self.paused and self.motion()):
            self.paint_motion.stop()
        elif self.paint_motion.state() != QVariantAnimation.Running:
            self.paint_motion.setDuration(max(1, self.remaining))
            self.paint_motion.start()
        self.changed.emit()

    def _timeout(self):
        if not self.active or self.paused:
            return
        # An early or superseded timer delivery cannot expire a new display.
        if self.remaining:
            self.timer.start(self.remaining)
            return
        self.stop()
        self.expired.emit()


class CountdownLine(QWidget):
    def __init__(self, parent, deadline):
        super().__init__(parent)
        self.deadline = deadline
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        deadline.changed.connect(self.refresh)
        visual.theme.changed.connect(self.update)
        visual.theme.accent_changed.connect(self.update)
        self.hide()

    def refresh(self):
        self.setVisible(self.deadline.active and self.deadline.motion() and self.deadline.presented)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(QRectF(0, 0, self.width()*self.deadline.fraction, self.height()), QColor(visual.accent()))
