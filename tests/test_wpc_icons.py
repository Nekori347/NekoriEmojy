"""Category pixels, independent geometry and persistent frame decisions on real widgets."""
from pathlib import Path
from time import perf_counter
from PIL import Image
from PySide6.QtCore import Qt,QSize
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from test_management_mode import management


def test_tree_pixels_and_gallery_node_sizes_are_independent(management,tmp_path):
    from services.config import ConfigService
    view,storage,parent,dest,paths,sent=management
    child=storage.create_node('Sized node',parent)
    icon=tmp_path/'icon.png';Image.new('RGB',(96,96),'red').save(icon)
    storage.set_node_icon(child,str(icon));view.sidebar._refresh_node_icon(child)
    QTest.qWait(350);view.renderer.sync()
    card=next(c for c in view._all_card_widgets if getattr(c,'node_id',None)==child)
    tree=view.sidebar.tree
    def tree_item():return next(i for i in tree.findItems('Sized node',Qt.MatchExactly|Qt.MatchRecursive,0))
    original_card_size=card._icon.size()
    for size in (14,48):
        view.config.set('sidebar_icon_size',size);view.on_settings_changed('sidebar_icon_size')
        assert tree_item().icon(0).actualSize(QSize(size,size))==QSize(size,size)
        assert tree_item().sizeHint(0).height()>=size+16
        assert card._icon.size()==original_card_size
        assert any(icon.actualSize(QSize(size,size))==QSize(size,size) for nid,name,icon,*_ in view.sidebar.icons.canvas.items if nid==child)
    tree_size=tree.iconSize()
    for size in (14,48):
        view.config.set('gallery_node_icon_size',size);view.on_settings_changed('gallery_node_icon_size')
        assert card._icon.size()==QSize(size,size) and tree.iconSize()==tree_size
        index=next(i for i,e in enumerate(view._entries) if e['id']==child)
        rect=view.renderer.index.rects[index]
        # Compact category rows preserve the requested image extent, with
        # 8 px vertical room; the former 40 px minimum is no longer the UI.
        assert card.height()==rect.height()==max(30,size+8)
        assert card.rect().contains(card.disclosure_rect())
    reloaded=ConfigService()
    assert reloaded.get('sidebar_icon_size')==48 and reloaded.get('gallery_node_icon_size')==48


def test_gif_resource_frame_snapshot_refresh_and_restart(management,tmp_path):
    from services.resource_import import ImportTarget
    from services.storage import StorageService
    from fluent_ui.components.node_card import render_node_icon
    view,storage,parent,dest,paths,sent=management
    child=storage.create_node('Animated icon',parent)
    source=tmp_path/'frames.gif'
    Image.new('RGB',(64,64),'red').save(source,save_all=True,append_images=[Image.new('RGB',(64,64),'blue')],duration=80,loop=0)
    path=storage.save_file(str(source),target=ImportTarget(parent))[0]
    storage.set_resource_metadata(path,{'thumb_frame':1})
    view._set_category_icon(path,child);QTest.qWait(350);view.renderer.sync()
    record=storage.node(child);first=record['icon']
    assert first.endswith('.png')
    assert render_node_icon(storage,record,24).toImage().pixelColor(12,12).blue()>240
    card=next(c for c in view._all_card_widgets if getattr(c,'node_id',None)==child)
    assert card._icon.toImage().pixelColor(8,8).blue()>240
    storage.set_resource_metadata(path,{'thumb_frame':0});view._set_category_icon(path,child)
    QTest.qWait(350);view.renderer.sync()
    assert storage.node(child)['icon']!=first
    assert card._icon.toImage().pixelColor(8,8).red()>240
    reopened=StorageService(config=view.config)
    assert render_node_icon(reopened,reopened.node(child),24).toImage().pixelColor(12,12).red()>240
    assert Path(path).read_bytes().startswith(b'GIF')  # source animation never rewritten


def test_local_gif_picker_cancel_and_nonfirst_frame(management,tmp_path,monkeypatch):
    from fluent_ui.components import dialogs
    from fluent_ui.views import gallery_view
    view,storage,parent,dest,paths,sent=management
    source=tmp_path/'local.gif'
    Image.new('RGB',(40,40),'red').save(source,save_all=True,append_images=[Image.new('RGB',(40,40),'blue')],duration=80,loop=0)
    monkeypatch.setattr(gallery_view.QFileDialog,'getOpenFileName',lambda *a,**k:(str(source),''))
    before=storage.node(dest)['icon']
    monkeypatch.setattr(dialogs.FramePickerDialog,'exec',lambda d:0)
    view.sidebar._set_image_icon(dest);assert storage.node(dest)['icon']==before
    def choose(dialog):
        dialog.slider.setValue(1);dialog._apply();return 1
    monkeypatch.setattr(dialogs.FramePickerDialog,'exec',choose)
    view.sidebar._set_image_icon(dest)
    image=QImage(storage.node_icon_path(dest))
    assert image.pixelColor(10,10).blue()>240


def test_category_menu_custom_leaf_branch_search_and_default(management,tmp_path,monkeypatch):
    from fluent_ui.components.category_menu import CategoryTargetMenu
    view,storage,parent,dest,paths,sent=management
    child=storage.create_node('Child',parent)
    source=tmp_path/'custom.png';Image.new('RGB',(64,64),'blue').save(source)
    storage.set_node_icon(parent,str(source));storage.set_node_icon(child,str(source))
    chosen=[];start=perf_counter();menu=CategoryTargetMenu('加入分类',storage,chosen.append,view);menu.prepare()
    branch=next(m for m in menu._subMenus if m.node==parent)
    assert branch.icon().pixmap(16,16).toImage().pixelColor(8,8).blue()>240
    # Submenu preparation shares the same metadata snapshot, with no per-node SQL.
    def no_read(*a,**k):raise AssertionError('submenu re-read category catalog')
    monkeypatch.setattr(storage.index,'nodes',no_read)
    branch.prepare();action=next(a for a in branch.actions() if a.data()==child)
    assert action.icon().pixmap(16,16).toImage().pixelColor(8,8).blue()>240
    action.trigger();assert chosen==[child]
    menu._populate('Child');found=next(a for a in menu.actions() if a.data()==child)
    assert found.icon().pixmap(16,16).toImage().pixelColor(8,8).blue()>240
    assert perf_counter()-start<2  # coarse stall guard, not a microbenchmark
    menu.close();menu.deleteLater()


def test_settings_row_preview_discard_and_save(management):
    from fluent_ui.views.settings_center import SettingsCenter
    view,storage,parent,dest,paths,sent=management
    center=SettingsCenter(view.config,storage)
    center.settings_changed.connect(view.on_settings_changed)
    center._select_page(1);center._show_tab(1)
    row=center._rows['gallery_node_icon_size'][0]
    row.spin.setValue(38)
    assert center.pending['gallery_node_icon_size']==38
    center.discard()
    assert view.config.get('gallery_node_icon_size')==22
    row.spin.setValue(32);assert center.save()
    assert view.config.get('gallery_node_icon_size')==32
    center.hide();center.deleteLater()
