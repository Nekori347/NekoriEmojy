"""Surface geometry shared by the workbench, settings and auxiliary windows.

Only the native window blurs. These surfaces express nesting through paint,
space and edges; a child never requests another desktop backdrop.
"""
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QLinearGradient
from PySide6.QtWidgets import QWidget, QLabel, QHBoxLayout
from fluent_ui import visual


class Surface(QWidget):
    def __init__(self, role='base', parent=None, *, radius=14, edge=True):
        super().__init__(parent)
        self.surface_role, self.radius, self.edge = role, radius, edge
        self.setAutoFillBackground(False)
        visual.theme.changed.connect(self.update)
        visual.theme.accent_changed.connect(self.update)

    def paintEvent(self, event):
        c = visual.colors()
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(.5,.5,-.5,-.5)
        colors = {'base':'content_base','raised':'surface','recessed':'surface_alt','overlay':'surface_overlay','navigation':'navigation'}
        color = QColor(c[colors[self.surface_role]])
        if self.surface_role == 'navigation':
            color.setAlpha(32 if self.window().property('nativeMaterial') == 'acrylic' else 100)
        p.setPen(QPen(QColor(c['border_soft']),1) if self.edge else Qt.NoPen)
        p.setBrush(color); p.drawRoundedRect(r,self.radius,self.radius)
        if self.surface_role == 'navigation':
            # Low-information lower edge: one fading dot field, no repeated cards.
            p.setPen(Qt.NoPen)
            for x in range(12,min(self.width()-8,112),8):
                for y in range(max(16,self.height()-70),self.height()-12,8):
                    ink=QColor(c['text']); ink.setAlphaF(.065*(1-(x-12)/112))
                    p.setBrush(ink);p.drawEllipse(QPointF(x,y),.65,.65)


class RuleHeading(QWidget):
    """A semantic section title anchored to its surface's inner baseline."""
    def __init__(self, text, parent=None):
        super().__init__(parent)
        row=QHBoxLayout(self);row.setContentsMargins(12,8,12,8)
        self.label=QLabel(text,self);self.label.setFont(visual.font('section_title'))
        row.addWidget(self.label);row.addStretch()
        self.setMinimumHeight(38)

    def paintEvent(self,event):
        p=QPainter(self);c=visual.colors()
        y=self.height()-1
        p.setPen(QPen(QColor(c['border_soft']),1));p.drawLine(12,y,self.width()-12,y)
        p.setPen(QPen(QColor(c['accent']),2));p.drawLine(12,y,36,y)


class CommandWell(Surface):
    def __init__(self,parent=None):
        super().__init__('recessed',parent,radius=10,edge=False)
        self.row=QHBoxLayout(self);self.row.setContentsMargins(5,3,5,3);self.row.setSpacing(2)


class IdentityLabel(QLabel):
    """Latin branding may share a caption with translated text."""
    def __init__(self,text='',parent=None):
        super().__init__(text,parent)
        self.setFont(visual.font('brand'))
        self.setProperty('role','brand')
