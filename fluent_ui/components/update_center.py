"""User-initiated update state shared by Settings, About and the wordmark."""
import json
import time
from PySide6.QtCore import QObject,Signal,Qt,QPoint
from PySide6.QtWidgets import QApplication,QLabel,QWidget
from services.update_service import UpdateService,install_root
from fluent_ui.components.controls import TransparentToolButton,PushButton
from fluent_ui.icons import Icon
from services.i18n import t
from services.update_protocol import MANIFEST


class VersionDot(QWidget):
    def __init__(self,parent):
        super().__init__(parent);self.setFixedSize(5,5);self.setAttribute(Qt.WA_TransparentForMouseEvents);self.hide()
    def paintEvent(self,event):
        from PySide6.QtGui import QPainter,QColor
        from fluent_ui import visual
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.setPen(Qt.NoPen)
        p.setBrush(QColor(visual.colors()['danger']));p.drawEllipse(self.rect())


class VersionLabel(QLabel):
    """Keep the update dot attached to the actual version text, not its row."""
    dot_visible=False

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.dot=VersionDot(self.parentWidget())

    def position_dot(self):
        if not hasattr(self,'dot'):return
        fm=self.fontMetrics();ink=fm.tightBoundingRect(self.text())
        y=round((self.height()-fm.height())/2+fm.ascent()+ink.top())-3
        self.dot.move(self.mapTo(self.parentWidget(),QPoint(fm.horizontalAdvance(self.text())+2,y)))
        self.dot.setVisible(self.dot_visible and self.isVisible());self.dot.raise_()

    def set_update_available(self,available):
        self.dot_visible=bool(available);self.position_dot();self.update()

    def sizeHint(self):
        return super().sizeHint()

    def paintEvent(self,event):
        super().paintEvent(event)
        self.position_dot()

    def resizeEvent(self,event):super().resizeEvent(event);self.position_dot()
    def moveEvent(self,event):super().moveEvent(event);self.position_dot()
    def showEvent(self,event):super().showEvent(event);self.position_dot()
    def hideEvent(self,event):super().hideEvent(event);self.dot.hide()


class UpdateBadge(TransparentToolButton):
    def __init__(self,parent=None):
        super().__init__(parent);self.setIcon(Icon.UPDATE);self.setFixedSize(20,20)
        update_center().changed.connect(self.refresh)
        self.clicked.connect(self._open);self.refresh()
        from services.i18n import i18n_engine
        i18n_engine.language_changed.connect(self.refresh)
    def refresh(self,*_):
        release=update_center().release
        self.setVisible(bool(release));self.setProperty('update_available',bool(release))
        self.setToolTip(t('有可用更新')+' · v'+release['version'] if release else t('检查更新'));self.update()
    def _open(self):update_center().open(self.window())


class UpdateCheckButton(PushButton):
    def __init__(self,parent=None):
        super().__init__(parent);self.setText(t('检查更新'));self.setIcon(Icon.UPDATE);self.available=False
        from services.i18n import i18n_engine
        update_center().changed.connect(self.refresh)
        i18n_engine.language_changed.connect(self.refresh);self.refresh()
    def set_available(self,available):
        self.available=available;self.setProperty('update_available',available);self.refresh()
    def refresh(self,*_):
        center=update_center();release=center.release
        self.available=bool(release);self.setProperty('update_available',self.available)
        label='检查中…' if center.state=='checking' else '检查更新'
        if release:label='下载更新' if not release.get('manual_only') and (install_root()/MANIFEST).is_file() else '获取更新'
        self.setText(t(label));self.setEnabled(center.state!='checking')
        self.setToolTip(t('更新失败，请重试或打开发布页') if center.state=='error' else '')
        self.update()


class UpdateCenter(QObject):
    changed=Signal()
    def __init__(self,parent):
        super().__init__(parent);self.release=None;self.dialogs={};self.state='idle'
        self.auto_worker=None
        self.auto_service=None
        parent.aboutToQuit.connect(self.shutdown)

    @staticmethod
    def service():
        metadata=json.loads((install_root()/'version.json').read_text(encoding='utf-8'))
        return UpdateService(repository=metadata.get('update_repository',''),
                             asset_name=metadata.get('update_asset','NekoriEmojy_Release.zip'))

    def check_on_startup(self,config):
        """One background attempt per day, including failed network attempts."""
        if not config.get('auto_check_updates',True) or self.auto_worker is not None:
            return
        now=time.time()
        last=config.get('auto_update_last_attempt',0)
        if 0 <= now-last < 24*60*60:
            return
        from fluent_ui.components.update_dialog import UpdateWorker
        try:
            service=self.service()
            if not service.channel_available:return
            config.update({'auto_update_last_attempt':now,'auto_update_status':'checking'})
        except (OSError,ValueError,RuntimeError):
            # Preference IO failure must not prevent the main window starting.
            return
        self.auto_service=service
        self.set_check_state('checking')
        worker=UpdateWorker(lambda _:service.check(),self)
        self.auto_worker=worker
        def complete():
            self.auto_worker=None
            if worker.error or worker.cancelled:
                status='error'
                self.set_check_state(status)
            else:
                status=getattr(service,'last_check_status','available' if worker.result else 'current')
                self.set_release(worker.result)
                if status!='available':self.set_check_state(status)
            try:config.set('auto_update_status',status)
            except RuntimeError:pass
            worker.deleteLater()
        worker.finished.connect(complete)
        worker.start()

    def shutdown(self):
        if self.auto_worker is not None:
            self.auto_service.cancel.set()
            self.auto_worker.wait()

    def set_release(self,release):
        self.release=release;self.state='available' if release else 'current';self.changed.emit()

    def set_check_state(self,state):
        self.state=state
        if state in {'checking','error'}:self.release=None
        self.changed.emit()

    def open(self,owner):
        from fluent_ui.components.update_dialog import UpdateDialog
        owner=owner.window()
        if owner not in self.dialogs:
            service=self.service()
            dialog=UpdateDialog(owner,service)
            dialog.release_changed.connect(self.set_release)
            dialog.check_state_changed.connect(self.set_check_state)
            self.dialogs[owner]=dialog
        dialog=self.dialogs[owner]
        if self.release:
            dialog._checked(self.release);dialog.show();dialog.raise_();dialog.activateWindow()
        else:dialog.open_manual()
        return dialog


def update_center():
    app=QApplication.instance()
    if not hasattr(app,'_nekori_update_center'):app._nekori_update_center=UpdateCenter(app)
    return app._nekori_update_center
