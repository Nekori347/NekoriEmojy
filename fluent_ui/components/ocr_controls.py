"""OCR stays in the existing settings rows and resource menu/dialog."""
from PySide6.QtCore import QObject,QTimer,Qt
from PySide6.QtWidgets import QFileDialog,QPlainTextEdit,QLabel,QWidget,QHBoxLayout
from fluent_ui.components import dialogs
from fluent_ui.components.controls import PushButton,SplitPushButton
from fluent_ui.components.setting_rows import InfoRow,SwitchRow
from services.ocr_service import ocr_service
from services.i18n import t,i18n_engine,bind_text,translated

STATES={'unrecognized':'尚未识别','ready':'已识别','empty':'未发现文字','failed':'识别失败'}
TASKS={'running':'正在识别','completed':'识别完成','cancelled':'已停止识别','interrupted':'上次识别已中断','idle':'暂无识别任务'}


def request_recognition(parent,storage,paths,force=False):
    service=ocr_service(storage)
    if not service.available:
        offer_install(parent);return
    ids=[r['id'] for path in paths if (r:=storage.index.resource(path))]
    manual=[rid for rid in ids if storage.index.ocr_info(rid).get('manual')]
    overwrite=False
    if manual and force:
        if not dialogs.confirm(parent,t('重新识别文字'),
            t('选中表情包含人工修改的文字。重新识别成功后将替换这些文字，是否继续？'),ok_text='重新识别'):
            return
        overwrite=True
    service.enqueue(ids,force=force,overwrite=overwrite)


def offer_install(parent):
    dialog=dialogs.NekoriDialog(parent,t('文字识别'))
    dialog.add_hint(t('请先安装本地文字识别组件。'))
    dialog.add_button('取消',on_click=dialog.reject)
    def go():
        dialog.accept();window=parent.window()
        while window is not None and not hasattr(window,'settings_window'):
            window=getattr(window,'owner',None) or window.parentWidget()
        if window is not None:
            settings=window.settings_window;settings.center._select_page(3);settings.center._show_tab(1)
            settings.show_page(settings.center)
    dialog.add_button('前往设置',role='primary',on_click=go)
    dialog.exec()


def recognize_all(parent,storage):
    service=ocr_service(storage)
    if not service.available:offer_install(parent);return
    if service.library_busy:return
    if dialogs.confirm(parent,t('重新识别全部表情？'),
        t('将重新识别表情库中已有的表情，\n包括已经完成识别的项目。\n\n人工修改的文字将继续保留。\n识别过程可以停止，已完成的结果不会丢失。'),
        ok_text='开始重新识别'):
        service.supplement(force=True)


def edit_text(parent,storage,path):
    record=storage.index.resource(path)
    if not record:return
    service=ocr_service(storage)
    info=storage.index.ocr_info(record['id'])
    dialog=dialogs.NekoriDialog(parent,'表情文字');dialog.setMinimumWidth(520)
    dialog.add_hint(t('这些文字用于搜索，不会添加为标签。保存后的人工修改不会被自动识别覆盖。'))
    dialog.add_widget(QLabel(t(STATES.get(info['status'],'尚未识别')),dialog))
    editor=QPlainTextEdit(dialog);editor.setPlainText(info['text']);editor.setMinimumHeight(200)
    from fluent_ui.visual import colors
    c=colors()
    editor.setStyleSheet(f"QPlainTextEdit {{background:{c['surface']};color:{c['text']};border:1px solid {c['border']};border-radius:8px;padding:8px;}}")
    dialog.add_widget(editor)
    dialog.add_button('取消',on_click=dialog.reject)
    def save():
        service.edit(record['id'],editor.toPlainText());dialog.accept()
    dialog.add_button('保存',role='primary',on_click=save)
    dialog.exec()


class OcrSettings(QObject):
    def __init__(self,center):
        super().__init__(center)
        self.center=center;self.service=ocr_service(center.storage)
        section=center._section('本地文字识别')
        self.component=InfoRow('本地文字识别组件','安装后可在本地识别表情中的文字。\n卸载组件不会删除已有识别结果或人工修改。','')
        text_column=self.component.layout().itemAt(0).layout()
        self.component.controls.removeWidget(self.component.value_label)
        self.component.value_label.setAlignment(Qt.AlignLeft)
        text_column.addWidget(self.component.value_label)
        self.component_info=QLabel(self.component);self.component_info.setWordWrap(True);text_column.addWidget(self.component_info)
        self.size_info=QLabel(self.component);self.size_info.setWordWrap(True);text_column.addWidget(self.size_info)
        self.install_button=translated(PushButton,'安装组件…',self.component)
        self.install_button.clicked.connect(self.install);self.component.add_control(self.install_button)
        self.remove_button=translated(PushButton,'卸载',self.component)
        self.remove_button.clicked.connect(self.uninstall);self.component.add_control(self.remove_button)
        section.add_row(self.component)
        self.auto=SwitchRow('自动识别新表情','新表情导入完成后，自动在后台识别文字。\n不会自动识别表情库中的已有表情。',
            'ocr_auto',center.pending.get('ocr_auto',center.config.get('ocr_auto',False)))
        center._track(self.auto,'ocr_auto',False);section.add_row(self.auto)
        self.task=InfoRow('后台文字识别','补充识别会跳过已完成且未变化的表情。\n人工修改会保留；停止后可以继续。','')
        self.task.controls.removeWidget(self.task.value_label)
        self.task.value_label.setAlignment(Qt.AlignLeft)
        self.task.layout().itemAt(0).layout().addWidget(self.task.value_label)
        self.task_info=QLabel(self.task);self.task_info.setWordWrap(True)
        self.task.layout().itemAt(0).layout().addWidget(self.task_info)
        self.task.layout().setContentsMargins(22,18,34,18)
        self.task.layout().setSpacing(24)
        def group(label,callback,primary=False):
            widget=SplitPushButton('',self.task);widget.setProperty('attached',True)
            widget.layout().setSpacing(0);widget.setFixedHeight(32)
            widget.button.ghost=True;widget.button.setFixedHeight(32)
            widget.dropButton.setFixedSize(28,32)
            bind_text(widget.button,label);bind_text(widget.dropButton,'更多…','setToolTip')
            if primary:
                for part in (widget,widget.button,widget.dropButton):part.setProperty('role','primary')
            widget.clicked.connect(callback);widget.dropButton.clicked.disconnect()
            widget.dropButton.clicked.connect(lambda checked=False,w=widget:self.show_more(w.dropButton))
            return widget
        self.retry_group=group('重试失败项',lambda:self.service.supplement(failed_only=True))
        self.retry_group.dropButton.setFixedWidth(24)
        self.supplement_group=group('补充识别',lambda:self.service.supplement(),True)
        self.stop_group=group('停止',self.cancel)
        self.retry=self.retry_group.button;self.supplement=self.supplement_group.button;self.cancel_button=self.stop_group.button
        self.more=self.supplement_group.dropButton
        self.operations=QWidget(self.task);commands=QHBoxLayout(self.operations)
        commands.setContentsMargins(0,0,0,0);commands.setSpacing(8)
        for widget in (self.retry_group,self.supplement_group,self.stop_group):commands.addWidget(widget)
        self.task.add_control(self.operations);section.add_row(self.task)
        self.task.controls.setAlignment(Qt.AlignVCenter)
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.setInterval(80)
        self.timer.timeout.connect(self.refresh)
        self.service.changed.connect(self._schedule_refresh)
        self.service.component_finished.connect(self.installed)
        i18n_engine.language_changed.connect(self.refresh)
        from threading import Thread
        def measure():
            try:self.service.component.sizes()
            finally:self.service.changed.emit()
        Thread(target=measure,name='OCRComponentSize',daemon=True).start()
        self.refresh()

    def _schedule_refresh(self,*_):self.timer.start()

    def show_more(self,anchor=None):
        from fluent_ui.components.safe_round_menu import SafeRoundMenu
        from qfluentwidgets import Action
        from fluent_ui.icons import Icon
        menu=SafeRoundMenu(parent=self.center)
        action=translated(Action,Icon.SCAN_TEXT,'重新识别全部表情…',parent=menu)
        action.setEnabled(self.service.available and not self.service.library_busy)
        action.triggered.connect(lambda:recognize_all(self.center,self.center.storage));menu.addAction(action)
        detail=translated(Action,'查看详情',parent=menu);detail.triggered.connect(self.show_details);menu.addAction(detail)
        menu.popup_at(anchor or self.more)

    def show_details(self):
        dialog=dialogs.NekoriDialog(self.center,t('文字识别详情'))
        editor=QPlainTextEdit(dialog);editor.setReadOnly(True)
        editor.setPlainText(self.service.install_error or self.service.summary.get('error','') or t('暂无错误详情'))
        dialog.add_widget(editor);dialog.add_button('关闭',on_click=dialog.accept);dialog.resize(620,360);dialog.exec()

    def install(self):
        release=self.service.component.release()
        if not release.get('url'):
            filename,_=QFileDialog.getOpenFileName(self.center,t('选择本地 OCR 组件包'),'',t('OCR 组件包 (*.zip)'))
            if filename:self.service.install(filename)
        else:self.service.install()

    def uninstall(self):
        if dialogs.confirm(self.center,t('卸载 OCR'),t('停止识别并移除 OCR 组件？已识别文字和人工修改会保留。'),ok_text='卸载'):
            try:self.service.uninstall();self.center.sync_external_preference('ocr_auto',False)
            except Exception as exc:dialogs.message(self.center,t('卸载失败'),str(exc))

    def installed(self,ok,error):
        if ok:self.center.sync_external_preference('ocr_auto',True)
        self.timer.start()

    def cancel(self):
        if self.service.installing:self.service._install_cancel.set()
        else:self.service.cancel()

    def refresh(self,*_):
        s=self.service;installed=s.component.installed
        state=t('已安装') if installed else t('未安装')
        if s.install_state=='downloading':
            done,total=s.download;state=t('正在下载')+(f' {done*100//total}%' if total else '')
        elif s.installing:
            done,total=s.download
            state=t('正在安装')+(f' {done*100//total}%' if total else '')
        elif s.install_state=='failed':state=t('安装失败')
        elif s.install_state=='cancelled':state=t('已取消安装')
        self.component.set_value(state)
        self.component_info.setText(t('在线组件尚未发布，请选择本地组件包安装。') if not s.component.release().get('url') else '')
        sizes=s.component._sizes or s.component.release()
        download=sizes.get('download',sizes.get('size',0));installed_size=sizes.get('installed',sizes.get('installed_size',0))
        def amount(n):return f'{n/1024**2:.1f} MiB' if n else t('未知')
        self.size_info.setText(t('下载大小：{download} · 安装后占用：{installed}').format(download=amount(download),installed=amount(installed_size)))
        if s.install_error:self.component_info.setText(t('组件安装失败，请检查组件包或查看详情。'))
        self.install_button.setEnabled(not installed and not s.installing)
        self.remove_button.setEnabled(installed and not s.installing)
        self.auto.setEnabled(installed and not s.installing)
        summary=s.summary
        state=t(TASKS.get(summary.get('state','idle'),'暂无识别任务'))
        processed=sum(summary.get(k,0) for k in ('done','failed','skipped'))
        self.task.set_value(state)
        hint=''
        if summary.get('total'):
            hint=t('已完成 {done} / {total} 张\n失败 {failed} 张 · 跳过 {skipped} 张').format(done=processed,total=summary['total'],failed=summary.get('failed',0),skipped=summary.get('skipped',0))
        if summary.get('error'):hint+='\n'+t('部分表情未能识别，请查看详情或重试。')
        self.task_info.setText(hint);self.task_info.setVisible(bool(hint))
        self.supplement.setEnabled(s.available and not s.library_busy)
        self.retry.setEnabled(s.available and not s.library_busy)
        self.cancel_button.setEnabled(s.busy or s.installing)
        running=s.busy or s.installing
        self.supplement_group.setVisible(not running);self.stop_group.setVisible(running)
        if not running:
            index=s.storage.index
            if getattr(self,'_failure_revision',None)!=index.search_revision:
                with index.connect(search=False) as db:
                    self._has_failures=bool(db.execute("SELECT 1 FROM resources WHERE json_extract(ocr_state_json,'$.status')='failed' LIMIT 1").fetchone())
                self._failure_revision=index.search_revision
        failures=not running and getattr(self,'_has_failures',False)
        self.retry_group.setVisible(failures)
        self.supplement_group.dropButton.setVisible(not failures)
        self.more=(self.stop_group if running else self.retry_group if failures else self.supplement_group).dropButton
        for widget in (self.retry_group,self.supplement_group,self.stop_group):
            # Details remain available even when recognition cannot start.
            widget.dropButton.setProperty('role','primary' if widget.property('role')=='primary' and widget.button.isEnabled() else None)
            widget.update()
        self.retry.setMinimumWidth(self.retry.fontMetrics().horizontalAdvance(self.retry.text())+28)
