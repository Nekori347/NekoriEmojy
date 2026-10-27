"""Approved sorting copy; real controls, no Library."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json
from pathlib import Path
from types import SimpleNamespace
from PySide6.QtWidgets import QApplication,QWidget
from services.i18n import i18n_engine
COPY=json.loads((Path(__file__).parent/'fixtures/notification_tooltip_copy.json').read_text(encoding='utf-8'))

def test_exact_sort_mapping_and_language_refresh():
    from fluent_ui.components.navigation import SortCycleButton
    from fluent_ui.views.gallery_view import GalleryInterface
    app=QApplication.instance() or QApplication([])
    w=QWidget()
    for family,title in [('分类','分类显示排序'),('标签','标签显示排序')]:
        b=SortCycleButton(title,w)
        for r in [r for r in COPY if r.get('family')==family]:
            b.set_mode(r['mode'])
            for lang,text in r['values'].items():
                i18n_engine.load_language(lang)
                assert b.toolTip()==text and b.accessibleName()==text
                assert b.mode.value==r['mode']
    from fluent_ui.components.controls import TransparentToolButton
    v=SimpleNamespace(btn_content_sort=TransparentToolButton(w))
    for r in [r for r in COPY if r.get('family')=='表情']:
        v.content_sort=r['mode']
        for lang,text in r['values'].items():
            i18n_engine.load_language(lang);GalleryInterface._update_resource_sort_label(v)
            assert v.btn_content_sort.toolTip()==text
            assert v.btn_content_sort.accessibleName()==text

    w.deleteLater();app.processEvents();i18n_engine.load_language('zh')


def test_exact_approved_translation_diff():
    import subprocess
    root=Path(__file__).resolve().parents[1]
    for lang in ('zh','zh_TW','en','ja'):
        path=f'translations/{lang}.json'
        expected=json.loads(subprocess.check_output(['git','show',f'5529adb:{path}'],cwd=root).decode('utf-8'))
        for row in COPY:expected[row['source']]=row['values'][lang]
        assert json.loads((root/path).read_text(encoding='utf-8'))==expected
