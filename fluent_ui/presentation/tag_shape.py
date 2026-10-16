"""The same cut-corner tag contour in the dock and tag editor."""
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainterPath


def tag_path(rect):
    r=QRectF(rect)
    path=QPainterPath();path.moveTo(r.left()+7,r.top());path.lineTo(r.right(),r.top())
    path.lineTo(r.right(),r.bottom());path.lineTo(r.left()+7,r.bottom())
    path.lineTo(r.left(),r.center().y());path.closeSubpath()
    return path
