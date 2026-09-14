import json,os,sys,time,traceback
from pathlib import Path
from unittest.mock import patch
work=Path(os.environ['P3_WORK_DIR']).resolve();repo=Path(__file__).resolve().parents[2];os.chdir(repo);sys.path.insert(0,str(repo));os.environ['QT_QPA_PLATFORM']='offscreen'
from services.library import open_library
from services.config import ConfigService
from services.storage import StorageService
from services.clipboard import ClipboardService
from services.category_groups import CategoryGroups
from services.i18n import i18n_engine
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QThread
from PySide6.QtTest import QTest
from qfluentwidgets import qconfig
import requests
session=open_library(work/'performance/library');store=StorageService(session);config=ConfigService(session)
app=QApplication([]);app.setQuitOnLastWindowClosed(False);qconfig.file=session.context.data_dir/'cache'/'qt-state.json';i18n_engine.init(config)
errors=[];sys.excepthook=lambda *exc:errors.append(str(exc[1]));report={}
with patch('requests.sessions.Session.request',side_effect=requests.ConnectionError('isolated')),patch('fluent_ui.main_window.MainWindow.bind_global_hotkey'):
    from fluent_ui.main_window import MainWindow
    window=MainWindow(store,ClipboardService(config),config);window.resize(1000,730);window.show();QTest.qWait(300)
    try:
        g=window.gallery_interface;g.set_category('大分类');QTest.qWait(250)
        report['initial_cards']=len(g._all_card_widgets)
        report['before_jump']={'maximum':g.scroll_area.verticalScrollBar().maximum(),'predicted_last_y':g._group_card_tops[-1],'last_cell_y':g.gallery_layout.cellRect(*g._group_card_positions[-1]).y(),'columns':g._current_columns}
        bar=g.scroll_area.verticalScrollBar();bar.setValue(bar.maximum())
        deadline=time.perf_counter()+15
        while g._is_loading and time.perf_counter()<deadline:QTest.qWait(10)
        QTest.qWait(200)
        last=g._all_card_widgets[-1]
        report['cards_after_jump_to_end']=len(g._all_card_widgets)
        report['after_jump']={'maximum':bar.maximum(),'value':bar.value(),'predicted_last_y':g._group_card_tops[-1],'last_cell_y':g.gallery_layout.cellRect(*g._group_card_positions[-1]).y(),'columns':g._current_columns}
        report['last_group_visible']=last.image_path.endswith('asset-1999.png') and last.geometry().intersects(g.scroll_area.viewport().rect().translated(0,bar.value()))
        assert report['last_group_visible']
        bar.setValue(0);QTest.qWait(80)
        start=time.perf_counter();g._group_sections[0]['header'].collapse();sync=(time.perf_counter()-start)*1000;QTest.qWait(250)
        report['fold_500_member_group_ms']=round(sync,2)
        report['folded_first_group']=g._group_sections[0]['collapsed'] and g._group_sections[0]['paths']==[]
        assert report['folded_first_group']
        report['cards_after_fold']=len(g._all_card_widgets)
        window.resize(520,430);QTest.qWait(200)
        assert g._current_columns>=1
        report['narrow_columns']=g._current_columns
        report['narrow_widths']={'window':window.width(),'viewport':g.scroll_area.viewport().width()}
        assert g._current_columns == max(1,(g.scroll_area.viewport().width()-32)//130)
        g._group_sections[0]['header'].collapse();QTest.qWait(150)
    except Exception:report['error']=traceback.format_exc()
    report['qt_errors']=errors;report['passed']='error' not in report and not errors
    print(json.dumps(report,indent=2),flush=True);(work/'p3-scroll.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    for thread in window.findChildren(QThread):thread.wait(5000)
    window.settings_window.close();window.close();window.quick_panel.close();QTest.qWait(50)
session.close()
