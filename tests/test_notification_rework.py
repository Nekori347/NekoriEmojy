"""Acceptance rework: generated result counts and the duplicate row only."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from PySide6.QtCore import Qt,QEvent,QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QWidget,QVBoxLayout
from fluent_ui.components.controls import focus_input
from services.i18n import i18n_engine
from test_notification_interaction import scene,enter


@pytest.mark.parametrize('saved,duplicates,skipped,failed,expected',[
    (4,0,0,0,'import-added'),(0,0,1,0,'import-skipped'),
    (2,1,0,0,None),(2,0,0,1,None),(0,0,0,1,None)])
def test_real_gallery_result_mapping_keeps_counts_and_failure_level(saved,duplicates,skipped,failed,expected):
    from fluent_ui.views.gallery_view import GalleryInterface
    rows=json.loads((Path(__file__).parent/'fixtures/notification_tooltip_copy.json').read_text(encoding='utf-8'))
    r=SimpleNamespace(state='completed',saved=saved,duplicates=duplicates,skipped=skipped,failed=failed,
        kept=0,errors=[],done=saved+duplicates+skipped+failed,total=4,kind='import',phase='completed')
    host=Mock();v=SimpleNamespace(imports=SimpleNamespace(requests={'generated':r}),ocr=SimpleNamespace(jobs={}),feedback_host=host)
    for lang in ('zh','zh_TW','en','ja'):
        i18n_engine.load_language(lang);GalleryInterface._sync_background_tasks(v)
        value=host.upsert_task.call_args.kwargs
        if expected:
            text=next(row for row in rows if row.get('id')==expected)['values'][lang]
            assert value['caption']==text.format(added=saved,skipped=skipped)
        else:
            assert value['caption'] is None
        assert value['state']==('partial' if failed else 'success')
        assert (r.saved,r.duplicates,r.skipped,r.failed)==(saved,duplicates,skipped,failed)
    i18n_engine.load_language('zh')


def test_group_is_shared_neutral_and_only_interactive_when_entered(scene):
    app,w,h,u=scene
    h.toast('Generated one',kind='success');h.toast('Generated two',kind='success')
    enter(app,u.cover);u.ear.click();app.processEvents()
    assert u.opened and not u.clear_button.isVisible()
    enter(app,u.controls);app.processEvents()
    assert u.clear_button.isVisible()
    assert u.clear_button.parentWidget() is u.ear.parentWidget() is u.controls
    assert u.clear_button.property('role')!='danger'
    for root in (u.controls,u.ear,u.clear_button,u.panel):app.sendEvent(root,QEvent(QEvent.Leave))
    QTest.qWait(210);assert not u.clear_button.isVisible()
    u.collapse();app.processEvents();assert not u.clear_button.isVisible()


def test_duplicate_row_uses_keyboard_origin_without_changing_checkbox_input():
    from fluent_ui.components.duplicate_dialog import DuplicateApplyCheckBox
    app=QApplication.instance() or QApplication([])
    w=QWidget();layout=QVBoxLayout(w);box=DuplicateApplyCheckBox(w);box.setText('Generated apply all (1)');layout.addWidget(box)
    w.resize(760,100);w.show();app.setActiveWindow(w);app.processEvents()
    QTest.mouseClick(box,Qt.LeftButton,pos=QPoint(10,box.height()//2))
    assert box.isChecked() and not box.focus_indicator_visible()
    QTest.keyClick(box,Qt.Key_Space)
    assert not box.isChecked() and box.focus_indicator_visible()
    QTest.keyClick(box,Qt.Key_Space);assert box.isChecked()
    QTest.mouseClick(box,Qt.LeftButton,pos=QPoint(10,box.height()//2))
    assert not box.isChecked() and not box.focus_indicator_visible()
    w.close();w.deleteLater();app.processEvents()
