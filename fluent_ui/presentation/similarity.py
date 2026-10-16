"""Comparison tool: one parameter bench, one result plate, one commit footer."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout,QHBoxLayout,QLabel,QScrollArea
from fluent_ui.components.controls import ComboBox,PushButton,PrimaryPushButton
from fluent_ui.components.softframe import SoftframeSlider
from fluent_ui.components.feedback import FeedbackHost
from fluent_ui import visual
from services.i18n import t,translated
from .surfaces import Surface,RuleHeading
from .tools import WrapCommands


def build_similarity(v):
    v.layout=QVBoxLayout(v);v.layout.setContentsMargins(4,2,4,4);v.layout.setSpacing(12)
    title=translated(QLabel,'感知哈希去重',v);title.setProperty('role','title');v.layout.addWidget(title)
    bench=Surface('raised',v,radius=12)
    form=QVBoxLayout(bench);form.setContentsMargins(16,14,16,14);form.setSpacing(10)
    hint=translated(QLabel,'结果为疑似相似图片，请逐张比较后勾选删除。动图悬停播放，点击图片放大；预览中方向键跨组切换，Del 切换删除勾选。',bench)
    hint.setWordWrap(True);hint.setProperty('role','hint');form.addWidget(hint)
    row=QHBoxLayout();row.setSpacing(12)
    v.scope=ComboBox(bench);v.scope.addItem(t('全部资源'),userData=None)
    for name in v.storage.get_all_categories():
        if name!='全部表情':v.scope.addItem(name,userData=name)
    v.kind=ComboBox(bench)
    for name,value in [('全部图片','all'),('仅静态图','static'),('仅动图','animated')]:v.kind.addItem(t(name),userData=value)
    v.scan_button=translated(PrimaryPushButton,'开始扫描',bench)
    v.cancel_button=translated(PushButton,'取消',bench);v.cancel_button.setEnabled(False);v.cancel_button.hide()
    row.addWidget(v.scope,1);row.addWidget(v.kind);row.addWidget(v.scan_button);row.addWidget(v.cancel_button);form.addLayout(row)
    track=QHBoxLayout();track.setContentsMargins(2,6,2,2)
    track.addWidget(translated(QLabel,'严格',bench))
    v.threshold=SoftframeSlider(Qt.Horizontal,bench);v.threshold.setRange(0,16);v.threshold.setValue(6)
    track.addWidget(v.threshold,1);track.addWidget(translated(QLabel,'宽松',bench))
    v.threshold_label=QLabel('6',bench);v.threshold_label.setProperty('role','data');track.addWidget(v.threshold_label)
    form.addLayout(track);v.layout.addWidget(bench)
    result=Surface('base',v,radius=14);content=QVBoxLayout(result);content.setContentsMargins(14,10,14,12)
    v.status=translated(QLabel,'选择范围后点击开始扫描。',result);v.status.setWordWrap(True);content.addWidget(v.status)
    v.scroll=QScrollArea(result);v.scroll.setObjectName('similarityResults');v.scroll.setWidgetResizable(True);v.scroll.setFrameShape(QScrollArea.NoFrame)
    content.addWidget(v.scroll,1);v.layout.addWidget(result,1)
    v.feedback_host=FeedbackHost(v,v.layout,before=result);v.progress=v.feedback_host.progress
    footer=WrapCommands();v.layout.addLayout(footer)
    v.previous=translated(PushButton,'上一页',v);v.next=translated(PushButton,'下一页',v);v.page_label=QLabel(v)
    v.clear_button=translated(PushButton,'清空选择',v);v.delete_button=translated(PushButton,'删除所选（0）',v)
    v.delete_button.setProperty('role','danger')
    for w in (v.previous,v.page_label,v.next,v.clear_button,v.delete_button):footer.addWidget(w)
    visual.apply_typography(v)
