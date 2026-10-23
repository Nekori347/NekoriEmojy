"""QQ discovery, cancellation and preview boundaries on disposable input."""
import os,time
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest
from PySide6.QtCore import QEventLoop,QTimer,Qt
from PySide6.QtGui import QImage,QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication


@pytest.fixture
def qq(tmp_path,monkeypatch):
    from services.config import ConfigService
    from services.i18n import i18n_engine
    from services.qq_extractor import QQExtractor
    from fluent_ui import visual
    from fluent_ui.views.qq_scan_view import QQScanInterface
    root=tmp_path/'Tencent Files'
    for account in ('800001','800002'):
        (root/account/'nt_qq/nt_data/Emoji/personal_emoji/Ori').mkdir(parents=True)
    monkeypatch.setattr(QQExtractor,'get_nickname_cache_path',staticmethod(lambda:str(tmp_path/'nicknames.json')))
    app=QApplication.instance() or QApplication([])
    config=ConfigService(tmp_path/'app');config.config.update(qq_data_path=str(root))
    visual.theme.configure(config);i18n_engine.init(config)
    view=QQScanInterface(config_service=config);view.resize(1000,720);view.show()
    wait(lambda:view.userComboBox.count()==2)
    yield view,root,app
    view.shutdown();view.hide()
    wait(lambda:not view._discovery_workers)
    wait(lambda:not getattr(view,'_background_workers',[]))
    view.deleteLater();app.processEvents()


def wait(predicate,seconds=8):
    if predicate():return
    # Let Qt release the GIL as it does in the actual application event loop.
    loop=QEventLoop();poll=QTimer();deadline=QTimer();deadline.setSingleShot(True)
    poll.timeout.connect(lambda:loop.quit() if predicate() else None)
    deadline.timeout.connect(loop.quit);poll.start(10);deadline.start(int(seconds*1000))
    loop.exec();poll.stop();deadline.stop()
    assert predicate(),'QQ condition timed out'


def test_selected_account_directory_and_reopen(qq,monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    view,root,app=qq
    monkeypatch.setattr(QFileDialog,'getExistingDirectory',lambda *a,**kw:str(root/'800002'))
    view.selectReadPath()
    wait(lambda:not view._discovery_workers)
    assert view.userComboBox.count()==2
    assert view.get_selected_qq()=='800002'
    assert view.userdata_save_path_cache==str(root)
    view.shutdown();view.hide();view.show()
    view.populateUserComboBox()
    wait(lambda:not view._discovery_workers)
    assert not view._discovery_closed and view.userComboBox.isEnabled()
    assert view.emojiFolderComboBox.isEnabled() and view.scanButton.isEnabled()


def test_first_discovered_items_show_their_labels(qq):
    view,root,app=qq
    wait(lambda:not view._discovery_workers)
    for combo in (view.userComboBox,view.emojiFolderComboBox):
        assert combo.currentIndex()==0
        assert combo.text()==combo.itemText(0)


def test_scan_cancel_reaches_real_file_loop(tmp_path,monkeypatch):
    from services.qq_extractor import QQExtractor
    from fluent_ui.views.qq_scan_view import QQScanWorker
    source=tmp_path/'Ori';source.mkdir()
    image=QImage(24,24,QImage.Format_RGB32);image.fill(QColor('red'))
    for i in range(40):image.save(str(source/f'face{i:03d}.png'))
    worker=QQScanWorker(tmp_path,'personal_emoji');seen=[]
    original=QQExtractor.get_actual_extension
    def inspect(path):
        seen.append(path)
        if len(seen)==5:worker.cancel()
        return original(path)
    monkeypatch.setattr(QQExtractor,'get_actual_extension',staticmethod(inspect))
    worker.run()
    assert len(seen)<=5
    assert worker.was_cancelled


def test_discovery_new_path_wins_and_empty_path_finishes(qq,monkeypatch,tmp_path):
    from services.qq_extractor import QQExtractor
    view,root,app=qq
    original=QQExtractor.get_numeric_subdirectories
    def discover(path):
        if str(path)==str(root):time.sleep(.1)
        return original(path)
    monkeypatch.setattr(QQExtractor,'get_numeric_subdirectories',staticmethod(discover))
    view.populateUserComboBox()
    other=tmp_path/'Other drive data'
    (other/'800003/nt_qq/nt_data/Emoji/personal_emoji').mkdir(parents=True)
    view.userdata_save_path_cache=str(other);view.populateUserComboBox()
    wait(lambda:not view._discovery_workers)
    assert view.userComboBox.count()==1 and view.get_selected_qq()=='800003'
    assert view.readPathEdit.text()==str(other)
    empty=tmp_path/'Empty';empty.mkdir()
    view.userdata_save_path_cache=str(empty);view.populateUserComboBox()
    wait(lambda:not view._discovery_workers)
    assert view.userComboBox.count()==0 and view.userComboBox.isEnabled()
    assert not view.scanButton.isEnabled() and '读取' not in view.userComboBox.text()


def test_preview_close_discards_work_and_reopen_loads(qq,tmp_path):
    view,root,app=qq
    image=QImage(512,512,QImage.Format_RGB32);image.fill(QColor('blue'))
    source=root/'800001/nt_qq/nt_data/Emoji/personal_emoji/Ori'
    files=[]
    for i in range(60):
        path=source/f'face{i:03d}.png';image.save(str(path));files.append(str(path))
    view.emoji_file_paths=files;view.loadMoreEmojis()
    start=time.monotonic();view.shutdown();elapsed=time.monotonic()-start
    assert elapsed<.1
    wait(lambda:not view._background_workers)
    assert view.previewListWidget.count()==0
    view.hide();view.show()
    wait(lambda:view.previewListWidget.count()==60)
    assert view.loaded_emoji_count==60 and not view.is_loading


def test_scan_stop_action_and_close_do_not_apply_old_results(qq,monkeypatch):
    from services.qq_extractor import QQExtractor
    view,root,app=qq
    folder=root/'800001/nt_qq/nt_data/Emoji/personal_emoji/Ori'
    image=QImage(24,24,QImage.Format_RGB32);image.fill(QColor('green'))
    for i in range(50):image.save(str(folder/f'face{i:03d}.png'))
    original=QQExtractor.get_actual_extension;seen=[]
    def slow_read(path):
        seen.append(path);time.sleep(.01);return original(path)
    monkeypatch.setattr(QQExtractor,'get_actual_extension',staticmethod(slow_read))
    wait(lambda:view.scanButton.isEnabled())
    QTest.mouseClick(view.scanButton,Qt.LeftButton)
    wait(lambda:bool(seen))
    action=view.tooltip.host.action_button
    assert action.isEnabled() and not action.isHidden()
    QTest.mouseClick(action,Qt.LeftButton)
    wait(lambda:view._current_worker is None)
    assert not view.emoji_file_paths and len(seen)<50
    seen.clear();QTest.mouseClick(view.scanButton,Qt.LeftButton);wait(lambda:bool(seen))
    start=time.monotonic();view.shutdown()
    assert time.monotonic()-start<.1
    wait(lambda:not view._background_workers)
    assert not view.emoji_file_paths and view.previewListWidget.count()==0


def test_preview_marketface_and_apng_keep_animation(qq,tmp_path,monkeypatch):
    from PIL import Image
    from services.qq_extractor import QQExtractor
    from services import marketface_handler
    view,root,app=qq
    cache=tmp_path/'gif-cache';cache.mkdir()
    monkeypatch.setattr(marketface_handler,'get_cache_dir',lambda:str(cache))
    monkeypatch.setattr(QQExtractor,'get_temp_gif_cache_dir',staticmethod(lambda:str(cache)))
    first=Image.new('RGBA',(24,24),'red');second=Image.new('RGBA',(24,24),'blue')
    gif=tmp_path/'animated.gif';first.save(gif,save_all=True,append_images=[second],duration=80,loop=0)
    encrypted=tmp_path/'marketface.dat'
    data=marketface_handler.restore_marketface(gif.read_bytes());encrypted.write_bytes(data)
    view.emojiFolderComboBox.addItem('Marketface',userData='marketface')
    view.emojiFolderComboBox.setCurrentIndex(view.emojiFolderComboBox.count()-1)
    view.emoji_file_paths=[str(encrypted)];view.loadMoreEmojis()
    wait(lambda:view.previewListWidget.count()==1)
    item=view.previewListWidget.item(0)
    assert item.data(Qt.UserRole+1) and not item.icon().isNull()
    assert encrypted.read_bytes()==data
    view._clear_results()
    index=view.emojiFolderComboBox.findData('personal_emoji');view.emojiFolderComboBox.setCurrentIndex(index)
    apng=tmp_path/'animated.png';first.save(apng,save_all=True,append_images=[second],duration=80,loop=0)
    view.emoji_file_paths=[str(apng)];view.loadMoreEmojis()
    wait(lambda:view.previewListWidget.count()==1)
    item=view.previewListWidget.item(0)
    assert item.data(Qt.UserRole+1) and 'APNG' in item.toolTip()
    view.previewListWidget.setCurrentRow(0)
    assert view.detail_movie is not None and view.detail_movie.isValid()
