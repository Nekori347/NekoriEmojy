"""One page for first use and recovery; no data is touched by the pickers."""
from PySide6.QtWidgets import QFileDialog,QLabel,QHBoxLayout
from PySide6.QtCore import Qt
from fluent_ui.components.dialogs import NekoriDialog
from fluent_ui.components.controls import PushButton
from services.i18n import t,translated
from services.library_setup import check_target,commit_library,LibraryLocationError


class LibrarySetupDialog(NekoriDialog):
    def __init__(self,config,path,*,recovery=False):
        super().__init__(title='无法找到表情库' if recovery else '设置表情库位置')
        self.config=config;self.storage=None;self.path=str(path);self.mode='connect' if recovery else 'create'
        self.recovery=recovery;self.setMinimumWidth(550);self.resize(590,320)
        self.add_hint('无法访问原来的表情库位置。\n请选择原有表情库的新位置，或明确创建新的表情库。' if recovery else
                      '选择保存表情及管理数据的位置。\n以后可以在设置中查看或重新连接表情库。')
        if recovery:
            self.add_hint('原来的表情库位置')
            original=QLabel(self.path,self);original.setWordWrap(True);original.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.body.addWidget(original)
        self.path_label=QLabel(self.path,self);self.path_label.setWordWrap(True);self.body.addWidget(self.path_label)
        self.path_label.setVisible(not recovery)
        choices=QHBoxLayout();choices.setSpacing(8)
        self.choose_new=translated(PushButton,'创建新表情库…' if recovery else '选择其他位置…',self)
        self.choose_existing=translated(PushButton,'重新定位表情库…' if recovery else '连接已有表情库…',self)
        self.choose_new.clicked.connect(lambda:self.choose('create'))
        self.choose_existing.clicked.connect(lambda:self.choose('connect'))
        for button in ((self.choose_existing,self.choose_new) if recovery else (self.choose_new,self.choose_existing)):choices.addWidget(button)
        self.body.addLayout(choices)
        self.error_label=self.add_hint('');self.error_label.setProperty('role','error');self.error_label.hide()
        self.exit_button=self.add_button('退出' if recovery else '取消',on_click=self.reject)
        self.start_button=self.add_button('开始使用',role='primary',on_click=self.begin)
        if recovery:self.start_button.setEnabled(False)

    def show_failure(self,error):
        if isinstance(error,LibraryLocationError):text=t(str(error))
        else:text=t('无法准备表情库或保存设置。\n请检查目录是否可写，然后重试或选择其他位置。')
        self.error_label.setText(text);self.error_label.show();self.adjustSize()

    def choose(self,mode):
        directory=QFileDialog.getExistingDirectory(self,t('创建新表情库…' if mode=='create' else '连接已有表情库…'),self.path)
        if not directory:return
        try:actual=check_target(directory,mode)
        except (OSError,ValueError) as error:self.show_failure(error);return
        self.path=directory;self.mode=actual;self.path_label.setText(directory)
        self.path_label.show()
        self.start_button.setEnabled(True);self.error_label.hide()

    def begin(self):
        self.start_button.setEnabled(False)
        try:self.storage=commit_library(self.config,self.path,self.mode)
        except Exception as error:
            self.show_failure(error);self.start_button.setEnabled(True);return
        self.accept()


def open_startup_library(config):
    from services.library_setup import startup_location,prepare_library
    from services.i18n import i18n_engine
    from fluent_ui import visual
    i18n_engine.init(config);visual.theme.configure(config)
    path,needs_ui,recovery=startup_location(config)
    if not needs_ui:
        try:
            mode='connect' if path.exists() and any(path.iterdir()) else 'create'
            with prepare_library(path,mode,config) as storage:return storage
        except Exception:recovery=True
    dialog=LibrarySetupDialog(config,path,recovery=recovery)
    return dialog.storage if dialog.exec() else None
