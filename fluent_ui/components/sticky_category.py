"""One viewport presentation of the existing mixed-flow category row."""
from bisect import bisect_right
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QLinearGradient
from fluent_ui.components.node_card import NodeCard
from fluent_ui.components.gallery_model import occurrence_id
from fluent_ui.visual import colors


class StickyCategory(NodeCard):
    def __init__(self, gallery):
        super().__init__({'id':'', 'name':''}, gallery.storage,
                         parent=gallery.scroll_area.viewport())
        self.gallery=gallery
        self._signature=None
        self.setFocusPolicy(Qt.NoFocus)
        self.hide()
        self.clicked.connect(lambda _id,mods:gallery._entry_clicked(self.content_entry,mods))
        self.activated.connect(gallery.set_node)
        self.disclosure_toggled.connect(self._toggle)
        self.context_requested.connect(gallery.show_node_context_menu)

    def sync(self):
        g=self.gallery;index=g.renderer.index
        visible=g.available_gallery_rect()
        top=g.scroll_area.verticalScrollBar().value()+visible.top()
        if (not index.tops or getattr(g,'_gallery_drag_session',None) or
                (hasattr(g,'drop_cancel_zone') and g.drop_cancel_zone.isVisible())):
            self.hide();return
        row=bisect_right(index.tops,top)-1
        owner=index.section_owners[row] if row>=0 else None
        if owner is None or top>index.bottoms[-1]:
            self.hide();return
        entry=g._entries[owner];rect=index.rects[owner]
        if rect.top()>=top or entry['id'] not in g._expanded_nodes:
            self.hide();return
        signature=(entry,index.node_icon_size,entry['id'] in g._expanded_nodes)
        rebound=self._signature!=signature
        if rebound:
            self.reset_interaction()
            self.entry=self.content_entry=entry;self.node_id=entry['id']
            self.refresh_icon();self.set_expanded(True)
            self._motion.stop();self._angle=90.0
            self.setToolTip(' / '.join(n['name'] for n in g.storage.node_path(self.node_id)))
            self._signature=(dict(entry),index.node_icon_size,True)
        self.set_selected(g._entry_key(entry) in g.selected_keys)
        next_break=bisect_right(index.section_breaks,top)
        y=min(0,index.section_breaks[next_break]-top-rect.height()) if next_break<len(index.section_breaks) else 0
        x=visible.left()+rect.x()
        self.setGeometry(x,visible.top()+y,max(0,min(rect.width(),visible.right()-x+1)),rect.height())
        self.show();self.raise_()
        if rebound:self.sync_pointer_state()

    def _toggle(self,node_id):
        # The visible resource is about to disappear: anchor the real header.
        self.gallery.toggle_node_expansion(node_id,anchor=(occurrence_id(self.content_entry),-self.gallery.available_gallery_rect().top()))

    def mouseMoveEvent(self,event):
        # A fixed presentation is not another category drag source.
        event.ignore()

    def mousePressEvent(self,event):
        # NodeCard normally focuses a real flow row. Focusing this temporary
        # proxy makes QScrollArea scroll to it again as it hides/rebinds.
        self._dragging=False
        self._pressed=True;self._keyboard_focus=False;self.update()
        event.accept()

    def paintEvent(self,event):
        gradient=QLinearGradient(0,0,0,self.height())
        for stop,alpha in ((0,190),(.55,140),(1,0)):
            color=QColor(colors()['window_base']);color.setAlpha(alpha);gradient.setColorAt(stop,color)
        painter=QPainter(self);painter.fillRect(self.rect(),gradient);painter.end()
        super().paintEvent(event)
