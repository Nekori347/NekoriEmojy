"""User-triggered background identity repair with inspectable duplicate groups."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QListWidget, QListWidgetItem, QCheckBox, QMessageBox
from qfluentwidgets import PushButton
from fluent_ui.library_panel import LibraryJob
from services.maintenance import identity_report, similar_report


class MaintenanceDialog(QDialog):
    progress = Signal(int, int)

    def __init__(self, main_window):
        super().__init__(main_window.settings_window)
        self.main_window = main_window
        self.library = main_window.storage.session or main_window.storage.context
        self.job = None
        self.setWindowTitle('索引与重复图片')
        self.resize(620, 440)
        layout = QVBoxLayout(self)
        label = QLabel('检查已登记资源的索引；分类、顺序和标签保留。重复图片由你查看处理。')
        label.setWordWrap(True)
        layout.addWidget(label)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.list = QListWidget()
        layout.addWidget(self.list, 1)
        self.verify = QCheckBox('重新校验所有已登记图片的内容（需要读取图片）')
        layout.addWidget(self.verify)
        self.repair = PushButton('补全 / 修复索引')
        self.repair.clicked.connect(self.start_repair)
        layout.addWidget(self.repair)
        self.similar = PushButton('查找相似图片（后台，需人工确认）')
        self.similar.clicked.connect(lambda: self.start_repair(similar=True))
        layout.addWidget(self.similar)
        self.inspect = PushButton('在图库中选中这组重复图片')
        self.inspect.clicked.connect(self.inspect_group)
        layout.addWidget(self.inspect)
        self.progress.connect(lambda done, total: self.status.setText(f'已处理 {done} / {total}'))
        self.display(identity_report(self.library))

    def display(self, report):
        states = report['states']
        kind = '相似候选' if report.get('kind') == 'similar' else '完全重复'
        suffix = ' 检查已停止，结果不完整。' if report.get('cancelled') else ''
        self.status.setText(f"索引就绪 {states.get('ready',0)}，待补全 {states.get('unindexed',0)}，"
                            f"缺失 {states.get('missing',0)}，失败 {states.get('error',0)}；"
                            f"{kind} {len(report['duplicates'])} 组。" + suffix)
        self.list.clear()
        for number, names in enumerate(report['duplicates'], 1):
            item = QListWidgetItem(f'第 {number} 组 · {len(names)} 张图片')
            item.setData(Qt.UserRole, names)
            self.list.addItem(item)

    def start_repair(self, checked=False, *, similar=False):
        if self.job and self.job.isRunning():
            return
        verify_all = self.verify.isChecked()
        self.repair.setEnabled(False)
        self.similar.setEnabled(False)
        self.inspect.setEnabled(False)
        self.status.setText('正在检查索引…')
        operation = (lambda: similar_report(self.library, progress=self.progress.emit,
                                            cancel=lambda: self.job.isInterruptionRequested())) if similar else (
                     lambda: identity_report(self.library, repair=True, verify_all=verify_all, progress=self.progress.emit,
                                             cancel=lambda: self.job.isInterruptionRequested()))
        self.job = LibraryJob(operation, self)
        self.job.completed.connect(self.completed)
        self.job.start()

    def completed(self, report, error):
        self.repair.setEnabled(True)
        self.similar.setEnabled(True)
        self.inspect.setEnabled(True)
        if error:
            QMessageBox.warning(self, '索引修复未完成', str(error))
        else:
            self.display(report)
            self.main_window.storage.force_reload()
            self.main_window.gallery_interface.on_images_changed()

    def inspect_group(self):
        item = self.list.currentItem()
        if item is None:
            return
        gallery = self.main_window.gallery_interface
        gallery.set_category('全部表情')
        gallery.search_box.clear()
        gallery.search_keyword = ""
        gallery._search_timer.stop()
        from fluent_ui.views.gallery_view import FilterState
        gallery.filter_state = FilterState()
        gallery.set_selection_mode(True)
        gallery.selected_paths = {gallery.storage._to_abspath(name) for name in item.data(Qt.UserRole)}
        gallery.on_images_changed()
        self.main_window.show_gallery(refresh=False)
        self.close()

    def closeEvent(self, event):
        if self.job and self.job.isRunning():
            self.job.requestInterruption()
            self.status.setText('正在停止检查，请稍候…')
            event.ignore()
        else:
            super().closeEvent(event)
