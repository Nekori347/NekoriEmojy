"""Resource exchange uses the same editorial groups as Settings."""
from services.i18n import t, bind_text, translated
import os
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QFrame, QFileDialog
from fluent_ui.components.controls import TransparentToolButton
from fluent_ui.icons import Icon as FIF
from fluent_ui import visual
from fluent_ui.components import dialogs
from fluent_ui.components.setting_rows import ActionRow, SettingSection, apply_row_theme
from services.i18n import t, i18n_engine


class ExchangeInterface(QWidget):
    back_requested = Signal()
    import_requested = Signal()
    export_all_requested = Signal()
    export_selected_requested = Signal()
    qq_scan_requested = Signal()
    tg_sticker_requested = Signal()
    nekori_export_requested = Signal()
    nekori_import_requested = Signal()
    suzu_data_migration_requested = Signal()
    suzu_package_migration_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('ExchangeInterface')
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 8, 20, 12)
        root.setSpacing(14)
        header = QHBoxLayout()
        self.btnBack = TransparentToolButton(FIF.LEFT_ARROW, self)
        bind_text(self.btnBack, t('返回表情库'), 'setToolTip')
        self.btnBack.clicked.connect(self.back_requested.emit)
        header.addWidget(self.btnBack)
        self.titleLabel = translated(QLabel, '导入与导出', self)
        self.titleLabel.setProperty('role', 'title')
        self.titleLabel.setStyleSheet('font-size: 22px; font-weight: 600;')
        header.addWidget(self.titleLabel)
        header.addStretch()
        root.addLayout(header)
        self.scrollArea = QScrollArea(self)
        self.scrollArea.setFrameShape(QFrame.NoFrame)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setStyleSheet('QScrollArea { background: transparent; border: none; }')
        self.scrollWidget = QWidget()
        self.scrollWidget.setObjectName('ExchangeBody')
        self.groups = QVBoxLayout(self.scrollWidget)
        self.groups.setContentsMargins(0, 0, 8, 8)
        self.groups.setSpacing(16)
        self.scrollArea.setWidget(self.scrollWidget)
        root.addWidget(self.scrollArea)
        self.nativeGroup = self._group('Nekori 表情合集')
        self.nativeExportCard = self._row(self.nativeGroup, '导出整理结果', '表情、分类树、图标、标签与分类内混排顺序。', '导出…', self.nekori_export_requested.emit)
        self.nativeImportCard = self._row(self.nativeGroup, '导入 Nekori 表情合集', '恢复整理结果，并合并重复表情的分类关系。', '导入…', self.nekori_import_requested.emit)
        self.migrationGroup = self._group('从 SuzuEmojy 单向迁移')
        self.suzuDataCard = self._row(self.migrationGroup, '正在运行的 Suzu', '选择运行实例，预览其实际数据后导入 Nekori。', '查找实例…', self.suzu_data_migration_requested.emit)
        self.suzuPackageCard = self._row(self.migrationGroup, 'Suzu ZIP 表情合集', '迁移包内真实携带的表情、分类、图标与 Tag。', '选择 ZIP…', self.suzu_package_migration_requested.emit)
        self.resourceGroup = self._group('Suzu 分享包')
        self.importCard = self._row(self.resourceGroup, '导入分享包', '读取平面分类和表情，并自动去重。', '导入…', self.import_requested.emit)
        self.exportAllCard = self._row(self.resourceGroup, '导出全部表情', '导出为 Suzu 平面分享格式。需要完整节点树时请使用 Nekori 表情合集。', '导出全部…', self.export_all_requested.emit)
        self.exportSelectedCard = self._row(self.resourceGroup, '导出指定分类', '选择要分享的分类。', '选择分类…', self.export_selected_requested.emit)
        self.splitCard = self._row(self.resourceGroup, '表情合集分卷', '按完整表情切分，每卷不超过 100 MB。', '选择表情合集…', self._split_package)
        self.thirdPartyGroup = self._group('其他来源')
        self.qqScanCard = self._row(self.thirdPartyGroup, 'QQ 表情缓存', '扫描本地缓存并导入已有表情。', '扫描…', self.qq_scan_requested.emit)
        self.tgStickerCard = self._row(self.thirdPartyGroup, 'Telegram 表情', '下载表情并转换表情格式。', '打开…', self.tg_sticker_requested.emit)
        self.groups.addStretch()
        self.refresh_theme()
        visual.theme.changed.connect(self.refresh_theme)

    def _group(self, title):
        group = SettingSection(title, self.scrollWidget)
        self.groups.addWidget(group)
        return group

    def _row(self, group, title, hint, button, callback):
        row = ActionRow(title, hint, [(button, callback, False)], group)
        group.add_row(row)
        return row

    def refresh_theme(self):
        self.setStyleSheet(visual.settings_style() + 'QWidget#ExchangeBody { background: transparent; }')
        apply_row_theme(self)

    def _split_package(self, owner=None):
        owner = owner or self.window()
        from fluent_ui.components.feedback import feedback_for
        from services.exchange_split import split_package
        from fluent_ui.components.exchange_task_dialog import run_exchange_task

        source, _ = QFileDialog.getOpenFileName(
            owner, t("表情合集切割分卷"), "", "ZIP (*.zip)"
        )
        if not source:
            return
        output = QFileDialog.getExistingDirectory(
            owner, t("选择分卷保存文件夹"), os.path.dirname(source)
        )
        if not output:
            return
        try:
            destination, paths = run_exchange_task(
                owner, t("正在切割表情合集"),
                lambda progress: split_package(source, output, progress),
            )
            feedback_for(owner).toast( t("分卷完成"),
                t("已生成 {count} 个分卷，每卷不超过 100 MB，表情内容保持不变。\n保存位置：{path}\n请通过“导入表情合集”逐卷导入，分类会自动合并。").format(
                    count=len(paths), path=destination,
                ),
            )
        except Exception as exc:
            feedback_for(owner).notice(t("分卷失败"), str(exc), error=True)

