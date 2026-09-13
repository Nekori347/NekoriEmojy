"""Library selection is separate from business preferences and never creates implicitly."""
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QFileDialog, QMessageBox
from services.library import create_library, open_library, LibraryError


class LibraryDialog(QDialog):
    def __init__(self, parent=None, message="请选择一个独立资源库。图片和整理结果都保存在库中。"):
        super().__init__(parent)
        self.setWindowTitle("NekoriEmojy · 资源库")
        self.resize(500, 200)
        self.session = None
        layout = QVBoxLayout(self)
        label = QLabel(message)
        label.setWordWrap(True)
        layout.addWidget(label)
        for title, create in (("打开已有资源库", False), ("创建新资源库", True)):
            button = QPushButton(title)
            button.clicked.connect(lambda checked=False, create=create: self.select(create))
            layout.addWidget(button)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        layout.addWidget(cancel)

    def select(self, create):
        target = QFileDialog.getExistingDirectory(self, "选择空文件夹" if create else "选择已有资源库")
        if not target:
            return
        try:
            if create:
                create_library(target)
            self.session = open_library(target)
            self.accept()
        except (LibraryError, OSError) as exc:
            QMessageBox.warning(self, "资源库未连接", str(exc))


def choose_session(bootstrap, requested=None, parent=None):
    recent = requested or bootstrap.recent()
    message = "请选择一个独立资源库。图片和整理结果都保存在库中。"
    if recent:
        try:
            return open_library(recent)
        except LibraryError as exc:
            message = str(exc) + "\n原位置：" + str(recent)
    dialog = LibraryDialog(parent, message)
    return dialog.session if dialog.exec() == QDialog.Accepted else None
