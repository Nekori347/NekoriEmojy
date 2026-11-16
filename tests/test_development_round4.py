"""Icon drawer projection and decoration; disposable Library, no desktop input."""
from PySide6.QtCore import Qt,QPoint
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from test_phase2_interaction import surface
from fluent_ui import visual


def canvas_for(s):
    s.g.sidebar.set_presentation('categorized_icons')
    s.g.sidebar.icons.refresh();s.app.processEvents()
    return s.g.sidebar.icons.canvas


def test_selected_group_line_survives_header_hover(surface):
    s=surface;c=canvas_for(s)
    index=next(i for i,item in enumerate(c.items) if item[0]==s.parent)
    c._select({s.parent});QTest.mouseMove(c,c.rects[index].center())
    image=c.grab().toImage();rect=c.group_by_index[index]
    expected=QColor(visual.colors()['accent'])
    assert image.pixelColor(rect.center().x(),rect.top()+5)==expected


def test_drawer_hides_descendants_without_changing_selection_or_tree(surface):
    s=surface;grandchild=s.storage.create_node('Nested',s.child)
    s.g.sidebar.refresh_list(s.parent);c=canvas_for(s)
    index=next(i for i,item in enumerate(c.items) if item[0]==s.parent)
    descendants=[i for i,item in enumerate(c.items) if item[0] in (s.child,grandchild)]
    before_height=c.minimumHeight();tree_expanded=s.g.sidebar.tree._expanded_ids()
    content=s.storage.index.content(s.parent);selected=s.g.current_node
    QTest.mouseClick(c,Qt.LeftButton,pos=c.disclosure_rect(index).center())
    assert s.parent in c.collapsed
    assert c.minimumHeight()<before_height
    assert all(c.rects[i].isEmpty() for i in descendants)
    assert all(i not in c.visible_indices for i in descendants)
    assert s.g.current_node==selected and s.g.sidebar.tree._expanded_ids()==tree_expanded
    assert s.storage.index.content(s.parent)==content
    assert c.group_by_index[index].width()==c.width()-8
    # Refresh and a new projection do not discard the independent ID state.
    s.g.sidebar.icons.refresh();assert s.parent in c.collapsed
    QTest.mouseClick(c,Qt.LeftButton,pos=c.disclosure_rect(index).center())
    assert all(not c.rects[i].isEmpty() for i in descendants)
    assert s.storage.index.content(s.parent)==content


def test_drawer_state_survives_sort_mode_refresh_and_restart(surface):
    import json,subprocess,sys
    s=surface;c=canvas_for(s)
    index=next(i for i,item in enumerate(c.items) if item[0]==s.parent)
    QTest.mouseClick(c,Qt.LeftButton,pos=c.disclosure_rect(index).center())
    s.g.save_session_state()
    state=s.config.get('library_view_states')[s.g._view_state_key]
    assert s.parent in state['sidebar_icons_collapsed']
    for mode in ('name_asc','name_desc','manual'):
        s.g.sidebar.set_display_sort(mode)
        assert s.parent in c.collapsed
        assert c.rects[next(i for i,item in enumerate(c.items) if item[0]==s.child)].isEmpty()
    s.g.sidebar.set_presentation('tree');s.g.sidebar.set_presentation('categorized_icons')
    assert s.parent in c.collapsed
    # Real process restart reads the existing per-Library view state.
    code='''import json
from PySide6.QtWidgets import QApplication
from services.config import ConfigService
from services.storage import StorageService
from services.clipboard import ClipboardService
from services.i18n import i18n_engine
from fluent_ui import visual
from fluent_ui.views.gallery_view import GalleryInterface
app=QApplication([]);config=ConfigService();visual.theme.configure(config);i18n_engine.init(config)
storage=StorageService(config=config);g=GalleryInterface(storage,ClipboardService(config),config)
print('COLLAPSED='+json.dumps(sorted(g.sidebar.icons.canvas.collapsed)))
g.imports.shutdown();g.ocr.close()
'''
    result=subprocess.run([sys.executable,'-B','-c',code],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30)
    assert result.returncode==0,result.stderr[-1200:]
    restored=json.loads(next(line[10:] for line in result.stdout.splitlines() if line.startswith('COLLAPSED=')))
    assert s.parent in restored
    # A node temporarily without children keeps its ID preference for when
    # children return; only deleted identities are pruned by refresh.
    s.storage.move_node(s.child,s.other);s.g.sidebar.refresh_list(s.parent)
    assert s.parent in c.collapsed
    s.storage.move_node(s.child,s.parent);s.g.sidebar.refresh_list(s.parent)
    assert s.parent in c.collapsed and c.rects[next(i for i,item in enumerate(c.items) if item[0]==s.child)].isEmpty()


def test_title_navigation_nested_state_and_drop_projection(surface):
    from PySide6.QtCore import QMimeData,QUrl
    from services.library_index import ROOT
    s=surface;grandchild=s.storage.create_node('Grandchild',s.child)
    tail=s.storage.create_node('Last hidden child',s.other)
    s.g.sidebar.refresh_list(s.parent);c=canvas_for(s)
    def index(node):return next(i for i,item in enumerate(c.items) if item[0]==node)
    original=list(c.items);positions=s.storage.index.content(s.parent)
    QTest.mouseClick(c,Qt.LeftButton,pos=c.disclosure_rect(index(s.child)).center())
    QTest.mouseClick(c,Qt.LeftButton,pos=c.disclosure_rect(index(s.parent)).center())
    assert s.g.current_node==s.parent and c.rects[index(grandchild)].isEmpty()
    other=c.rects[index(s.other)]
    QTest.mouseClick(c,Qt.LeftButton,pos=QPoint(other.left()+24,other.center().y()))
    assert s.g.current_node==s.other and s.parent in c.collapsed
    # Title remains navigation, not disclosure. Hidden rects cannot be hit.
    rect=c.rects[index(s.parent)]
    QTest.mouseClick(c,Qt.LeftButton,pos=QPoint(rect.left()+24,rect.center().y()))
    assert s.parent in c.collapsed and s.g.current_node==s.parent
    assert c.disclosure_rect(index(s.child)).isEmpty()
    mime=QMimeData();mime.setUrls([QUrl.fromLocalFile(s.paths[0])])
    target,_=c.resolve(rect.center(),mime)
    assert target.valid and target.container_id==s.parent
    assert all(c.index_at(c.rects[i].center())==i for i in c.visible_indices)
    QTest.mouseClick(c,Qt.LeftButton,pos=c.disclosure_rect(index(s.parent)).center())
    assert s.child in c.collapsed and c.rects[index(grandchild)].isEmpty()
    QTest.mouseClick(c,Qt.LeftButton,pos=c.disclosure_rect(index(s.child)).center())
    assert not c.rects[index(grandchild)].isEmpty()
    assert [item[0] for item in c.items]==[item[0] for item in original]
    assert s.storage.index.content(s.parent)==positions
    QTest.mouseClick(c,Qt.LeftButton,pos=c.disclosure_rect(index(s.other)).center())
    assert c.rects[index(tail)].isEmpty()
    target,_=c.resolve(QPoint(12,c.minimumHeight()-2),mime)
    assert target.valid and target.container_id==ROOT


def test_whole_group_hover_and_menu_target_preserve_line_in_both_palettes(surface,monkeypatch):
    from PySide6.QtGui import QContextMenuEvent
    s=surface;c=canvas_for(s)
    index=next(i for i,item in enumerate(c.items) if item[0]==s.parent)
    c._select({s.parent});group=c.group_by_index[index];palette=visual.colors
    for dark in (False,True):
        with monkeypatch.context() as patch:
            patch.setattr(visual,'colors',lambda:palette(dark))
            c._update_hover(None);normal=c.grab().toImage()
            # Padding between children is still inside the whole card.
            pos=QPoint(group.right()-2,group.center().y())
            QTest.mouseMove(c,pos);hover=c.grab().toImage()
            assert c._hovered_group==index
            assert hover.pixelColor(group.left()+8,group.center().y())!=normal.pixelColor(group.left()+8,group.center().y())
            assert hover.pixelColor(group.center().x(),group.top()+5)==QColor(palette(dark)['accent'])
            child=next(i for i,item in enumerate(c.items) if item[0]==s.child)
            QTest.mouseMove(c,c.rects[child].center())
            assert c.grab().toImage().pixelColor(group.center().x(),group.top()+5)==QColor(palette(dark)['accent'])
    # Exercise the real context resolution without opening a blocking menu.
    s.g.sidebar.tree.node_menu_requested.disconnect()
    requests=[];s.g.sidebar.tree.node_menu_requested.connect(lambda *args:requests.append(args))
    pos=c.rects[index].center()
    c.contextMenuEvent(QContextMenuEvent(QContextMenuEvent.Mouse,pos,c.mapToGlobal(pos)))
    assert requests[0][0]==s.parent
