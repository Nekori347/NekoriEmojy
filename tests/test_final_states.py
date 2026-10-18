"""Mouse versus keyboard focus and the real settings save contract."""
from PySide6.QtCore import Qt,QEvent,QPoint
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from test_phase2_interaction import surface,settle
from test_l1_l3_interaction import settings


def accent_pixels(widget):
    from fluent_ui import visual
    image=widget.grab().toImage();accent=QColor(visual.accent())
    return sum(image.pixelColor(x,y)==accent for y in range(image.height()) for x in range(image.width()))


def test_command_focus_is_visible_for_keyboard_but_not_restored_mouse_focus(surface):
    g=surface.g;b=g.btn_settings;g.activateWindow();settle(surface.app)
    b.setFocus(Qt.OtherFocusReason);settle(surface.app)
    assert b.hasFocus()
    assert accent_pixels(b)==0
    g.search_box.setFocus();QTest.keyClick(g.search_box,Qt.Key_Tab)
    b.setFocus(Qt.TabFocusReason);settle(surface.app)
    assert accent_pixels(b)>0
    # Clicking an unfocusable surface keeps the Qt focus object but must end
    # the keyboard-visible ring; do not clear the actual focus globally.
    QTest.mouseClick(g.workspace,Qt.LeftButton,pos=QPoint(2,2));settle(surface.app)
    assert b.hasFocus() and accent_pixels(b)==0
    QTest.keyClick(b,Qt.Key_Tab);b.setFocus(Qt.TabFocusReason);settle(surface.app)
    assert accent_pixels(b)>0


def test_recent_limit_is_unique_visible_and_pending_until_saved(settings):
    c=settings;c._select_page(3);c._show_tab(0);settle(QApplication.instance())
    row=c._rows['recent_limit'][0];old=c.config.get('recent_limit',30)
    assert row.isVisible()
    assert row.hint_label.text()=='设置最近使用记录中显示的表情数量。\n主面板与快速面板共用此设置。'
    row.set_value(old+1);row.changed.emit()
    assert c.pending['recent_limit']==old+1 and c.config.get('recent_limit')==old
    c.discard();assert row.value()==old
    row.set_value(old+2);row.changed.emit();assert c.save()
    assert c.config.get('recent_limit')==old+2
    c._select_page(1);c._show_tab(2)
    assert 'recent_limit' not in c._rows


def test_category_marker_follows_real_children_not_depth(surface):
    s=surface;g=s.g;s.config.set('sidebar_mode','categorized_icons');g.sidebar.apply_presentation()
    from fluent_ui import visual
    accent=QColor(visual.accent())
    def marker(node):
        g.sidebar.tree.select_node(node);g.sidebar.icons.refresh();settle(s.app)
        canvas=g.sidebar.icons.canvas;i=next(i for i,item in enumerate(canvas.items) if item[0]==node)
        rect=canvas.group_by_index.get(i,canvas.rects[i]);image=canvas.grab().toImage()
        rows=[y for y in range(rect.top(),rect.bottom()+1) if any(image.pixelColor(x,y)==accent for x in range(rect.left()+5,rect.right()-4))]
        assert rows
        return min(rows)-rect.top(),max(rows)-rect.top(),rect.height()
    first,last,height=marker(s.other);assert first>height-10  # root-level leaf
    s.storage.create_node('New child',s.other);g.sidebar.refresh_list(s.other)
    first,last,height=marker(s.other);assert last<10  # same depth, now a parent
    first,last,height=marker(s.child);assert first>height-10  # nested leaf
