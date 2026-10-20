"""One compact information block embedded in Settings, with shared link routing."""
from html import escape
from PySide6.QtCore import QUrl,Qt,QSize
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QWidget,QLabel,QVBoxLayout,QHBoxLayout,QGridLayout
from fluent_ui import visual
from fluent_ui.icons import Icon
from fluent_ui.components.controls import TransparentToolButton
from fluent_ui.components.softframe import paint_setting_surface
from services.i18n import t,bind_text,i18n_engine

AUTHOR_LINKS=(('GitHub',Icon.GITHUB,'https://github.com/Nekori347'),
              ('X',Icon.BRAND_X,'https://x.com/Nekori_Net'),
              ('哔哩哔哩',Icon.BILIBILI,'https://space.bilibili.com/17409970'))
SOURCES=(('SuzuEmojy · IxinorTyan','https://github.com/IxinorTyan/SuzuEmojy'),
         ('Nekori Softframe','https://github.com/Nekori347/Nekori-Softframe'),
         ('QQFavoriteExtract · VanillaNahida','https://github.com/VanillaNahida/QQFavoriteExtract'))


class AboutInformation(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.external_buttons={}
        root=QVBoxLayout(self);root.setContentsMargins(18,16,18,16);root.setSpacing(14)
        header=QHBoxLayout();header.setSpacing(10)
        logo=QLabel(self);logo.setPixmap(self.window().windowIcon().pixmap(48,48));header.addWidget(logo)
        names=QVBoxLayout();names.setSpacing(1)
        name=QLabel('NekoriEmojy',self);name.setFont(visual.font('section_title'));names.addWidget(name)
        summary=QLabel(self);bind_text(summary,'本地表情管理');summary.setFont(visual.font('secondary'));names.addWidget(summary)
        header.addLayout(names,1)
        author=QVBoxLayout();author.setSpacing(1);title=QLabel(self);bind_text(title,'作者');title.setFont(visual.font('secondary'));author.addWidget(title)
        author.addWidget(QLabel('Nekori_Net',self))
        social=QHBoxLayout();social.setSpacing(8)
        for label,icon,url in AUTHOR_LINKS:
            button=TransparentToolButton(icon,self);button.setFixedSize(28,28);button.setIconSize(QSize(18,18))
            button.setAccessibleName(label);button.setToolTip(label+' · '+url)
            button.setFocusPolicy(Qt.StrongFocus);button.clicked.connect(lambda checked=False,u=url:self.open_link(u))
            self.external_buttons[label]=button;social.addWidget(button)
        social.addStretch();author.addLayout(social);header.addLayout(author);root.addLayout(header)
        self.links=[]
        for heading,entries in (
            ('项目参考与相关工具',SOURCES),
            ('字体、图标与界面资源',tuple((name,None) for name in ('Sarasa UI SC','Rajdhani','JetBrains Mono','Tabler Icons'))),
            ('框架与许可证',(('PySide6',None),('GPL-3.0','https://github.com/Nekori347/NekoriEmojy/blob/main/LICENSE')))):
            group=QVBoxLayout();group.setSpacing(6)
            title=QLabel(self);bind_text(title,heading);title.setFont(visual.font('section_title'));group.addWidget(title)
            grid=QGridLayout();grid.setHorizontalSpacing(20);grid.setVerticalSpacing(6)
            for index,(name,url) in enumerate(entries):
                label=QLabel(self);label.setFont(visual.font('secondary'))
                label.setTextInteractionFlags(Qt.LinksAccessibleByMouse|Qt.LinksAccessibleByKeyboard)
                label.linkActivated.connect(self.open_link);label.setToolTip(url or name)
                self.links.append((label,name,url));grid.addWidget(label,index//2,index%2)
            grid.setColumnStretch(0,1);grid.setColumnStretch(1,1);group.addLayout(grid);root.addLayout(group)
        self.license=QLabel(self);self.license.setFont(visual.font('secondary'));self.license.setWordWrap(True)
        self.license.linkActivated.connect(self.open_link);root.addWidget(self.license)
        i18n_engine.language_changed.connect(self.refresh_texts);visual.theme.changed.connect(self.refresh_texts);self.refresh_texts()

    def open_link(self,url):return QDesktopServices.openUrl(QUrl(url))

    def refresh_texts(self,*_):
        color=visual.colors()['text_secondary']
        for label,name,url in self.links:
            label.setText(f'<a href="{escape(url)}" style="color:{color};text-decoration:none;white-space:nowrap">{escape(name)}</a>' if url else name)
            label.setStyleSheet(f'color:{color};background:transparent;')
        self.license.setText(t('表情版权归各自作者所有'))
        self.update()

    def paintEvent(self,event):
        from PySide6.QtGui import QPainter
        from PySide6.QtCore import QRectF
        painter=QPainter(self);paint_setting_surface(painter,QRectF(self.rect()))
