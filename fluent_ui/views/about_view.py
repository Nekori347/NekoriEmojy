"""Nekori identity and concise upstream acknowledgements on shared surfaces."""
from PySide6.QtCore import Qt,Signal,QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QWidget,QLabel,QVBoxLayout,QHBoxLayout,QScrollArea,QApplication
from fluent_ui import visual
from fluent_ui.icons import Icon
from fluent_ui.presentation.surfaces import Surface,RuleHeading
from fluent_ui.components.controls import PushButton,TransparentToolButton
from fluent_ui.components.softframe import DisclosureButton
from services.update_service import current_version
from services.i18n import t,bind_text,i18n_engine


class AboutInterface(QWidget):
    back_requested=Signal()
    AUTHOR_URL='https://github.com/Nekori347'
    def __init__(self,parent=None):
        super().__init__(parent);self.setObjectName('AboutInterface')
        root=QVBoxLayout(self);root.setContentsMargins(4,2,4,4);root.setSpacing(12)
        head=QHBoxLayout();self.btnBack=TransparentToolButton(Icon.LEFT_ARROW,self)
        bind_text(self.btnBack,'返回设置','setToolTip');self.btnBack.clicked.connect(self.back_requested)
        head.addWidget(self.btnBack);self.titleLabel=QLabel(self);bind_text(self.titleLabel,'关于软件')
        self.titleLabel.setProperty('role','title');head.addWidget(self.titleLabel);head.addStretch();root.addLayout(head)
        self.sheet=Surface('base',self,radius=14);root.addWidget(self.sheet,1)
        sheet=QVBoxLayout(self.sheet);sheet.setContentsMargins(24,24,24,20);sheet.setSpacing(24)
        brand=QHBoxLayout();logo=QLabel(self.sheet)
        # The window supplies the actual Nekori icon, including user overrides.
        logo.setPixmap(self.window().windowIcon().pixmap(64,64));brand.addWidget(logo)
        names=QVBoxLayout();name=QLabel('NekoriEmojy',self.sheet);name.setFont(visual.font('page_title'));name.setProperty('role','title')
        names.addWidget(name);self.summary=QLabel(self.sheet);bind_text(self.summary,'本地图片与表情资源管理')
        self.summary.setProperty('role','hint');names.addWidget(self.summary);brand.addLayout(names,1)
        self.version=QLabel('v'+current_version(),self.sheet);self.version.setProperty('role','data');brand.addWidget(self.version)
        sheet.addLayout(brand)
        self.scroll=QScrollArea(self.sheet);self.scroll.setWidgetResizable(True);self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.scroll.setStyleSheet('QScrollArea {border:none;background:transparent;}')
        body=QWidget();self.scroll.setWidget(body);body.setAutoFillBackground(False)
        self.scroll.viewport().setAutoFillBackground(False)
        content=QVBoxLayout(body);content.setContentsMargins(0,0,0,0);content.setSpacing(18);content.setAlignment(Qt.AlignTop)
        self._entry(content,'Nekori347','NekoriEmojy · Softframe',self.AUTHOR_URL)
        details=Surface('raised',body,radius=12);info=QVBoxLayout(details);info.setContentsMargins(20,16,20,16);info.setSpacing(12)
        for text in ('分类、标签与搜索','快速面板与图片发送','QQ / Telegram 导入工具'):
            label=QLabel(details);bind_text(label,text);info.addWidget(label)
        content.addWidget(details)
        title=RuleHeading('',body);bind_text(title.label,'来源与致谢');content.addWidget(title)
        self._entry(content,'SuzuEmojy · IxinorTyan','兼容来源与原始代码致谢','https://github.com/IxinorTyan/SuzuEmojy')
        self._entry(content,'Nekori Softframe','界面设计规范','https://github.com/Nekori347/Nekori-Softframe')
        self._entry(content,'QQFavoriteExtract · VanillaNahida','QQ 表情提取参考','https://github.com/VanillaNahida/QQFavoriteExtract')
        resources=QLabel('Sarasa UI SC  /  Rajdhani  /  JetBrains Mono\nTabler Icons  ·  PySide6',body)
        resources.setFont(visual.font('data'));resources.setProperty('role','data');content.addWidget(resources)
        license=QLabel('GPL-3.0  ·  '+t('资源版权归各自作者所有'),body);license.setWordWrap(True)
        license.setProperty('role','hint');content.addWidget(license);sheet.addWidget(self.scroll,1)
        footer=QHBoxLayout();footer.addStretch()
        self.btnReleases=PushButton(Icon.CLOUD_DOWNLOAD,t('检查更新'),self.sheet)
        self.btnReleases.clicked.connect(self._open_updates);footer.addWidget(self.btnReleases);sheet.addLayout(footer)
        visual.apply_typography(self);i18n_engine.language_changed.connect(self.update_texts)
        visual.theme.changed.connect(self.refresh_theme);self.refresh_theme()

    def refresh_theme(self):
        c=visual.colors()
        self.setStyleSheet(f'QLabel {{color:{c["text"]};background:transparent;}} QLabel[role="hint"],QLabel[role="data"] {{color:{c["text_secondary"]};}}')
    def _entry(self,layout,title,description,url):
        row=Surface('raised',self,radius=12,edge=False);box=QHBoxLayout(row);box.setContentsMargins(18,16,14,16)
        text=QVBoxLayout();name=QLabel(title,row);name.setFont(visual.font('section_title'));text.addWidget(name)
        note=QLabel(row);bind_text(note,description);note.setProperty('role','hint');text.addWidget(note);box.addLayout(text,1)
        button=TransparentToolButton(Icon.LINK,row);button.setFixedSize(32,32);button.setToolTip(url)
        button.clicked.connect(lambda:QDesktopServices.openUrl(QUrl(url)));box.addWidget(button);layout.addWidget(row)
    def _open_updates(self):
        from fluent_ui.components.update_center import update_center
        update_center().open(self.window())
    def update_texts(self,*_):
        self.btnReleases.setText(t('检查更新'));visual.apply_typography(self)
    def shutdown(self):
        if hasattr(self,'update_dialog'):self.update_dialog.shutdown()
