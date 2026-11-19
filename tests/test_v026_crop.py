from test_phase2_interaction import surface
from services.image_frames import normalized_crop,crop_image,frame_at
from fluent_ui.components.emoji_card import ThumbnailCache,_ThumbnailLoadTask
from fluent_ui.components.dialogs import FramePickerDialog
from PySide6.QtGui import QImage,QColor
from PySide6.QtCore import Qt,QPoint
from PySide6.QtTest import QTest


def test_first_interior_drag_creates_crop_without_persisting_on_cancel(surface):
    s=surface;path=s.paths[0];before=s.storage.resource_metadata(path)
    d=FramePickerDialog(s.g,s.storage,path);d.show();s.app.processEvents()
    rect=d.preview._image_rect
    start=QPoint(round(rect.left()+rect.width()*.2),round(rect.top()+rect.height()*.2))
    end=QPoint(round(rect.left()+rect.width()*.75),round(rect.top()+rect.height()*.8))
    QTest.mousePress(d.preview,Qt.LeftButton,pos=start)
    QTest.mouseMove(d.preview,end)
    QTest.mouseRelease(d.preview,Qt.LeftButton,pos=end)
    assert d.preview.crop and .15<d.preview.crop[0]<.25 and .7<d.preview.crop[2]<.8
    d.reject();assert s.storage.resource_metadata(path)==before
    d.deleteLater()


def test_crop_identity_shared_static_snapshots_and_cache(surface):
    s=surface;path=s.paths[0]
    image=QImage(100,50,QImage.Format_RGBA8888);image.fill(QColor('red'))
    for x in range(50,100):
        for y in range(50):image.setPixelColor(x,y,QColor('blue'))
    assert image.save(path)
    s.storage.set_resource_metadata(path,{'thumb_frame':0,'thumb_crop':[.5,0,1,1]})
    record=s.storage.resource_of(path)
    assert s.storage.representative_crop(record)==(.5,0.,1.,1.)
    assert ThumbnailCache.cache_key(path,64)!=ThumbnailCache.cache_key(path,64,crop=(.5,0,1,1))
    assert ThumbnailCache.cache_key(path,64,library_id='a')!=ThumbnailCache.cache_key(path,64,library_id='b')
    out=[];task=_ThumbnailLoadTask(path,64,1,crop=s.storage.representative_crop(path));task.signals.finished.connect(lambda p,img,*a:out.append(img));task.run()
    assert out[0].pixelColor(1,1).blue()==255
    node=s.storage.create_node('Crop snapshot');s.storage.set_node_icon(node,path)
    icon_path=s.storage.node_icon_path(node);assert QImage(icon_path).pixelColor(1,1).blue()==255
    full=s.storage.create_node('Explicit full image');s.storage.set_node_icon(full,path,crop=None)
    assert QImage(s.storage.node_icon_path(full)).pixelColor(1,1).red()==255
    s.storage.set_resource_metadata(path,{})
    assert s.storage.representative_crop(path) is None
    assert QImage(icon_path).pixelColor(1,1).blue()==255
    from services.app_icon import ApplicationIconService
    s.storage.set_resource_metadata(path,{'thumb_crop':[.5,0,1,1]})
    icon=ApplicationIconService(s.config,storage=s.storage).set_from_image(path)
    result=QImage(icon);assert result.pixelColor(result.width()//2,result.height()//2).blue()>240


def test_picker_resize_preserves_frame_and_metadata_reset(surface):
    s=surface;d=FramePickerDialog(s.g,s.storage,s.paths[4]);d.show();s.app.processEvents()
    rect=d.preview._image_rect;start=rect.topLeft().toPoint();target=start+QPoint(25,25)
    QTest.mousePress(d.preview,Qt.LeftButton,pos=start);QTest.mouseMove(d.preview,target);QTest.mouseRelease(d.preview,Qt.LeftButton,pos=target)
    assert d.preview.crop and d.preview.crop[0]>0 and d.preview.crop[1]>0
    crop=d.preview.crop;d.slider.setValue(1);assert d.preview.crop==crop;d._apply()
    assert s.storage.resource_metadata(s.paths[4])['thumb_frame']==1
    assert tuple(s.storage.resource_metadata(s.paths[4])['thumb_crop'])==crop
    reset=FramePickerDialog(s.g,s.storage,s.paths[4]);reset._reset()
    assert s.storage.representative_crop(s.paths[4]) is None
    assert s.storage.representative_frame(s.paths[4])==0
    d.deleteLater();reset.deleteLater()


def test_invalid_crop_is_ignored():
    for value in ([0,0,0,1],[0,0,float('nan'),1],[-1,0,1,1],{},[0,0,1,1]):assert normalized_crop(value) is None
