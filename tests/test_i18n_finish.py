"""Local regression seams for multilingual UI, color/layout and preview presentation."""
import json,string,time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
import pytest
from PySide6.QtWidgets import QApplication,QWidget,QLabel,QAbstractButton,QLineEdit
from PySide6.QtCore import Qt,QPoint,QRect
from PySide6.QtGui import QColor,QPixmap
from PySide6.QtTest import QTest
from services.config import ConfigService
from services.storage import StorageService
from services.i18n import i18n_engine,t
from fluent_ui import visual

@pytest.fixture
def case(tmp_path,monkeypatch):
 app=QApplication.instance() or QApplication([])
 monkeypatch.setenv('NEKORI_APP_DATA',str(tmp_path/'app'));monkeypatch.setenv('NEKORI_LIBRARY',str(tmp_path/'library'))
 cfg=ConfigService();i18n_engine.init(cfg);visual.theme.configure(cfg)
 yield SimpleNamespace(app=app,cfg=cfg,root=tmp_path)
 i18n_engine.load_language('zh')
 for w in app.topLevelWidgets():w.hide()
 app.processEvents()

def texts(root):
 return [w.text() for w in root.findChildren(QLabel)+root.findChildren(QAbstractButton)] + [w.placeholderText() for w in root.findChildren(QLineEdit)]

def test_tg_source_bindings_survive_language_switch_and_keep_user_data(case):
 from fluent_ui.views.tg_sticker_view import TGStickerInterface,TGHelpDialog
 v=TGStickerInterface();help=TGHelpDialog();v.urlInputEdit.setText('Custom_日本語_中文_Tag')
 image=QPixmap(12,12);image.fill(QColor('red'));v.detailPreviewLabel.setPixmap(image)
 v.detailInfoLabel.setText('User_日本語_emoji · 12 × 12')
 for lang in ('en','ja','zh_TW','zh'):
  i18n_engine.load_language(lang);case.app.processEvents()
  assert not [text for text in texts(v)+texts(help) if '[MISSING:' in text]
  assert v.urlInputEdit.text()=='Custom_日本語_中文_Tag'
  assert v.formatComboBox.itemData(0)=='png'
  assert not v.detailPreviewLabel.pixmap().isNull()
  assert v.detailInfoLabel.text()=='User_日本語_emoji · 12 × 12'
 v.deleteLater();help.deleteLater();case.app.processEvents()

def test_canonical_template_fields_match_in_four_dictionaries():
 fmt=string.Formatter()
 for lang in ('en','ja','zh_TW'):
  d=json.loads((Path(__file__).parents[1]/'translations'/(lang+'.json')).read_text(encoding='utf-8'))
  for source,target in d.items():
   try:fields=lambda text:{name for _,name,_,_ in fmt.parse(text) if name is not None};left,right=fields(source),fields(target)
   except ValueError:continue
   assert left==right,(lang,source,left,right)

def test_actual_category_confirmation_formats_and_cancels_without_tag_write(case):
 from fluent_ui.views.gallery_view import GalleryInterface
 from fluent_ui.components import dialogs
 owner=QWidget();storage=Mock();storage.node.return_value={'name':'User_日本語_分类'};storage.resources_in_subtree.return_value=[1,2]
 g=SimpleNamespace(storage=storage,tag_model=SimpleNamespace(names=lambda:['Tag_日本']),window=lambda:owner)
 for lang in ('zh','en','ja','zh_TW'):
  i18n_engine.load_language(lang)
  with patch.object(dialogs,'confirm',return_value=False) as confirm:
   GalleryInterface.apply_tags_to_category(g,'category',['Tag_日本'])
   body=confirm.call_args.args[2];assert 'User_日本語_分类' in body and '[MISSING:' not in body
 storage.apply_tags.assert_not_called()

def test_color_layout_hex_hsv_and_spectrum_drag(case):
 from fluent_ui.components.accent_picker import AccentColorPicker
 d=AccentColorPicker('#ff0000');d.show();case.app.processEvents()
 d.hex_editor.setFocus();d.hex_editor.selectAll();QTest.keyClicks(d.hex_editor,'#336699');case.app.processEvents()
 assert d.color.name()=='#336699' and d.comparison.current.name()=='#336699' and d.comparison.previous.name()=='#ff0000'
 assert d.comparison.mapTo(d,QPoint()).y()<d.hsv_sliders[0].mapTo(d,QPoint()).y()
 assert d.hex_editor.mapTo(d,QPoint()).x()>d.comparison.mapTo(d,QPoint()).x()
 d.hsv_sliders[0].setValue(180);assert d.hex_editor.text()==d.color.name().upper()
 changes=[];d.colorChanged.connect(lambda color:changes.append(color.name()))
 start=time.perf_counter();QTest.mousePress(d.spectrum,Qt.LeftButton,pos=QPoint(20,20))
 for x in range(25,225,5):QTest.mouseMove(d.spectrum,QPoint(x,40),1)
 QTest.mouseRelease(d.spectrum,Qt.LeftButton,pos=QPoint(225,40))
 assert len(changes)>10 and time.perf_counter()-start<2
 assert d.comparison.current==d.color
 d.reject()

def test_frame_picker_center_and_frame_actions(case):
 from PIL import Image
 from fluent_ui.components.dialogs import FramePickerDialog
 from services.resource_import import ImportTarget
 storage=StorageService(config=case.cfg);node=storage.create_node('Example')
 source=case.root/'a.gif';Image.new('RGB',(20,20),'red').save(source,save_all=True,append_images=[Image.new('RGB',(20,20),'blue')],duration=100,loop=0)
 path=storage.save_file(str(source),target=ImportTarget(node))[0]
 owner=QWidget();owner.resize(700,650);owner.move(30,30);owner.show()
 for lang in ('zh','en','ja','zh_TW'):
  i18n_engine.load_language(lang);d=FramePickerDialog(owner,storage,path);d.show();QTest.qWait(20)
  area=d.screen().availableGeometry();center=owner.frameGeometry().center()
  expected=QPoint(max(area.left(),min(center.x()-d.width()//2,area.right()-d.width()+1)),max(area.top(),min(center.y()-d.height()//2,area.bottom()-d.height()+1)))
  assert (d.pos()-expected).manhattanLength()<=2
  assert not [text for text in texts(d) if '[MISSING:' in text]
  d.slider.setValue(1);d._apply();assert storage.resource_metadata(path).get('thumb_frame')==1
  reset=FramePickerDialog(owner,storage,path);reset._reset();assert not storage.resource_metadata(path).get('thumb_frame')
  d.deleteLater();reset.deleteLater();case.app.processEvents()

def test_preview_information_order_long_text_and_animation(case):
 from PIL import Image
 from fluent_ui.components.hover_preview import HoverPreviewPopup
 source=case.root/'preview.gif';Image.new('RGB',(20,20),'red').save(source,save_all=True,append_images=[Image.new('RGB',(20,20),'blue')],duration=100,loop=0)
 pane=QWidget();pane.resize(700,650);pane.show();p=HoverPreviewPopup();p.apply_presentation(pane)
 info={'name':'用户的日本語.gif','path':'very long folder / '*20+'用户的日本語.gif','ocr_text':'笑嘻了 日本語 example '*20}
 p.show_preview(str(source),pane.mapToGlobal(QPoint(20,20)),320,'分类A, 分類B','TagA 日本語',info=info,container_rect=QRect(pane.mapToGlobal(QPoint()),pane.size()))
 QTest.qWait(120)
 assert p.meta_layout.itemAt(0).widget() is p.ocr_heading and p.ocr_label.text()==info['ocr_text'].strip()
 assert [item.name for item in p.tags._items]==['TagA','日本語']
 assert p.path_label.toolTip()==str(source.resolve()) and not p.path_label.wordWrap()
 assert p.ocr_label.height()<=p.ocr_label.fontMetrics().lineSpacing()*3
 assert p.current_movie is not None and p.current_movie.currentFrameNumber()>=0
 p.hide_preview();info['ocr_text']=''
 p.show_preview(str(source),pane.mapToGlobal(QPoint(20,20)),320,'','',info=info)
 assert p.ocr_heading.isHidden() and p.tags.isHidden()
 p.hide_preview();p.deleteLater();pane.close();case.app.processEvents()
