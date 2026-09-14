import json
from pathlib import Path
import pytest
from PIL import Image
from services.library import create_library,open_library,copy_library,read_db,LibraryError
from services.config import ConfigService
from services.storage import StorageService
from services.category_groups import CategoryGroups


def fixture(tmp_path):
    context=create_library(tmp_path/'library')
    store=StorageService(context)
    source=tmp_path/'source.png';Image.new('RGBA',(20,20),'red').save(source)
    path=store.save_file(source,target_category='大分类')[0]
    return context,store,path


def test_preferences_preview_save_cancel_and_runtime_state(tmp_path):
    context,store,path=fixture(tmp_path);config=ConfigService(context)
    config.begin_preview();config.set('left_search',True);config.set('sidebar_is_grid_mode',True)
    config.set('window_geometry',[10,20,800,700])
    assert config.preview_dirty and config.get('left_search')
    assert not ConfigService(context).get('left_search')
    config.cancel_preview()
    assert not config.get('left_search') and config.get('window_geometry')==[10,20,800,700]
    config.begin_preview();config.set('left_filter',True);config.save_preview()
    assert ConfigService(context).get('left_filter') and not config.preview_dirty
    config.set('left_filter',False);config.cancel_preview()
    assert config.get('left_filter')
    assert store.get_all_images()==[path]


def test_preference_import_validation_and_defaults_do_not_touch_library(tmp_path):
    context,store,path=fixture(tmp_path);config=ConfigService(context)
    config.set('private_token','do-not-export')
    config.set('runtime_icon',Path(path).name)
    config.begin_preview();config.set('left_search',True)
    exported=tmp_path/'prefs.json';config.export_preferences(exported)
    text=exported.read_text(encoding='utf-8')
    assert 'do-not-export' not in text and str(context.root) not in text and Path(path).name not in text
    invalid=json.loads(text);invalid['preferences']['library_root']='D:/unrelated'
    exported.write_text(json.dumps(invalid),encoding='utf-8')
    with pytest.raises(LibraryError):config.import_preferences_preview(exported)
    assert config.get('left_search') and config.preview_dirty
    config.restore_defaults_preview()
    assert not config.get('left_search') and config.get('runtime_icon')==''
    config.cancel_preview()
    assert config.get('runtime_icon')==Path(path).name and store.get_all_images()==[path]


def test_valid_import_is_preview_until_saved(tmp_path):
    context,store,path=fixture(tmp_path);first=ConfigService(context)
    first.set('left_search',True);first.set('show_category_names',False)
    export=tmp_path/'preferences.json';first.export_preferences(export)
    other=create_library(tmp_path/'other');second=ConfigService(other)
    second.import_preferences_preview(export)
    assert second.get('left_search') and not ConfigService(other).get('left_search')
    second.save_preview()
    assert ConfigService(other).get('left_search') and not ConfigService(other).get('show_category_names')
    assert second.context.root==other.root


def test_flat_groups_share_one_asset_and_survive_category_reordering(tmp_path):
    context,store,path=fixture(tmp_path);groups=CategoryGroups(context)
    one=groups.create('大分类','一号');two=groups.create('大分类','二号')
    assert groups.add(one,[path,path])==1 and groups.add(two,[path])==1
    groups.set_collapsed(one,True)
    store.add_category('另一分类');store.add_images_to_category([path],'另一分类')
    store.save_categories(dict(reversed(list(store.get_all_categories().items()))))
    rows=groups.list('大分类')
    assert rows[0]['collapsed'] and all(r['paths']==[str(Path(path).resolve())] for r in rows)
    assert len(list(context.images_dir.iterdir()))==1
    groups.delete(one)
    assert store.get_images_by_category('大分类')==[path] and Path(path).exists()
    assert groups.list('大分类')[0]['id']==two


def test_group_parent_rename_member_remove_and_delete_are_consistent(tmp_path):
    context,store,path=fixture(tmp_path);groups=CategoryGroups(context)
    group=groups.create('大分类','子组');groups.add(group,[path])
    assert store.rename_category('大分类','新名称')
    assert groups.list('新名称')[0]['id']==group and groups.list('大分类')==[]
    store.remove_image_from_category(path,'新名称')
    assert groups.list('新名称')[0]['paths']==[] and Path(path).exists()
    groups.add(group,[path]);store.remove_category('新名称')
    assert groups.list('新名称')==[] and Path(path).exists()
    with read_db(context.db('categories')) as conn:
        assert conn.execute('SELECT COUNT(*) FROM group_images').fetchone()[0]==0


def test_group_order_collapse_copy_and_reconnect(tmp_path):
    context,store,path=fixture(tmp_path);groups=CategoryGroups(context)
    one=groups.create('大分类','一号');two=groups.create('大分类','二号')
    groups.add(one,[path]);groups.set_collapsed(one,True);groups.reorder('大分类',[two,one])
    session=open_library(context.root)
    copied=copy_library(session,tmp_path/'copied');session.close()
    new_session=open_library(copied.root);rows=CategoryGroups(new_session).list('大分类')
    assert [r['id'] for r in rows]==[two,one] and rows[1]['collapsed']
    assert Path(rows[1]['paths'][0]).is_relative_to(copied.root)
    assert Path(rows[1]['paths'][0]).read_bytes()==Path(path).read_bytes()
    new_session.close()


def test_group_rejects_cross_library_resource_and_name_conflict(tmp_path):
    context,store,path=fixture(tmp_path);groups=CategoryGroups(context)
    group=groups.create('大分类','子组')
    with pytest.raises(LibraryError):groups.create('大分类',' 子组 ')
    with pytest.raises(LibraryError):groups.add(group,[tmp_path/'outside.png'])
    assert groups.list('大分类')[0]['paths']==[]


def test_export_cannot_overwrite_library_files(tmp_path):
    context, store, path = fixture(tmp_path)
    config = ConfigService(context)
    for target in (context.root / 'nekori-library.json', context.data_dir / 'library.db', Path(path)):
        original = target.read_bytes()
        with pytest.raises(LibraryError):
            config.export_preferences(target)
        assert target.read_bytes() == original


def test_startup_save_failure_restores_registry_and_keeps_preview(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from fluent_ui.settings_window import SettingsWindow
    from services import windows_startup
    context, store, path = fixture(tmp_path)
    config = ConfigService(context)
    config.begin_preview()
    config.set('start_with_windows', True)
    calls = []
    monkeypatch.setattr(windows_startup, 'read_startup', lambda: ('old entry', 1))
    monkeypatch.setattr(windows_startup, 'apply_startup', lambda *args: calls.append(('apply', args[0])))
    monkeypatch.setattr(windows_startup, 'restore_startup', lambda value: calls.append(('restore', value)))
    monkeypatch.setattr(config, '_save_config', lambda value: (_ for _ in ()).throw(OSError('simulated disk failure')))
    monkeypatch.setattr('fluent_ui.settings_window.QMessageBox.warning', lambda *args: None)
    window = SimpleNamespace(config=config)
    SettingsWindow.save(window)
    assert calls == [('apply', True), ('restore', ('old entry', 1))]
    assert config.preview_dirty and not ConfigService(context).get('start_with_windows')


def test_startup_command_handles_spaces_and_requires_executable(tmp_path):
    from services.windows_startup import startup_command
    context, store, path = fixture(tmp_path)
    executable = tmp_path / 'application folder' / 'NekoriEmojy.exe'
    with pytest.raises(LibraryError):
        startup_command(context, executable)
    executable.parent.mkdir()
    executable.write_bytes(b'test fixture, never executed')
    from types import SimpleNamespace
    short_library = SimpleNamespace(root=Path('D:/library'))
    command = startup_command(short_library, executable)
    assert command.startswith('"') and '--library' in command and str(short_library.root) in command


def test_group_listing_is_metadata_only_and_rejects_bad_reference(tmp_path, monkeypatch):
    context, store, path = fixture(tmp_path)
    groups = CategoryGroups(context)
    group = groups.create('大分类', '一号')
    groups.add(group, [path])
    monkeypatch.setattr(type(context), 'resource', lambda *args: (_ for _ in ()).throw(AssertionError('disk path resolution')))
    assert len(groups.list('大分类')[0]['paths']) == 1
    with context.transaction() as conn:
        conn.execute('UPDATE categories.group_images SET image_path=?', ('../outside.png',))
    with pytest.raises(LibraryError):
        groups.list('大分类')


def test_explicit_perceptual_maintenance_keeps_assets_and_groups(tmp_path):
    from services.maintenance import similar_report
    context, store, path = fixture(tmp_path)
    second = tmp_path / 'another.png'
    Image.new('RGBA', (20, 20), 'blue').save(second)
    another = store.save_file(second, target_category='大分类')[0]
    group = CategoryGroups(context).create('大分类', '保留')
    CategoryGroups(context).add(group, [path, another])
    before = {name: Path(name).read_bytes() for name in (path, another)}
    report = similar_report(context)
    assert report['kind'] == 'similar' and report['duplicates'] and report['failed'] == 0
    assert all(Path(name).read_bytes() == value for name, value in before.items())
    assert len(CategoryGroups(context).list('大分类')[0]['paths']) == 2
    with read_db(context.db('features')) as conn:
        assert conn.execute('SELECT COUNT(*) FROM image_features WHERE phash IS NOT NULL').fetchone()[0] == 2
