"""Shared action geometry, taken from the existing footer MetaButton painter."""
from functools import lru_cache
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainterPath, QTransform


@lru_cache(maxsize=1)
def default_reset_path():
    # Exactly the original MetaButton default-action symbol. Its enclosing
    # solid disk is a button decoration and deliberately is not part of this.
    path=QPainterPath();path.addEllipse(QRectF(-10,-10,20,20))
    hole=QPainterPath();hole.addEllipse(QRectF(-6,-6,12,12))
    path=path.subtracted(hole)
    cut=QPainterPath();cut.addRect(QRectF(-2,-13,4,26))
    return path.subtracted(QTransform().rotate(35).map(cut))
