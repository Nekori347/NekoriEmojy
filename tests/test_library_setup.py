"""First-use/recovery boundaries, using only disposable libraries and Qt input."""
import json,sqlite3,hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from PySide6.QtWidgets import QApplication,QFileDialog,QDialog
from services.config import ConfigService
from services.library_setup import identify_library,check_target,commit_library,startup_location,LibraryLocationError
from services.library_index import LibraryIndex,ROOT
from fluent_ui.components.library_setup import LibrarySetupDialog
from services.i18n import i18n_engine
from fluent_ui import visual
from test_phase2_interaction import surface,settle


@pytest.fixture
def setup_case(tmp_path,monkeypatch):
    app=QApplication.instance() or QApplication([])
    monkeypatch.setenv('NEKORI_APP_DATA',str(tmp_path/'app'))
    monkeypatch.delenv('NEKORI_LIBRARY',raising=False)
    monkeypatch.setattr('services.app_paths.default_library_dir',lambda:tmp_path/'recommended')
    config=ConfigService(defer_create=True);i18n_engine.init(config);visual.theme.configure(config)
    yield SimpleNamespace(root=tmp_path,app=app,config=config)
    for window in app.topLevelWidgets():
        if isinstance(window,LibrarySetupDialog):window.reject();window.deleteLater()
    app.processEvents()


def tree_bytes(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}


def test_fresh_cancel_and_reopen_do_not_create_files(setup_case):
    s=setup_case;path,ui,recovery=startup_location(s.config)
    assert ui and not recovery and not path.exists() and not Path(s.config.config_path).exists()
    d=LibrarySetupDialog(s.config,path);d.reject()
    assert not path.exists() and not Path(s.config.config_path).exists()
    assert startup_location(ConfigService(defer_create=True))==(path,True,False)


@pytest.mark.parametrize('custom',[False,True])
def test_confirm_then_restart_empty_library_is_not_first_use(setup_case,custom):
    s=setup_case;path=s.root/'中文 空格 表情库' if custom else startup_location(s.config)[0]
    d=LibrarySetupDialog(s.config,path);d.begin()
    assert d.result()==QDialog.DialogCode.Accepted and d.storage is not None
    assert Path(s.config.config_path).is_file() and (path/'index.sqlite3').is_file()
    loaded=ConfigService(defer_create=True)
    assert startup_location(loaded)==(path.resolve(),False,False)
    assert not d.storage.index.resources()


def test_recovery_preserves_original_and_rejects_ordinary_folder(setup_case,monkeypatch):
    s=setup_case;original=s.root/'old-missing';s.config.set('library_path',str(original))
    loaded=ConfigService(defer_create=True);path,ui,recovery=startup_location(loaded)
    assert ui and recovery
    before=Path(loaded.config_path).read_bytes();ordinary=s.root/'pictures';ordinary.mkdir();(ordinary/'a.png').write_bytes(b'original')
    d=LibrarySetupDialog(loaded,path,recovery=True)
    assert not d.start_button.isEnabled()
    monkeypatch.setattr(QFileDialog,'getExistingDirectory',lambda *a:str(ordinary));d.choose('connect')
    assert not d.start_button.isEnabled() and not d.error_label.isHidden()
    assert not (ordinary/'index.sqlite3').exists() and Path(loaded.config_path).read_bytes()==before
    replacement=s.root/'relocated';LibraryIndex(replacement)
    monkeypatch.setattr(QFileDialog,'getExistingDirectory',lambda *a:str(replacement));d.choose('connect');d.begin()
    assert d.result()==QDialog.DialogCode.Accepted and d.storage.library_root==str(replacement.resolve())
    assert not original.exists()


@pytest.mark.parametrize('failure',['config','storage'])
def test_failed_start_rolls_back_only_new_files_and_allows_retry(setup_case,monkeypatch,failure):
    s=setup_case;path=s.root/'chosen';path.mkdir();original=dict(s.config.config)
    d=LibrarySetupDialog(s.config,path)
    with monkeypatch.context() as fault:
        if failure=='config':fault.setattr(s.config,'_save_config',Mock(side_effect=RuntimeError('disk denied')))
        else:fault.setattr('services.storage.StorageService',Mock(side_effect=PermissionError('disk denied')))
        d.begin()
    assert d.result()!=QDialog.DialogCode.Accepted and d.storage is None and d.start_button.isEnabled()
    assert s.config.config==original and list(path.iterdir())==[] and not Path(s.config.config_path).exists()
    d.begin();assert d.result()==QDialog.DialogCode.Accepted


def test_nonempty_create_rejected_without_modifying_original_files(setup_case):
    s=setup_case;folder=s.root/'ordinary';folder.mkdir();(folder/'keep.txt').write_text('user data')
    before=tree_bytes(folder)
    for mode in ('create','connect'):
        with pytest.raises(LibraryLocationError):check_target(folder,mode)
    assert tree_bytes(folder)==before
    d=LibrarySetupDialog(s.config,folder);d.begin()
    assert d.result()!=QDialog.DialogCode.Accepted and tree_bytes(folder)==before


def test_existing_and_wal_validation_is_read_only_and_reconnect_preserves_data(setup_case):
    s=setup_case;folder=s.root/'existing';index=LibraryIndex(folder)
    from PIL import Image
    (folder/'images').mkdir();Image.new('RGB',(8,8),'green').save(folder/'images/x.png')
    category=index.create_node('保留分类')
    with index.connect() as db:
        db.execute("INSERT INTO resources(id,filename,relative_path,display_name,tags,ocr_text,ocr_state_json,library_added_seq) VALUES ('one','x.png','images/x.png','例','tag','放棄','{\"manual\":true}',1)")
        db.execute("INSERT INTO recent VALUES ('one',100)")
        db.execute('INSERT INTO content(parent_id,resource_id,position) VALUES (?,?,?)',(category,'one',0))
    db=sqlite3.connect(index.path);db.execute('PRAGMA journal_mode=WAL');db.execute("UPDATE resources SET ocr_text='保留文字' WHERE id='one'");db.commit()
    try:
        before=tree_bytes(folder);assert identify_library(folder)=='catalog';assert tree_bytes(folder)==before
    finally:db.close()
    def catalog(value):
        with value.connect(search=False) as db:
            return {table:[tuple(row) for row in db.execute('SELECT * FROM '+table+' ORDER BY 1,2')]
                    for table in ('resources','nodes','content','recent')}
    records=catalog(index)
    storage=commit_library(s.config,folder,'connect')
    assert storage.index.resource_by_id('one')['ocr_text']=='保留文字'
    assert catalog(storage.index)==records
    with storage.index.connect() as db:assert db.execute('SELECT count(*) FROM recent').fetchone()[0]==1
    import shutil
    moved=s.root/'移动后的 中文 空格库';shutil.copytree(folder,moved)
    reconnected=commit_library(s.config,moved,'connect')
    assert catalog(reconnected.index)==records and reconnected.get_recent_images()==[str((moved/'images/x.png').resolve()).lower()]


def test_old_catalog_and_internal_adoption_formats_are_still_supported(setup_case):
    s=setup_case;old=s.root/'v1';old.mkdir()
    with sqlite3.connect(old/'index.sqlite3') as db:
        db.executescript("PRAGMA user_version=1; CREATE TABLE resources(id TEXT PRIMARY KEY, filename TEXT UNIQUE,relative_path TEXT UNIQUE,display_name TEXT,tags TEXT DEFAULT '',ocr_text TEXT DEFAULT '',metadata_json TEXT DEFAULT '{}',status TEXT DEFAULT 'normal',created_at TEXT);")
    before=tree_bytes(old);assert identify_library(old)=='catalog' and tree_bytes(old)==before
    commit_library(s.config,old,'connect')
    legacy=s.root/'internal';(legacy/'images').mkdir(parents=True)
    for name,value in [('categories',{'旧分类':['missing.png']}),('order',['missing.png']),('metadata',{'missing.png':'旧标签'})]:
        (legacy/(name+'.json')).write_text(json.dumps(value),'utf-8')
    before=tree_bytes(legacy);assert identify_library(legacy)=='legacy' and tree_bytes(legacy)==before
    storage=commit_library(s.config,legacy,'connect')
    assert storage.index.resource('missing.png')['tags']=='旧标签'


def test_settings_selection_discard_and_save_use_same_safety_rules(surface,monkeypatch):
    from fluent_ui.views.settings_center import SettingsCenter
    s=surface;monkeypatch.delenv('NEKORI_LIBRARY');c=SettingsCenter(s.config,s.storage)
    c._select_page(3);c._show_tab(0);c.show_error=Mock();c.show_success=Mock()
    path=s.tmp/'new-location';path.mkdir()
    monkeypatch.setattr(QFileDialog,'getExistingDirectory',lambda *a:str(path))
    before=Path(s.config.config_path).read_bytes();c._choose_library('create')
    assert not list(path.iterdir()) and c.pending['library_path']==str(path)
    c.discard();assert not list(path.iterdir()) and Path(s.config.config_path).read_bytes()==before
    c._choose_library('create')
    with monkeypatch.context() as fault:
        fault.setattr(s.config,'_save_config',Mock(side_effect=RuntimeError('denied')))
        assert not c.save()
    assert not list(path.iterdir()) and Path(s.config.config_path).read_bytes()==before
    assert c.save() and (path/'index.sqlite3').exists()
    c.close();c.deleteLater();settle(s.app)


def test_empty_library_import_uses_existing_picker(setup_case,monkeypatch):
    from services.clipboard import ClipboardService
    from fluent_ui.views.gallery_view import GalleryInterface
    s=setup_case;storage=commit_library(s.config,s.root/'empty','create')
    g=GalleryInterface(storage,ClipboardService(s.config),s.config);g.resize(1000,740);g.show()
    settle(s.app)
    try:
        assert g.placeholder.isVisible() and g.empty_import_button.isVisible()
        picker=Mock();monkeypatch.setattr(g,'_pick_import_files',picker)
        g.empty_import_button.click();picker.assert_called_once_with()
    finally:
        g.imports.shutdown();g.ocr.close();g.close();g.deleteLater();settle(s.app)


def test_corrupt_config_recovers_without_replacing_it_on_cancel(setup_case):
    s=setup_case;path=Path(s.config.config_path);path.parent.mkdir();path.write_bytes(b'{broken')
    loaded=ConfigService(defer_create=True);root,ui,recovery=startup_location(loaded)
    assert ui and recovery and loaded.load_error
    LibrarySetupDialog(loaded,root,recovery=True).reject()
    assert path.read_bytes()==b'{broken' and not root.exists()


def test_recommended_existing_library_connects_and_keeps_identity(setup_case):
    s=setup_case;folder=startup_location(s.config)[0];index=LibraryIndex(folder)
    with index.connect() as db:identity=db.execute("SELECT value FROM library_meta WHERE key='library_id'").fetchone()[0]
    assert startup_location(s.config)==(folder,True,False)
    d=LibrarySetupDialog(s.config,folder);d.begin()
    assert d.result()==QDialog.DialogCode.Accepted
    with d.storage.index.connect() as db:assert db.execute("SELECT value FROM library_meta WHERE key='library_id'").fetchone()[0]==identity


def test_legacy_database_adoption_failure_keeps_original_data(setup_case,monkeypatch):
    s=setup_case;root=s.root/'legacy-db';(root/'images').mkdir(parents=True)
    for name,sql in [('order','CREATE TABLE item_orders(image_path TEXT,sort_order INTEGER)'),
                     ('categories','CREATE TABLE categories(id INTEGER,name TEXT,sort_order INTEGER,icon_path TEXT); CREATE TABLE category_images(category_name TEXT,image_path TEXT)'),
                     ('metadata','CREATE TABLE image_metadata(image_path TEXT,keywords TEXT)')]:
        with sqlite3.connect(root/(name+'.db')) as db:db.executescript(sql)
    before=tree_bytes(root);assert identify_library(root)=='legacy' and tree_bytes(root)==before
    with monkeypatch.context() as fault:
        fault.setattr(s.config,'_save_config',Mock(side_effect=RuntimeError('denied')))
        with pytest.raises(RuntimeError):commit_library(s.config,root,'connect')
    assert tree_bytes(root)==before and (root/'images').is_dir()
    storage=commit_library(s.config,root,'connect')
    assert storage.index.path.exists()
