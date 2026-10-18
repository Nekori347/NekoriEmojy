"""Layout and UI state contracts of the one-page library setup, isolated only."""
from unittest.mock import Mock,patch
from PySide6.QtWidgets import QFileDialog,QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from fluent_ui.components.library_setup import LibrarySetupDialog
from services.i18n import i18n_engine
from test_library_setup import setup_case


def settle(app):
    app.processEvents();QTest.qWait(30);app.processEvents()


def test_full_path_copy_and_long_path_does_not_grow_window(setup_case):
    s=setup_case;d=LibrarySetupDialog(s.config,s.root/'short');d.show();settle(s.app)
    height=d.height();width=d.width()
    long=str(s.root/('中文 directory with spaces '*12)/'NekoriEmojy Library')
    d.path=long;d._render_state();settle(s.app)
    assert d.height()==height and d.width()==width
    assert d.path_box.toolTip()==long and d.path_label.toolTip()==long
    assert '…' in d.path_label.text() and d.path_label.text().endswith('NekoriEmojy Library')
    clipboard=Mock()
    with patch.object(QApplication,'clipboard',return_value=clipboard):
        QTest.mouseClick(d.path_box.copy_button,Qt.LeftButton)
        clipboard.setText.assert_called_once_with(long)
    assert not d.path_label.wordWrap()


def test_failed_commit_requires_reselection_and_hides_technical_error(setup_case,monkeypatch):
    s=setup_case;d=LibrarySetupDialog(s.config,s.root/'first');d.show();settle(s.app)
    commit=Mock(side_effect=PermissionError('PRIVATE RAW ERROR'))
    monkeypatch.setattr('fluent_ui.components.library_setup.commit_library',commit)
    QTest.mouseClick(d.start_button,Qt.LeftButton);settle(s.app)
    assert d.windowTitle()=='无法使用所选位置' and d.start_button.text()=='选择其他位置…'
    assert d.details.isHidden() and 'PRIVATE' not in d.error_label.text()
    assert d.error_label.text()=='无法写入该文件夹。'
    assert d.path_box.full_path==str(s.root/'first')
    monkeypatch.setattr(QFileDialog,'getExistingDirectory',lambda *args:'')
    QTest.mouseClick(d.start_button,Qt.LeftButton)
    assert commit.call_count==1 and d._failed and d.storage is None
    QTest.mouseClick(d.details_button,Qt.LeftButton);assert d.details.isVisible()
    monkeypatch.setattr(QFileDialog,'getExistingDirectory',lambda *args:str(s.root/'second'))
    QTest.mouseClick(d.start_button,Qt.LeftButton);settle(s.app)
    assert commit.call_count==1 and not d._failed and d._ready and d.details.isHidden()
    assert d.path==str(s.root/'second') and d.start_button.text()=='开始使用'
    assert not (s.root/'second').exists()


def test_recovery_has_locate_before_start_and_separate_path_labels(setup_case,monkeypatch):
    from services.library_index import LibraryIndex
    s=setup_case;old=s.root/'missing';chosen=s.root/'existing';LibraryIndex(chosen)
    d=LibrarySetupDialog(s.config,old,recovery=True);d.show();settle(s.app)
    assert d.start_button.text()=='重新定位表情库…' and not d._ready
    assert d.path_box.full_path==str(old) and d.selected_box.isHidden()
    monkeypatch.setattr(QFileDialog,'getExistingDirectory',lambda *args:str(chosen))
    QTest.mouseClick(d.start_button,Qt.LeftButton);settle(s.app)
    assert d.start_button.text()=='连接并开始' and d.storage is None
    assert d.path_heading.text()=='原表情库位置' and d.selected_heading.text()=='所选位置'
    assert d.path_box.full_path==str(old) and d.selected_box.full_path==str(chosen)
    d.show_failure(PermissionError('error'),initialization=True);settle(s.app)
    assert d.windowTitle()=='无法使用所选位置' and d.path_box.full_path==str(chosen)
    assert d.selected_box.isHidden() and d.path_heading.text()=='所选位置'


def test_locales_and_esc_cancel_without_writes(setup_case):
    s=setup_case
    for lang in ('zh','en','ja','zh_TW'):
        i18n_engine.load_language(lang)
        for recovery in (False,True):
            path=s.root/('missing' if recovery else 'recommended')
            d=LibrarySetupDialog(s.config,path,recovery=recovery);d.show();settle(s.app)
            for failure in (False,True):
                if failure:d.show_failure(PermissionError('raw'),initialization=True);settle(s.app)
                labels=[d.title_label,d.subtitle,d.description,d.path_heading,d.start_button,d.exit_button,d.details_button]
                assert all('[MISSING:' not in label.text() for label in labels)
                assert d.start_button.geometry().right()<d.width()
                assert d.path_box.geometry().width()>400
            QTest.keyClick(d,Qt.Key_Escape);assert not d.isVisible()
            assert not path.exists()
            d.deleteLater();settle(s.app)
    i18n_engine.load_language('zh')
