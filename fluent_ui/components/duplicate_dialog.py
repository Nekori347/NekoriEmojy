"""Compare the real duplicate candidates, streaming animated frames with Pillow."""
from pathlib import Path
from PySide6.QtCore import Qt,QTimer
from PySide6.QtGui import QImage,QPixmap
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel
from services.i18n import t,translated
from fluent_ui.components.hover_preview import PreviewImage
from fluent_ui.components.dialogs import NekoriDialog


class CandidatePreview(PreviewImage):
    def __init__(self,source,parent=None):
        super().__init__(parent);self.setMinimumSize(220,200);self.setMaximumHeight(320)
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.timeout.connect(self.advance)
        self.image=None;self.frame=0;self.first=0
        if isinstance(source,QImage):
            self.setPixmap(QPixmap.fromImage(source));self.description=f'{source.width()} × {source.height()}';return
        from PIL import Image
        try:
            self.image=Image.open(source);self.first=int(bool(self.image.info.get('default_image')))
            self.frame=self.first;self.description=f'{Path(source).name}\n{self.image.width} × {self.image.height} · {Path(source).stat().st_size/1024:.1f} KiB'
            self.advance()
        except Exception:
            self.description=Path(source).name;self.setText(t('无法预览'))

    def advance(self):
        if self.image is None:return
        try:
            self.image.seek(self.frame)
            duration=max(20,int(self.image.info.get('duration',100) or 100))
            image=self.image.convert('RGBA');image.thumbnail((320,300))
            qimage=QImage(image.tobytes(),image.width,image.height,QImage.Format_RGBA8888).copy()
            self.setPixmap(QPixmap.fromImage(qimage));self.update()
            if getattr(self.image,'n_frames',1)>1:
                self.frame+=1
                if self.frame>=self.image.n_frames:self.frame=self.first
                self.timer.start(duration)
        except Exception:self.stop()

    def stop(self):
        self.timer.stop()
        if self.image:self.image.close();self.image=None


class DuplicateDialog(NekoriDialog):
    def __init__(self,parent,existing,incoming,decide):
        super().__init__(parent,t('发现重复表情'))
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setModal(False);self.setWindowModality(Qt.NonModal);self.resize(700,430)
        self.set_semantic('warning');self.previews=[];row=QHBoxLayout()
        for title,source in [('已有表情',existing),('本次导入',incoming)]:
            column=QWidget(self);layout=QVBoxLayout(column)
            layout.addWidget(translated(QLabel,title,column))
            preview=CandidatePreview(source,column);self.previews.append(preview);layout.addWidget(preview,1)
            info=QLabel(preview.description,column);info.setWordWrap(True);layout.addWidget(info);row.addWidget(column,1)
        self.body.addLayout(row)
        self.choice='skip'
        self.add_button('保留两张',on_click=lambda:self.select('keep'))
        self.add_button('替换已有',role='danger',on_click=lambda:self.select('replace'))
        cancel=self.add_button('取消本张导入',on_click=self.reject);cancel.setDefault(True);cancel.setFocus()
        self.finished.connect(lambda *_:self._finish(decide))

    def select(self,choice):self.choice=choice;self.accept()

    def _finish(self,decide):
        for preview in self.previews:preview.stop()
        decide(self.choice)
