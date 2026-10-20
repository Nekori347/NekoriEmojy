"""Inline keyboard hints with real rounded key faces and normal text wrapping."""
import math
import re
from PySide6.QtCore import QObject, QSize, QSizeF, QPointF, QEvent, Qt
from PySide6.QtGui import (QPainter,QColor,QPen,QFontMetricsF,QTextDocument,
    QTextCursor,QTextCharFormat,QTextFormat,QPyTextObject,QAbstractTextDocumentLayout)
from PySide6.QtWidgets import QLabel
from fluent_ui import visual

KEY_PATTERN=re.compile(r'(?<![A-Za-z0-9_./\\])(?:Ctrl|Alt|Shift|Win|Enter(?!\s+(?:a|an|the|your)\b)|Esc|Tab|Space|Backspace|Delete|Home|End|PgUp|PgDown|F(?:1[0-2]|[1-9]))(?:\s*\+\s*(?:Ctrl|Alt|Shift|Win|[A-Z0-9]))*(?![A-Za-z0-9_./\\])')
KEY_OBJECT=QTextFormat.UserObject+9
KEY_TEXT=QTextFormat.UserProperty+9


def paint_keycap(p,rect,text,font):
    p.save();p.setRenderHint(QPainter.Antialiasing);c=visual.colors()
    p.setPen(QPen(QColor(c['border']),.8));p.setBrush(QColor(c['surface_alt']))
    p.drawRoundedRect(rect.adjusted(.5,.5,-.5,-.5),3,3)
    p.setPen(QColor(c['text']));p.setFont(font)
    metrics=QFontMetricsF(font);ink=metrics.tightBoundingRect(text)
    p.drawText(QPointF(rect.center().x()-ink.center().x(),rect.center().y()-ink.center().y()),text);p.restore()


class KeyFace(QPyTextObject):
    def intrinsicSize(self,doc,pos,fmt):
        metrics=QFontMetricsF(fmt.toCharFormat().font())
        return QSizeF(metrics.horizontalAdvance(fmt.property(KEY_TEXT))+12,metrics.height()+2)

    def drawObject(self,p,rect,doc,pos,fmt):
        paint_keycap(p,rect,fmt.property(KEY_TEXT),fmt.toCharFormat().font())


class KeycapLabel(QLabel):
    """Only labels use this; shortcut editors continue to use native text input."""
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self._document=QTextDocument(self);self._document.setDocumentMargin(0)
        self._key_face=KeyFace(self)
        self._document.documentLayout().registerHandler(KEY_OBJECT,self._key_face)
        self._rebuild()

    def setText(self,text):
        super().setText(text)
        if hasattr(self,'_document'):self._rebuild()

    def _rebuild(self):
        self._document.clear();self._document.setDefaultFont(self.font())
        cursor=QTextCursor(self._document);text=self.text();start=0
        for match in KEY_PATTERN.finditer(text):
            cursor.insertText(text[start:match.start()])
            fmt=QTextCharFormat();fmt.setObjectType(KEY_OBJECT)
            fmt.setVerticalAlignment(QTextCharFormat.AlignBaseline)
            fmt.setProperty(KEY_TEXT,match.group())
            key_font=visual.font('data');key_font.setPixelSize(self.font().pixelSize() if self.font().pixelSize()>0 else 12)
            fmt.setFont(key_font)
            cursor.insertText('\ufffc',fmt);cursor.setCharFormat(QTextCharFormat())
            start=match.end()
        cursor.insertText(text[start:]);self.updateGeometry();self.update()

    def hasHeightForWidth(self):return self.wordWrap()

    def heightForWidth(self,width):
        if not hasattr(self,'_document'):return super().heightForWidth(width)
        self._document.setTextWidth(max(1,width) if self.wordWrap() else -1)
        return math.ceil(self._document.size().height())

    def sizeHint(self):
        if not hasattr(self,'_document'):return super().sizeHint()
        self._document.setTextWidth(-1)
        width=math.ceil(self._document.idealWidth())
        if self.wordWrap():width=min(480,width)
        return QSize(width,self.heightForWidth(width))

    def minimumSizeHint(self):
        hint=self.sizeHint()
        return QSize(min(80,hint.width()),self.fontMetrics().height()+6)

    def event(self,event):
        result=super().event(event)
        if event.type()==QEvent.FontChange and hasattr(self,'_document'):self._rebuild()
        return result

    def paintEvent(self,event):
        # Wrapped paragraphs must honour the label's horizontal alignment;
        # translating a full-width document cannot centre its individual lines.
        option=self._document.defaultTextOption()
        alignment=self.alignment() & Qt.AlignHorizontal_Mask
        if option.alignment()!=alignment:
            option.setAlignment(alignment)
            self._document.setDefaultTextOption(option)
        p=QPainter(self);rect=self.contentsRect()
        self._document.setTextWidth(rect.width() if self.wordWrap() else -1)
        size=self._document.size();x=rect.x();y=rect.y()
        if self.alignment()&Qt.AlignHCenter:x+=(rect.width()-size.width())/2
        elif self.alignment()&Qt.AlignRight:x+=rect.width()-size.width()
        if self.alignment()&Qt.AlignVCenter:y+=(rect.height()-size.height())/2
        p.setClipRect(rect);p.translate(QPointF(x,y))
        context=QAbstractTextDocumentLayout.PaintContext();context.palette=self.palette()
        self._document.documentLayout().draw(p,context)
