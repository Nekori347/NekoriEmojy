"""User-initiated update state shared by Settings, About and the wordmark."""
import json
from PySide6.QtCore import QObject,Signal
from PySide6.QtWidgets import QApplication
from services.update_service import UpdateService,install_root
from fluent_ui.components.controls import TransparentToolButton
from fluent_ui.icons import Icon
from services.i18n import t


class UpdateBadge(TransparentToolButton):
    def __init__(self,parent=None):
        super().__init__(parent);self.setIcon(Icon.CLOUD_DOWNLOAD);self.setFixedSize(20,20)
        update_center().changed.connect(self.refresh)
        self.clicked.connect(self._open);self.refresh()
    def refresh(self):
        release=update_center().release
        self.setVisible(bool(release));self.setToolTip(t('可用更新')+(' · v'+release['version'] if release else ''))
    def _open(self):update_center().open(self.window())


class UpdateCenter(QObject):
    changed=Signal()
    def __init__(self,parent):
        super().__init__(parent);self.release=None;self.dialogs={}

    def set_release(self,release):
        self.release=release;self.changed.emit()

    def open(self,owner):
        from fluent_ui.components.update_dialog import UpdateDialog
        owner=owner.window()
        if owner not in self.dialogs:
            metadata=json.loads((install_root()/'version.json').read_text(encoding='utf-8'))
            service=UpdateService(repository=metadata.get('update_repository',''),asset_name=metadata.get('update_asset','NekoriEmojy_Release.zip'))
            dialog=UpdateDialog(owner,service)
            dialog.release_changed.connect(self.set_release)
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
