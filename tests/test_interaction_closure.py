"""Receiver/source lifecycle regression; real Windows gestures remain human QA."""
import json
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from fluent_ui import visual
from PySide6.QtCore import Qt, QPoint, QPointF, QMimeData, QEvent
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDragLeaveEvent, QDropEvent, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QApplication
from fluent_ui.components.drop_contract import NODE_MIME, TAG_MIME
from services.library_index import ROOT


@pytest.fixture
def scene(tmp_path, monkeypatch):
    from services.config import ConfigService
    from services.storage import StorageService
    from services.clipboard import ClipboardService
    from services.i18n import i18n_engine
    from fluent_ui import visual
    from fluent_ui.views.gallery_view import GalleryInterface
    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv('NEKORI_APP_DATA', str(tmp_path/'app'))
    monkeypatch.setenv('NEKORI_LIBRARY', str(tmp_path/'library'))
    config = ConfigService()
    visual.theme.configure(config)
    i18n_engine.init(config)
    storage = StorageService(config=config)
    nodes = [storage.create_node(name) for name in ('Alpha', 'Beta', 'Delta', '中文', '🙂', '99')]
    children = [storage.create_node(name, nodes[0]) for name in ('Z-child', 'A-child')]
    gallery = GalleryInterface(storage, ClipboardService(config), config)
    gallery.resize(1000, 750)
    gallery.show()
    app.processEvents()
    yield app, gallery, storage, config, nodes, children
    gallery.focus_timer.stop()
    gallery.close()
    app.processEvents()


def mime_for(kind, ids):
    mime = QMimeData()
    mime.setData(kind, json.dumps(ids).encode())
    return mime


def enter(widget, point, mime):
    event = QDragEnterEvent(point, Qt.MoveAction, mime, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(widget, event)
    assert event.isAccepted(), 'source/blank admission must not require a legal drop'


def move_drop(widget, point, mime):
    move = QDragMoveEvent(point, Qt.MoveAction, mime, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(widget, move)
    assert move.isAccepted()
    drop = QDropEvent(QPointF(point), Qt.MoveAction, mime, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(widget, drop)
    assert drop.isAccepted()


def test_repeated_tree_sessions_from_source_and_after_reparent(scene):
    app, gallery, storage, config, nodes, children = scene
    tree = gallery.sidebar.tree
    source, target = nodes[1:3]
    for attempt in range(12):
        # Same payload across different source parents must get fresh ancestry.
        mime = mime_for(NODE_MIME, [source])
        enter(tree.viewport(), tree.visualItemRect(tree._find_item(source)).center(), mime)
        session = tree._drag_session
        assert session.parents[source] == storage.node(source)['parent_id']
        rect = tree.visualItemRect(tree._find_item(target))
        point = rect.center() if attempt % 2 == 0 else rect.topLeft()+QPoint(12, 2)
        move_drop(tree.viewport(), point, mime)
        assert session.committed and tree._drag_session is None
        assert not tree.feedback.isVisible() and not tree._hover_expand_timer.isActive()
        assert tree._hover_expand_item is None and not tree.scroller.timer.isActive()
        assert storage.node(source)['parent_id'] == (target if attempt % 2 == 0 else ROOT)
        assert tree._find_item(source) is not None
        # A duplicate drop without a new entry cannot commit again.
        duplicate = QDropEvent(QPointF(point), Qt.MoveAction, mime, Qt.LeftButton, Qt.NoModifier)
        tree.dropEvent(duplicate)
        assert not duplicate.isAccepted() and tree._drag_session is None
        app.processEvents()
    parent = tree._find_item(nodes[0])
    parent.setExpanded(True)
    app.processEvents()
    mime = mime_for(NODE_MIME, [children[1]])
    enter(tree.viewport(), tree.visualItemRect(tree._find_item(children[1])).center(), mime)
    move_drop(tree.viewport(), tree.visualItemRect(tree._find_item(children[0])).topLeft()+QPoint(12, 2), mime)
    assert [node['id'] for node in storage.child_nodes(nodes[0])] == children[::-1]


def test_invalid_cancel_exception_clear_legality_and_feedback(scene, monkeypatch):
    app, gallery, storage, config, nodes, children = scene
    tree = gallery.sidebar.tree
    mime = mime_for(NODE_MIME, [nodes[0]])
    tree._find_item(nodes[0]).setExpanded(True)
    app.processEvents()
    point = tree.visualItemRect(tree._find_item(children[0])).center()
    enter(tree.viewport(), point, mime)
    assert not tree._resolve_target(point, mime)[0].valid  # Cycle remains forbidden.
    tree._schedule_hover_expand(tree._find_item(nodes[0]))
    invalid = QDropEvent(QPointF(point), Qt.MoveAction, mime, Qt.LeftButton, Qt.NoModifier)
    tree.dropEvent(invalid)
    assert not invalid.isAccepted() and tree._drag_session is None
    assert tree._hover_expand_item is None
    enter(tree.viewport(), point, mime)
    QApplication.sendEvent(tree.viewport(), QDragLeaveEvent())
    assert tree._drag_session is None
    mime = mime_for(NODE_MIME, [nodes[1]])
    point = tree.visualItemRect(tree._find_item(nodes[2])).topLeft()+QPoint(10, 2)
    enter(tree.viewport(), point, mime)
    def fail(*args):
        raise RuntimeError('commit failed')
    monkeypatch.setattr(tree, '_commit_target', fail)
    with pytest.raises(RuntimeError, match='commit failed'):
        tree.dropEvent(QDropEvent(QPointF(point), Qt.MoveAction, mime, Qt.LeftButton, Qt.NoModifier))
    assert tree._drag_session is None and not tree.feedback.isVisible()
    assert not tree.scroller.timer.isActive() and not tree._hover_expand_timer.isActive()


def test_sources_use_one_drag_commit_and_keep_block(scene, monkeypatch):
    app, gallery, storage, config, nodes, children = scene
    import PySide6.QtGui as gui
    tree = gallery.sidebar.tree
    destination = {}
    class FakeDrag:
        def __init__(self, source):
            self.source = source
        def setMimeData(self, mime):
            self.mime = mime
        def setPixmap(self, pixmap):
            pass
        def setHotSpot(self, point):
            pass
        def exec(self, *args):
            widget, origin, point = destination['points']()
            enter(widget, origin, self.mime)
            move_drop(widget, point, self.mime)
            return Qt.MoveAction
    monkeypatch.setattr(gui, 'QDrag', FakeDrag)
    tree.clearSelection()
    for node in nodes[1:3]:
        tree._find_item(node).setSelected(True)
    destination['points'] = lambda: (tree.viewport(), tree.visualItemRect(tree._find_item(nodes[1])).center(), tree.visualItemRect(tree._find_item(nodes[0])).topLeft()+QPoint(10, 2))
    tree.startDrag(Qt.MoveAction)
    assert [node['id'] for node in storage.child_nodes(ROOT)][:3] == nodes[1:3]+nodes[:1]
    assert all(tree._find_item(node) is not None for node in nodes+children)
    config.set('sidebar_mode', 'categorized_icons')
    gallery.sidebar.apply_presentation()
    app.processEvents()
    canvas = gallery.sidebar.icons.canvas
    def rect(node):
        return canvas.rects[next(i for i, record in enumerate(canvas.items) if record[0] == node)]
    # The same selected block is used by Icon source, through Tree's MIME adapter.
    origin = rect(nodes[1]).center()
    canvas.mousePressEvent(QMouseEvent(QEvent.MouseButtonPress, QPointF(origin), QPointF(origin), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
    destination['points'] = lambda: (canvas, origin, rect(nodes[-1]).topLeft()+QPoint(2, 8))
    point = origin+QPoint(20, 0)
    canvas.mouseMoveEvent(QMouseEvent(QEvent.MouseMove, QPointF(point), QPointF(point), Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
    assert [node['id'] for node in storage.child_nodes(ROOT)][-3:] == nodes[1:3]+nodes[-1:]
    assert tree._drag_session is None and canvas._press is None
    for name in ('First', 'Second', 'Third'):
        gallery.tag_model.create(name)
    gallery._rebuild_tag_panel()
    flow = gallery.tag_panel.flow
    flow._set_selection(['Second', 'Third'])
    destination['points'] = lambda: (flow, flow._rects[1].center(), flow._rects[0].topLeft()+QPoint(2, 3))
    flow._start_drag()
    assert gallery.tag_model.order() == ['Second', 'Third', 'First']
    assert flow._drag_session is None and not flow._dragging


def test_projection_headers_orientation_density_no_queries(scene, monkeypatch, tmp_path):
    app, gallery, storage, config, nodes, children = scene
    from fluent_ui.components.section_index import SortProjection
    sidebar, panel = gallery.sidebar, gallery.tag_panel
    names = [storage.node(node)['name'] for node in nodes]
    for name in names:
        panel.model.create(name)
    panel.set_items(panel.model.project())
    for sort, mode in [('name_asc', SortProjection.A_Z), ('name_desc', SortProjection.Z_A)]:
        sidebar.set_display_sort(sort)
        panel.set_sort(mode)
        projection = sidebar.tree.section_projection
        assert sidebar.index_view.model.projection is projection
        assert sidebar.icons.canvas.projection is projection
        assert panel.flow.projection is panel.index_view.model.projection
        assert projection.sections == panel.flow.projection.sections
        assert set(sidebar.tree.section_headers) == set(sidebar.icons.canvas.section_headers) == set(projection.sections)
        assert [key for key, rect in panel.flow._section_headers] == projection.sections
        assert len(projection.itemsBySection['#']) == 2  # Numbers and emoji are one contiguous section.
        parent = sidebar.tree._find_item(nodes[0])
        assert [parent.child(i).data(0, Qt.UserRole) for i in range(parent.childCount())] == children
    for position in ('left', 'top', 'right', 'bottom'):
        gallery.tag_panel_host.set_placement(position)
        gallery.resize(760 if position == 'bottom' else 1000, 800)
        panel.set_items(panel.model.project())
        app.processEvents()
        horizontal = position in ('top', 'bottom')
        assert panel.index_view.orientation == (Qt.Horizontal if horizontal else Qt.Vertical)
        assert (panel.index_view.height() if horizontal else panel.index_view.width()) == visual.SECTION_INDEX_COMPACT_EXTENT
    config.set('sidebar_mode', 'categorized_icons')
    sidebar.apply_presentation()
    app.processEvents()
    canvas = sidebar.icons.canvas
    def forbidden(*args, **kwargs):
        raise AssertionError('presentation-only change queried category data')
    for method in ('child_nodes', 'node_counts', 'node'):
        monkeypatch.setattr(storage, method, forbidden)
    monkeypatch.setattr(storage.index, 'content', forbidden)
    def structure():
        return [(node_id,name,depth,group) for node_id,name,icon,depth,group in canvas.items]
    snapshot = structure()
    heights = []
    for size, labels in ((20, True), (48, True), (20, False)):
        config.set('sidebar_icon_size', size)
        config.set('sidebar_show_labels', labels)
        gallery.on_settings_changed('sidebar_icon_size')
        app.processEvents()
        heights.append(canvas.rects[-1].height())
        assert structure() == snapshot
    assert heights[1] > heights[0] > heights[2]
    wheel = QWheelEvent(QPointF(30, 40), QPointF(30, 40), QPoint(), QPoint(0, 120), Qt.NoButton, Qt.ControlModifier, Qt.NoScrollPhase, False)
    QApplication.sendEvent(sidebar.icons.viewport(), wheel)
    assert config.get('sidebar_icon_size') == 22 and structure() == snapshot
    config.set('sidebar_show_labels', True)
    sidebar.apply_presentation()
    app.processEvents()
    gallery.grab().save(str(tmp_path/'sectioned-icons-bottom.png'))


@pytest.mark.parametrize('placement', ['top', 'bottom'])
def test_cold_panel_placement_is_horizontal(tmp_path, monkeypatch, placement):
    from services.config import ConfigService
    from services.storage import StorageService
    from fluent_ui.components.tag_model import TagModel
    from fluent_ui.components.tag_panel import TagPanel
    from fluent_ui.components.panel_host import TagPanelHost
    from fluent_ui.components.section_index import SortProjection
    from PySide6.QtWidgets import QWidget
    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv('NEKORI_APP_DATA', str(tmp_path/'app'))
    monkeypatch.setenv('NEKORI_LIBRARY', str(tmp_path/'library'))
    config = ConfigService()
    config.set('tag_panel_placement', placement)
    model = TagModel(StorageService(config=config))
    panel = TagPanel(model, config)
    host = TagPanelHost(QWidget(), panel, config)
    host.resize(380, 640)  # Deliberately tall aspect ratio.
    host.show()
    for name in ('99', 'Delta', 'Sigma'):
        model.create(name)
    panel.set_items(model.project())
    panel.set_sort(SortProjection.A_Z)
    app.processEvents()
    try:
        assert panel.index_view.orientation == Qt.Horizontal
        assert panel.index_view.size().width() == 66
        assert panel.index_view.size().height() == visual.SECTION_INDEX_COMPACT_EXTENT
    finally:
        host.close()


def test_preview_same_surface_image_and_footer_in_both_modes(scene, tmp_path):
    from PySide6.QtCore import QRect
    from PySide6.QtGui import QImage, QColor
    from fluent_ui import visual
    app, gallery, storage, config, nodes, children = scene
    image = QImage(90, 240, QImage.Format_ARGB32)
    image.fill(QColor(80, 100, 140, 80))
    path = tmp_path/'portrait.png'
    image.save(str(path))
    preview = gallery.preview_popup
    identity = id(preview)
    for fixed in (False, True, False):
        preview.apply_presentation(gallery.content_pane if fixed else None)
        preview.show_preview(str(path), QPoint(100, 100), 240, 'Category', 'Tag',
                             info={'name': 'A long image name.png', 'path': str(path)},
                             container_rect=QRect(0, 0, 500, 500) if fixed else None)
        app.processEvents()
        assert id(preview) == identity
        assert preview.testAttribute(Qt.WA_StyledBackground)
        assert visual.surface_style('popover') in preview.styleSheet()
        assert preview.image_label.geometry().bottom() < preview.metadata_footer.geometry().top()
        assert preview.metadata_footer.geometry().bottom() < preview.height()
    preview.hide()
