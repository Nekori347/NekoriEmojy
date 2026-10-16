"""Select a running Suzu instance and inspect its real data before migration."""
from services.i18n import t, bind_text, translated
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QListWidget, QListWidgetItem

from fluent_ui.components.dialogs import NekoriDialog
from fluent_ui.components.exchange_task_dialog import run_exchange_task


class SuzuInstanceDialog(NekoriDialog):
    def __init__(self, parent, service):
        super().__init__(parent, '从正在运行的 SuzuEmojy 迁移', code='SUZU → NEKORI')
        self.service = service
        self.selected_data_dir = None
        self.setMinimumSize(640, 420)
        self.add_hint(t('先启动要迁移的 Suzu，再从下方选择实例。迁移会复制数据到当前 Nekori 资源库。'))
        self.instances = QListWidget(self)
        self.instances.setMinimumHeight(130)
        self.instances.currentItemChanged.connect(self._preview)
        self.add_widget(self.instances)
        self.preview = translated(QLabel, '正在查找运行中的 Suzu…', self)
        self.preview.setWordWrap(True)
        self.preview.setTextFormat(Qt.PlainText)
        self.preview.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.add_widget(self.preview)
        self.add_hint(t('保留图片、分类、分类图标、Tag 和实际保存的顺序；缺失源文件会报告为跳过。原 Suzu 数据保持原样。'))
        self.add_button(t('取消'), on_click=self.reject)
        self.refresh_button = self.add_button(t('刷新实例'), on_click=self.refresh)
        self.import_button = self.add_button(t('导入 Nekori'), role='primary', on_click=self.accept, enabled=False)
        QTimer.singleShot(0, self.refresh)

    def refresh(self):
        self.instances.clear()
        self.import_button.setEnabled(False)
        self.selected_data_dir = None
        try:
            found = run_exchange_task(self, '查找正在运行的 SuzuEmojy',
                                      lambda progress: self.service.discover_instances())
        except Exception as error:
            self.preview.setText(str(error))
            return
        for instance in found:
            item = QListWidgetItem(f"{instance['title']} · PID {instance['pid']}\n{instance['executable']}")
            item.setData(Qt.UserRole, instance)
            self.instances.addItem(item)
        if found:
            self.instances.setCurrentRow(0)
        else:
            bind_text(self.preview, t('未找到运行中的 SuzuEmojy。请启动 Suzu 后刷新，或返回使用 Suzu ZIP 资源包迁移。'), 'setText')

    def _preview(self, item, previous=None):
        self.selected_data_dir = None
        self.import_button.setEnabled(False)
        if item is None:
            return
        instance = item.data(Qt.UserRole)
        if not instance['data_dir']:
            self.preview.setText(instance['error'])
            return
        try:
            preview = self.service.preview_data(instance['data_dir'])
        except Exception as error:
            self.preview.setText(str(error))
            return
        categories = '、'.join(preview['categories'][:12]) or t('无')
        bind_text(self.preview, t('数据来源：{value_0}\n\n{value_1} 项图片 · {value_2} 个分类 · {value_3} 项含 Tag · {value_4} 个分类图标\n{value_5} 项保存了顺序 · {value_6} 个源文件缺失\n分类：{value_7}').format(value_0=preview['data_dir'], value_1=preview['resources'], value_2=preview['nodes'], value_3=preview['tags'], value_4=preview['icons'], value_5=preview['ordered'], value_6=len(preview['missing']), value_7=categories), 'setText')
        self.selected_data_dir = instance['data_dir']
        self.import_button.setEnabled(True)
