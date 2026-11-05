"""Parent fallback never steals accepted child semantics or internal drags."""
from unittest.mock import Mock
from PySide6.QtCore import Qt,QMimeData,QPoint,QPointF,QUrl
from PySide6.QtGui import QImage,QColor,QDragEnterEvent,QDropEvent
from PySide6.QtWidgets import QWidget,QPushButton,QApplication
from PySide6.QtTest import QTest
from test_phase2_interaction import surface
from fluent_ui.components.window_import import install_window_import
from services.external_drag import ResourceDragMimeData


def events(window,point,mime):
    enter=QDragEnterEvent(point,Qt.CopyAction,mime,Qt.LeftButton,Qt.NoModifier)
    QApplication.sendEvent(window,enter)
    drop=QDropEvent(QPointF(point),Qt.CopyAction,mime,Qt.LeftButton,Qt.NoModifier)
    QApplication.sendEvent(window,drop)
    return enter,drop


def test_blank_drop_uses_common_paste_target_and_batch_boundary(surface):
    s=surface;window=QWidget();window.resize(500,300);window.setAttribute(Qt.WA_DontShowOnScreen);window.show()
    install_window_import(window,s.g)
    source=s.tmp/'new-fallback.png';image=QImage(31,27,QImage.Format_RGB32);image.fill(QColor(17,31,99));image.save(str(source))
    mime=QMimeData();mime.setUrls([QUrl.fromLocalFile(str(source))])
    before=len(s.g.imports.requests);enter,drop=events(window,QPoint(450,250),mime)
    assert enter.isAccepted() and drop.isAccepted()
    request=list(s.g.imports.requests.values())[-1]
    assert len(s.g.imports.requests)==before+1 and request.target.parent_node==s.parent
    assert request.drag_session_id
    for _ in range(100):
        if request.state in ('completed','failed','cancelled'):break
        QTest.qWait(20)
    assert request.state=='completed' and request.saved==1
    assert len(request.paths)==1
    window.hide();window.deleteLater()


def test_internal_resource_and_interactive_control_never_become_plain_import(surface):
    s=surface;window=QWidget();window.resize(500,300);window.setAttribute(Qt.WA_DontShowOnScreen);window.show()
    receiver=install_window_import(window,s.g)
    own=ResourceDragMimeData(s.paths[:1]);own._files=Mock(side_effect=AssertionError('must not materialize internal data'))
    before=len(s.g.imports.requests)
    enter,drop=events(window,QPoint(450,250),own)
    assert not enter.isAccepted() and not drop.isAccepted() and len(s.g.imports.requests)==before
    button=QPushButton('normal action',window);button.setGeometry(100,100,150,40);button.show()
    incoming=QMimeData();incoming.setImageData(QImage(20,20,QImage.Format_RGB32))
    assert not receiver._blank(QPoint(120,120))
    assert not events(window,QPoint(120,120),incoming)[0].isAccepted()
    assert len(s.g.imports.requests)==before
    window.hide();window.deleteLater()


def test_invalid_file_rejected_with_existing_feedback(surface):
    s=surface;window=QWidget();window.resize(500,300)
    receiver=install_window_import(window,s.g)
    path=s.tmp/'unsupported.txt';path.write_text('not an emoji')
    mime=QMimeData();mime.setUrls([QUrl.fromLocalFile(str(path))])
    event=QDropEvent(QPointF(20,20),Qt.CopyAction,mime,Qt.LeftButton,Qt.NoModifier)
    receiver.eventFilter(window,event)
    assert not event.isAccepted()
    assert s.g.feedback_host.notices[-1][0]=='无法导入'
    window.deleteLater()
