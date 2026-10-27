import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import Qt,QEvent
from PySide6.QtWidgets import QApplication,QWidget
from PySide6.QtTest import QTest,QSignalSpy
from fluent_ui.components.feedback import FeedbackHost


def test_clear_completed_button_preserves_actionable_records_and_collapses():
    app=QApplication.instance() or QApplication([])
    owner=QWidget();owner.resize(1100,700);owner.show()
    host=FeedbackHost(owner)
    for key in ('running','waiting','error','warning','partial','cancelled','interrupted'):
        host.upsert_task(key,key,state=key,cancel=lambda:None)
    host.upsert_task('success','Done',state='success')
    host.upsert_task('info','Notice',state='info')
    host.upsert_task('resume','Resume',state='success',resume=lambda:None)
    ui=host._caption_ui;app.sendEvent(host.strip,QEvent(QEvent.Enter));app.sendEvent(ui.controls,QEvent(QEvent.Enter));folded=QSignalSpy(ui.fold.finished);ui.ear.click()
    if ui.expansion<.999:assert folded.wait(2000)
    assert ui.opened and ui.clear_button.isVisible(), (ui.expansion,host.clearable_tasks(),owner.isVisible())
    QTest.mouseClick(ui.clear_button,Qt.LeftButton)
    assert not ui.opened and ui.clear_button.isHidden()
    assert set(host.named_tasks)=={'running','waiting','error','warning','partial','cancelled','interrupted','resume'}
    owner.close();owner.deleteLater();app.processEvents()
