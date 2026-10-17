"""OCR stays in the existing settings rows and resource menu/dialog."""
from PySide6.QtCore import QObject,QTimer
from PySide6.QtWidgets import QFileDialog,QPlainTextEdit,QLabel
from fluent_ui.components import dialogs
from fluent_ui.components.controls import PushButton
from fluent_ui.components.setting_rows import InfoRow,SwitchRow
from services.ocr_service import ocr_service
from services.i18n import t,i18n_engine

STATES={'unrecognized':'尚未识别','ready':'已识别','empty':'未发现文字','failed':'识别失败'}
TASKS={'running':'正在识别','completed':'识别完成','cancelled':'已停止识别','interrupted':'上次识别已中断','idle':'暂无识别任务'}


def request_recognition(parent,storage,paths,force=False):
    service=ocr_service(storage)
    if not service.available:
        dialogs.message(parent,t('文字识别'),t('请先在设置中安装 OCR 组件。'));return
    ids=[r['id'] for path in paths if (r:=storage.index.resource(path))]
    manual=[rid for rid in ids if storage.index.ocr_info(rid).get('manual')]
    overwrite=False
    if manual and force:
        if not dialogs.confirm(parent,t('重新识别文字'),
            t('选中表情包含人工修改的文字。重新识别成功后将替换这些文字，是否继续？'),ok_text='重新识别'):
            return
        overwrite=True
    service.enqueue(ids,force=force,overwrite=overwrite)


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
        self.component=InfoRow('OCR 组件','可选安装，识别在本地完成。卸载组件不会删除已有文字。','')
        self.install_button=PushButton(t('安装 OCR…'),self.component)
        self.install_button.clicked.connect(self.install);self.component.add_control(self.install_button)
        self.remove_button=PushButton(t('卸载'),self.component)
        self.remove_button.clicked.connect(self.uninstall);self.component.add_control(self.remove_button)
        section.add_row(self.component)
        self.auto=SwitchRow('自动识别新表情','导入成功后在后台识别，不会自动扫描已有表情。',
            'ocr_auto',center.pending.get('ocr_auto',center.config.get('ocr_auto',False)))
        center._track(self.auto,'ocr_auto',False);section.add_row(self.auto)
        self.task=InfoRow('后台识别','补识别会跳过已完成且未变化的表情，保留人工修改；停止后可再次继续。','')
        self.supplement=PushButton(t('补识别已有表情'),self.task)
        self.supplement.clicked.connect(lambda:self.service.supplement());self.task.add_control(self.supplement)
        section.add_row(self.task)
        self.retry=PushButton(t('重试失败项'),self.task)
        self.retry.clicked.connect(lambda:self.service.supplement(failed_only=True));self.task.add_control(self.retry)
        self.cancel_button=PushButton(t('停止'),self.task)
        self.cancel_button.clicked.connect(self.cancel);self.task.add_control(self.cancel_button)
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.setInterval(80)
        self.timer.timeout.connect(self.refresh)
        self.service.changed.connect(lambda:self.timer.start())
        self.service.component_finished.connect(self.installed)
        i18n_engine.language_changed.connect(lambda *_:self.refresh())
        self.refresh()

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

    def refresh(self):
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
        hint=t('可选安装，识别在本地完成。卸载组件不会删除已有文字。')
        if not s.component.release().get('url'):hint+='\n'+t('在线组件尚未发布，目前支持从本地组件包安装。')
        if s.install_error:hint+='\n'+s.install_error
        self.component.set_hint(hint)
        self.install_button.setEnabled(not installed and not s.installing)
        self.remove_button.setEnabled(installed and not s.installing)
        self.auto.setEnabled(installed and not s.installing)
        summary=s.summary
        state=t(TASKS.get(summary.get('state','idle'),'暂无识别任务'))
        processed=sum(summary.get(k,0) for k in ('done','failed','skipped'))
        self.task.set_value(state)
        hint=t('补识别会跳过已完成且未变化的表情，保留人工修改；停止后可再次继续。')
        if summary.get('total'):
            hint+='\n'+t('{done}/{total}，失败 {failed}，跳过 {skipped}').format(done=processed,total=summary['total'],failed=summary.get('failed',0),skipped=summary.get('skipped',0))
        if summary.get('error'):hint+='\n'+summary['error']
        self.task.set_hint(hint)
        self.supplement.setEnabled(s.available and not s.busy)
        self.retry.setEnabled(s.available and not s.busy)
        self.cancel_button.setEnabled(s.busy or s.installing)
