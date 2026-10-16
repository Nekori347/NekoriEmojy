"""Input bench and results sheet for the import tools, sharing the native shell."""
from PySide6.QtCore import Qt,QRect,QSize,QTimer
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QBoxLayout,QLayout,QLayoutItem,QLineEdit,QSizePolicy,QLabel,QScrollArea,QFrame,QStyledItemDelegate,QStyle
from fluent_ui import visual
from .surfaces import Surface,RuleHeading
from services.i18n import bind_text,t


class WrapCommands(QLayout):
    """Commands preserve label width and wrap as complete hit targets."""
    def __init__(self,parent=None):
        super().__init__(parent);self._items=[];self.setContentsMargins(8,8,8,8);self.setSpacing(6)
    def addItem(self,item):self._items.append(item)
    def count(self):return len(self._items)
    def itemAt(self,i):return self._items[i] if 0<=i<len(self._items) else None
    def takeAt(self,i):return self._items.pop(i) if 0<=i<len(self._items) else None
    def addStretch(self,*_):pass
    def expandingDirections(self):return Qt.Horizontal
    def hasHeightForWidth(self):return True
    def heightForWidth(self,width):return self._arrange(QRect(0,0,width,0),False)
    def minimumSize(self):
        w=max((i.minimumSize().width() for i in self._items),default=0)
        return QSize(w+16,48)
    def sizeHint(self):return self.minimumSize()
    def setGeometry(self,r):super().setGeometry(r);self._arrange(r,True)
    def _arrange(self,r,apply):
        m=self.contentsMargins();x=r.x()+m.left();y=r.y()+m.top();start=x;h=0
        for item in self._items:
            if item.widget() and item.widget().isHidden():continue
            size=item.sizeHint();size.setHeight(max(30,size.height()))
            if x>start and x+size.width()>r.x()+r.width()-m.right():x=start;y+=h+self.spacing();h=0
            if apply:item.setGeometry(QRect(x,y,size.width(),size.height()))
            x+=size.width()+self.spacing();h=max(h,size.height())
        return y-r.y()+h+m.bottom()


class ImportBench(QWidget):
    def __init__(self,view):
        super().__init__(view);self.view=view
        from fluent_ui.components.controls import PushButton,TransparentToolButton
        from fluent_ui.icons import Icon
        self.is_tg=hasattr(view,'urlInputEdit')
        self.row=QHBoxLayout(self);self.row.setContentsMargins(0,0,0,0);self.row.setSpacing(8)
        self.inputs=Surface('raised',self,radius=12);left=QVBoxLayout(self.inputs)
        left.setContentsMargins(12,10,12,10);left.setSpacing(10)
        heading=RuleHeading('',self.inputs);bind_text(heading.label,'导入来源');left.addWidget(heading)
        view.configFormWidget=QWidget(self.inputs);form=QVBoxLayout(view.configFormWidget)
        form.setContentsMargins(0,0,0,0);form.setSpacing(10)
        view.configScrollArea=QScrollArea(self.inputs);view.configScrollArea.setWidgetResizable(True)
        view.configScrollArea.setFrameShape(QFrame.NoFrame);view.configScrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.configScrollArea.setStyleSheet('QScrollArea {border:none;background:transparent;}')
        view.configScrollArea.viewport().setAutoFillBackground(False)
        view.configScrollArea.setWidget(view.configFormWidget);view.configFormWidget.setAutoFillBackground(False)
        left.addWidget(view.configScrollArea,1)
        if self.is_tg:
            self.field(form,view.urlLabel,view.urlInputEdit,view.helpButton)
            view.urlInputEdit.setPlaceholderText(t('输入表情合集链接或名称'))
            form.addWidget(view.parseButton)
            self.network_button=PushButton(t('连接设置'),self.inputs);self.network_button.clicked.connect(self.open_network)
            form.addWidget(self.network_button)
            form.addWidget(view.batchPackageButton)
        else:
            self.field(form,view.readPathLabel,view.readPathEdit,view.selectReadDirButton)
            self.field(form,view.userLabel,view.userComboBox,view.helpButton)
            self.field(form,view.emojiFolderLabel,view.emojiFolderComboBox)
            form.addWidget(view.scanButton)
        form.addStretch()
        self.export_dialog=None;self.export_options=PushButton(t('导出设置'),self.inputs)
        self.export_options.clicked.connect(self.open_export_options);left.addWidget(self.export_options)
        self.results=Surface('base',self,radius=12);right=QVBoxLayout(self.results)
        right.setContentsMargins(8,8,8,8);right.setSpacing(6)
        toolbar=QHBoxLayout()
        if hasattr(view,'previewTitleLabel'):
            view.previewTitleLabel.setParent(self.results);view.previewTitleLabel.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred);toolbar.addWidget(view.previewTitleLabel,1)
        else:
            label=QLabel(self.results);bind_text(label,'表情预览');toolbar.addWidget(label,1)
        for name,icon,text,callback in (
            ('selectAllButton',Icon.ACCEPT,'全选已加载',view.selectAllLoaded),
            ('clearSelectionButton',Icon.CANCEL,'清空选择',view.clearSelection)) + (
                (('invertSelectionButton',Icon.SYNC,'反选',view.invertSelection),) if self.is_tg else ()):
            old=getattr(view,name);old.hide()
            button=IconCommand(self.results);button.setIcon(icon);button.setText(t(text));button.setFixedSize(26,26)
            button.clicked.connect(callback);setattr(view,name,button);toolbar.addWidget(button)
        right.addLayout(toolbar)
        grid=view.previewListWidget;grid.setParent(self.results)
        grid.setIconSize(QSize(80,80));grid.setGridSize(QSize(88,88));grid.setMinimumSize(180,150)
        grid.setStyleSheet('QListWidget {background:transparent;border:none;outline:none;}')
        grid.setItemDelegate(ImportTileDelegate(grid));right.addWidget(grid,1)
        inspector=Surface('raised',self.results,radius=8);detail=QHBoxLayout(inspector)
        detail.setContentsMargins(8,6,8,6);detail.setSpacing(10)
        view.detailPreviewLabel.setParent(inspector);view.detailPreviewLabel.setFixedSize(64,64)
        view.detailPreviewLabel.setFrameStyle(QFrame.NoFrame);detail.addWidget(view.detailPreviewLabel)
        view.detailInfoLabel.setMinimumWidth(0);view.detailInfoLabel.setMaximumWidth(16777215)
        view.detailInfoLabel.setParent(inspector);view.detailInfoLabel.setWordWrap(True);detail.addWidget(view.detailInfoLabel,1)
        view.detailWidget=inspector;inspector.setMaximumHeight(120);right.addWidget(inspector);inspector.hide()
        grid.itemSelectionChanged.connect(self.update_detail_visibility)
        self.actions=QWidget(self.results);actions=QHBoxLayout(self.actions);actions.setContentsMargins(0,2,0,0);actions.setSpacing(6)
        for button in (view.importSelectedButton,view.importAllButton):
            button.setParent(self.actions);actions.addWidget(button);button.show()
        actions.addStretch()
        self.more=PushButton(t('导出'),self.actions);self.more.clicked.connect(self.show_exports);actions.addWidget(self.more)
        self.actions.setFixedHeight(38);right.addWidget(self.actions)
        self.row.addWidget(self.inputs);self.row.addWidget(self.results,1)
        self.update_detail_visibility()
        visual.theme.changed.connect(self.refresh_theme);self.refresh_theme()

    def field(self,layout,label,control,trailing=None):
        group=QWidget(self);column=QVBoxLayout(group);column.setContentsMargins(0,0,0,0);column.setSpacing(4)
        label.setParent(group);label.setMinimumWidth(0);label.setMaximumWidth(16777215)
        from fluent_ui.components.controls import _own_presentation
        _own_presentation(label)
        label.setProperty('role','hint');column.addWidget(label);label.show()
        row=QHBoxLayout();row.setSpacing(4);control.setParent(group);control.setMinimumWidth(0)
        control.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed);row.addWidget(control,1);control.show()
        if trailing:
            trailing.setParent(group)
            if isinstance(trailing, __import__('fluent_ui.components.controls',fromlist=['TransparentToolButton']).TransparentToolButton):trailing.setFixedSize(24,24)
            else:trailing.setFixedWidth(max(68,trailing.sizeHint().width()))
            row.addWidget(trailing);trailing.show()
        column.addLayout(row);layout.addWidget(group)

    def build_network(self):
        from fluent_ui.components.dialogs import NekoriDialog
        self.network=NekoriDialog(self.view.window(),t('连接设置'));self.network.resize(580,390)
        v=self.view
        for label,control,trailing in ((v.tokenLabel,v.tokenEdit,v.toggleTokenBtn),(v.cfProxyLabel,v.cfProxyEdit,None),(v.proxyLabel,v.proxyEdit,None)):
            self.field(self.network.body,label,control,trailing)
        row=QHBoxLayout();row.addWidget(v.testNetButton);row.addWidget(v.resetCfgButton);self.network.body.addLayout(row)
        self.network.add_button('完成',on_click=self.network.accept)

    def open_network(self):
        if not hasattr(self,'network'):self.build_network()
        self.network.show();self.network.raise_();self.network.activateWindow()

    def open_export_options(self):
        from fluent_ui.components.dialogs import NekoriDialog
        if self.export_dialog is None:
            self.export_dialog=NekoriDialog(self.view.window(),t('导出设置'));self.export_dialog.resize(560,260)
            self.field(self.export_dialog.body,self.view.savePathLabel,self.view.savePathEdit,self.view.selectDirButton)
            if self.is_tg:
                self.field(self.export_dialog.body,self.view.formatLabel,self.view.formatComboBox)
                self.export_dialog.body.addWidget(self.view.zipCheckBox)
            self.export_dialog.add_button('完成',on_click=self.export_dialog.accept)
        self.export_dialog.show();self.export_dialog.raise_();self.export_dialog.activateWindow()

    def show_exports(self):
        from fluent_ui.components.safe_round_menu import SafeRoundMenu
        from qfluentwidgets import Action
        menu=SafeRoundMenu(parent=self.more)
        buttons=[self.view.exportSelectedButton,self.view.exportAllButton]
        if self.is_tg:buttons.append(self.view.exportPackageButton)
        for button in buttons:
            action=Action(button.text(),menu);action.setEnabled(button.isEnabled());action.triggered.connect(button.click);menu.addAction(action)
        self.export_menu=menu;menu.exec(self.more.mapToGlobal(self.more.rect().bottomLeft()))

    def set_config_expanded(self,expanded):
        # Core source controls remain beside results; scanning never removes
        # the ability to change source or import without returning to a page.
        self.view.summaryRow.hide()

    def update_detail_visibility(self):
        self.view.detailWidget.setVisible(bool(self.view.previewListWidget.selectedItems()))

    def refresh_theme(self):
        c=visual.colors()
        self.setStyleSheet(f'QLabel {{color:{c["text"]};background:transparent;}} QLabel[role="hint"] {{color:{c["text_secondary"]};}}')
        for label in self.findChildren(QLabel):
            from fluent_ui.components.controls import _own_presentation
            _own_presentation(label)
            label.setStyleSheet('background:transparent;color:'+c['text_secondary' if label.property('role')=='hint' else 'text']+';')

    def fit_form(self):
        self.view.configFormWidget.layout().activate()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        self.inputs.setFixedWidth(300 if self.width()>=900 else 260)


def build_import_tool(view):
    for widget in (view.topBar,view.summaryRow,view.configCard,view.actionBar,view.detailWidget,view.detailTitle,view.thanksLabel):widget.hide()
    while view.mainLayout.count():view.mainLayout.takeAt(0)
    view.mainLayout.setContentsMargins(2,2,2,2);view.mainLayout.setSpacing(6)
    view.presentation=ImportBench(view);view.mainLayout.addWidget(view.presentation,1)
    # Low-frequency help/log remain a compact footer instead of a large card
    # occupying the preview surface.
    foot=QHBoxLayout();foot.setContentsMargins(4,0,4,0)
    view.summaryLabel.setParent(view);view.summaryLabel.setProperty('role','hint');foot.addWidget(view.summaryLabel,1);view.summaryLabel.show()
    view.btnLog.setParent(view);view.btnLog.setFixedSize(24,24);foot.addWidget(view.btnLog);view.btnLog.show()
    view.mainLayout.addLayout(foot)
    visual.apply_typography(view)


class ImportTileDelegate(QStyledItemDelegate):
    def sizeHint(self,option,index):return QSize(88,88)
    def paint(self,p,option,index):
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QColor,QPen,QPainter,QPainterPath
        c=visual.colors();r=QRectF(option.rect).adjusted(2,2,-2,-2)
        p.save();p.setRenderHint(QPainter.Antialiasing);p.setBrush(QColor(c['surface_alt']))
        p.setPen(QPen(QColor(c['accent'] if option.state&QStyle.State_Selected else c['border'] if option.state&QStyle.State_MouseOver else c['border_soft']),1))
        p.drawRoundedRect(r,8,8)
        icon=index.data(Qt.DecorationRole)
        if icon:
            clip=QPainterPath();clip.addRoundedRect(r.adjusted(2,2,-2,-2),6,6);p.setClipPath(clip)
            icon.paint(p,r.adjusted(2,2,-2,-2).toRect())
        p.restore()


from fluent_ui.components.controls import TransparentToolButton
class IconCommand(TransparentToolButton):
    def setText(self,text):
        self.setToolTip(text);self.setAccessibleName(text)
