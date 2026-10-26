"""Real Qt text layout with fake batch/OCR state; no workers or data tasks."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import importlib
import json
import subprocess
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from PySide6.QtCore import QObject,Signal
from PySide6.QtWidgets import QApplication,QWidget,QVBoxLayout
from PySide6.QtTest import QTest
from qfluentwidgets import Theme,setTheme
from services.config import ConfigService
from services.i18n import i18n_engine
from fluent_ui import visual


def test_batch_summary_and_ocr_live_layout(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([])
    monkeypatch.setenv('NEKORI_APP_DATA',str(tmp_path/'app'))
    monkeypatch.setenv('NEKORI_LIBRARY',str(tmp_path/'unused-library'))
    monkeypatch.setattr('requests.sessions.Session.request',Mock(side_effect=AssertionError('No network')))
    config=ConfigService();i18n_engine.init(config);visual.theme.configure(config)
    # Use reviewed window hosts, never the protected W01 worktree experiments.
    if os.environ.get('QT_QPA_PLATFORM')=='windows':
        root=Path(__file__).resolve().parents[1]
        for short in ('materials','window_shell'):
            module=importlib.import_module('fluent_ui.'+short)
            source=subprocess.check_output(['git','show',f'HEAD:fluent_ui/{short}.py'],cwd=root).decode('utf-8')
            exec(compile(source,str(root/'fluent_ui'/f'{short}.py'),'exec'),module.__dict__)
    from fluent_ui.components.tg_batch_dialog import TGBatchPackageDialog
    from fluent_ui.components import ocr_controls
    from fluent_ui.components.setting_rows import SettingSection
    mapping=json.loads((Path(__file__).parent/'fixtures/tpb_batch3_copy.json').read_text(encoding='utf-8'))
    m={r['id']:r for r in mapping['records']}

    class FakeOcr(QObject):
        changed=Signal()
        component_finished=Signal(bool,str)
        def __init__(self):
            super().__init__()
            self.component=SimpleNamespace(installed=True,_sizes=dict(download=100,installed=200),release=lambda:{},sizes=lambda:None)
            self.install_state='';self.installing=False;self.install_error='';self.available=True
            self.library_busy=False;self.busy=False
            self.summary=dict(state='waiting_source',done=2,failed=1,skipped=1,total=6,error='Generated source error')
            self.storage=SimpleNamespace(index=SimpleNamespace(search_revision=0,connect=self.connect))
            self.cancel=Mock()
        @contextmanager
        def connect(self,**_):
            yield SimpleNamespace(execute=lambda *_:SimpleNamespace(fetchone=lambda:None))
    service=FakeOcr();monkeypatch.setattr(ocr_controls,'ocr_service',lambda *_:service)
    class Center(QWidget):
        def __init__(self):
            super().__init__();self.config=config;self.storage=None;self.pending={};self.body=QVBoxLayout(self)
            self.setStyleSheet(visual.settings_style())
        def _section(self,title):
            s=SettingSection(title,self);self.body.addWidget(s);return s
        def _track(self,row,*_):return row
    owner=QWidget();owner.resize(1000,740);owner.show()
    measurements=[]
    for lang in ('zh','zh_TW','en','ja'):
        i18n_engine.load_language(lang)
        for theme in (Theme.LIGHT,Theme.DARK):
            setTheme(theme);visual.theme.refresh()
            for width,height in ((920,640),(680,480)):
                dialog=TGBatchPackageDialog(owner,'generated-output',{},None,None)
                dialog.worker=SimpleNamespace(results=[dict(status='done'),dict(status='failed'),dict(status='cancelled')],error=None,isRunning=lambda:False)
                dialog._finished();dialog.resize(width,height);dialog.show();QTest.qWait(35)
                assert dialog.summary.text()==m['batch-078']['values'][lang].format(success=1,failed=1,cancelled=1)
                needed=dialog.summary.heightForWidth(dialog.summary.contentsRect().width())
                assert dialog.summary.height()>=needed,(lang,theme,width,dialog.summary.size(),needed)
                assert dialog.summary.geometry().bottom()<dialog.close_button.mapTo(dialog,dialog.close_button.rect().topLeft()).y()
                if os.environ.get('QT_QPA_PLATFORM')=='windows':
                    dest=Path(__file__).resolve().parents[2]/'DevData/ui-refresh'
                    dialog.grab().save(str(dest/f'tpb3-batch-{lang}-{theme.value}-{width}.png'))
                measurements.append((lang,theme.value,width,dialog.summary.width(),dialog.summary.height(),needed))
                dialog.worker=None;dialog.close();dialog.deleteLater();app.processEvents()
            center=Center();center.resize(760,700);panel=ocr_controls.OcrSettings(center);center.show();QTest.qWait(35)
            assert panel.task.value_label.text()==m['ocr-096']['values'][lang]
            assert panel.task.value_label.height()>=panel.task.value_label.heightForWidth(panel.task.value_label.width())
            assert m['ocr-097']['values'][lang].format(done=4,total=6,failed=1,skipped=1) in panel.task_info.text()
            assert panel.task_info.height()>=panel.task_info.heightForWidth(panel.task_info.width())
            if os.environ.get('QT_QPA_PLATFORM')=='windows':
                center.grab().save(str(dest/f'tpb3-ocr-{lang}-{theme.value}.png'))
            center.close();center.deleteLater();app.processEvents()
    owner.close();owner.deleteLater();i18n_engine.load_language('zh')
    print('TPB3_QT_LAYOUT',json.dumps(measurements))
