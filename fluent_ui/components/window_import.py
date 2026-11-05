"""Parent-only ordinary import fallback; Qt's accepted child drops stay first."""
import logging
from PySide6.QtCore import QObject,QEvent,Qt
from PySide6.QtWidgets import QAbstractButton,QLineEdit,QTextEdit,QPlainTextEdit,QComboBox,QAbstractItemView
from services.clipboard import ClipboardService
from services.i18n import t
from fluent_ui.components.drop_contract import (
    RESOURCE_MIME,NODE_MIME,TAG_MIME,prepare_drag,DropTarget,INTO,IMPORT)


class WindowImportReceiver(QObject):
    def __init__(self,window,gallery):
        super().__init__(window);self.window=window;self.gallery=gallery
        window.setAcceptDrops(True);window.installEventFilter(self)

    def _blank(self,point):
        widget=self.window.childAt(point)
        while widget is not None and widget is not self.window:
            if isinstance(widget,(QAbstractButton,QLineEdit,QTextEdit,QPlainTextEdit,QComboBox)):
                return False
            if isinstance(widget,QAbstractItemView) and widget.indexAt(widget.viewport().mapFrom(self.window,point)).isValid():
                return False
            if type(widget).__name__ in ('EmojiCard','NodeCard','NodeRenderer','CategoryItem','TagChip'):
                return False
            widget=widget.parentWidget()
        return True

    def eventFilter(self,watched,event):
        if watched is not self.window or event.type() not in (QEvent.DragEnter,QEvent.DragMove,QEvent.Drop):
            return False
        mime=event.mimeData()
        if any(mime.hasFormat(fmt) for fmt in (RESOURCE_MIME,NODE_MIME,TAG_MIME)) or not self._blank(event.position().toPoint()):
            event.ignore();return True
        if event.type()!=QEvent.Drop:
            if mime.hasImage():supported=True
            else:
                kind,_=ClipboardService.importable_payload(mime,self.gallery.storage.SUPPORTED_FORMATS)
                supported=kind is not None
            if supported:event.setDropAction(Qt.CopyAction);event.accept()
            else:event.ignore()
            return True
        operation=prepare_drag(mime)
        if operation.state!='dragging':event.ignore();return True
        operation.target=DropTarget(INTO,IMPORT,None,self.gallery.content_scope_node()).freeze()
        kind,payload=ClipboardService.importable_payload(mime,self.gallery.storage.SUPPORTED_FORMATS)
        if kind is None:
            self.gallery.feedback_host.notice(t('无法导入'),t('未找到支持的表情文件或图片。'),error=True)
            event.ignore();return True
        request=[]
        def submit():
            from shiboken6 import isValid
            if not isValid(self.window) or not isValid(self.gallery):return False
            identity=self.gallery._import_clipboard_payload(operation.target.container_id,kind,payload)
            if not identity:return False
            request.append(identity)
            self.gallery.imports.requests[identity].drag_session_id=operation.id
            return True
        if operation.complete(submit):
            logging.getLogger('nekori.drag').info('session=%s import_task=%s target=%s',operation.id,request[0],operation.target.container_id)
            event.setDropAction(Qt.CopyAction);event.accept()
        else:event.ignore()
        return True


def install_window_import(window,gallery):
    if not hasattr(window,'_window_import_receiver'):
        window._window_import_receiver=WindowImportReceiver(window,gallery)
    return window._window_import_receiver
