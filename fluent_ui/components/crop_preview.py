"""Frame-picker crop interaction, retaining normalized resource coordinates."""
from PySide6.QtCore import Qt,QRectF,QPointF,Signal,QSize
from PySide6.QtGui import QPainter,QColor,QPen,QPixmap
from PySide6.QtWidgets import QLabel
from services.image_frames import normalized_crop

class CropPreview(QLabel):
    cropChanged=Signal()
    def __init__(self,parent=None,crop=None):
        super().__init__(parent);self.crop=normalized_crop(crop);self._pixmap=QPixmap();self._image_rect=QRectF();self._drag=None
        self.setMouseTracking(True)
    def set_frame(self,image):
        self._pixmap=QPixmap.fromImage(image).scaled(self.size()-QSize(8,8),Qt.KeepAspectRatio,Qt.SmoothTransformation)
        self._image_rect=QRectF((self.width()-self._pixmap.width())/2,(self.height()-self._pixmap.height())/2,self._pixmap.width(),self._pixmap.height());self.update()
    def reset_crop(self):self.crop=None;self.cropChanged.emit();self.update()
    def _rect(self):
        l,t,r,b=self.crop or (0,0,1,1);a=self._image_rect
        return QRectF(a.left()+l*a.width(),a.top()+t*a.height(),(r-l)*a.width(),(b-t)*a.height())
    def _handles(self):
        r=self._rect();return {'lt':r.topLeft(),'rt':r.topRight(),'lb':r.bottomLeft(),'rb':r.bottomRight(),'l':QPointF(r.left(),r.center().y()),'r':QPointF(r.right(),r.center().y()),'t':QPointF(r.center().x(),r.top()),'b':QPointF(r.center().x(),r.bottom())}
    def paintEvent(self,event):
        p=QPainter(self);p.fillRect(self.rect(),self.palette().window());p.drawPixmap(self._image_rect.topLeft(),self._pixmap)
        if self._pixmap.isNull():return
        a=self._image_rect;r=self._rect();shade=QColor(0,0,0,115)
        for box in (QRectF(a.left(),a.top(),a.width(),r.top()-a.top()),QRectF(a.left(),r.bottom(),a.width(),a.bottom()-r.bottom()),QRectF(a.left(),r.top(),r.left()-a.left(),r.height()),QRectF(r.right(),r.top(),a.right()-r.right(),r.height())):p.fillRect(box,shade)
        from fluent_ui.visual import colors
        p.setPen(QPen(QColor(colors()['accent']),1));p.drawRect(r)
        for point in self._handles().values():p.fillRect(QRectF(point.x()-3,point.y()-3,6,6),QColor(colors()['accent']))
    def mousePressEvent(self,event):
        if event.button()!=Qt.LeftButton or not self._image_rect.contains(event.position()):return super().mousePressEvent(event)
        pos=event.position();handle=next((name for name,p in self._handles().items() if abs(p.x()-pos.x())<=8 and abs(p.y()-pos.y())<=8),None)
        self._drag=(handle or ('move' if self.crop is not None and self._rect().contains(pos) else 'new'),pos,self.crop or (0,0,1,1));event.accept()
    def mouseMoveEvent(self,event):
        if not self._drag:return super().mouseMoveEvent(event)
        mode,start,original=self._drag;a=self._image_rect;pos=event.position();l,t,r,b=original;dx=(pos.x()-start.x())/a.width();dy=(pos.y()-start.y())/a.height()
        if mode=='move':
            dx=max(-l,min(1-r,dx));dy=max(-t,min(1-b,dy));l+=dx;r+=dx;t+=dy;b+=dy
        elif mode=='new':
            x=max(0,min(1,(start.x()-a.left())/a.width()));y=max(0,min(1,(start.y()-a.top())/a.height()));xx=max(0,min(1,(pos.x()-a.left())/a.width()));yy=max(0,min(1,(pos.y()-a.top())/a.height()));l,r=sorted((x,xx));t,b=sorted((y,yy))
        else:
            if 'l' in mode:l=max(0,min(r-.005,l+dx))
            if 'r' in mode:r=min(1,max(l+.005,r+dx))
            if 't' in mode:t=max(0,min(b-.005,t+dy))
            if 'b' in mode:b=min(1,max(t+.005,b+dy))
        if r-l>.001 and b-t>.001:self.crop=normalized_crop((l,t,r,b));self.cropChanged.emit();self.update()
        event.accept()
    def mouseReleaseEvent(self,event):
        if self._drag:self._drag=None;event.accept()
        else:super().mouseReleaseEvent(event)
