"""One shared nonblocking voice for UI events and their settings previews."""
from pathlib import Path
from PySide6.QtCore import QObject, QUrl, Signal, Slot, Qt, QThread


SOUNDS=Path(__file__).resolve().parents[1]/'fluent_ui/assets/sounds'
DEFAULT_SOUND=SOUNDS/'zen-press.wav'
DEFAULT_IMPORT_SOUND=SOUNDS/'zen-uncheck.wav'
EVENT_SOUNDS={'send':DEFAULT_SOUND,'import':DEFAULT_IMPORT_SOUND,
              'delete':SOUNDS/'zen-reorder.wav','reorder':SOUNDS/'zen-typing.wav',
              'category':SOUNDS/'zen-swipe.wav'}


class OperationSounds(QObject):
    """Marshal worker results to the existing single GUI-thread sound voice."""
    submitted=Signal(str)
    def __init__(self,config,parent):
        super().__init__(parent);self.config=config
        self.submitted.connect(self._play,Qt.QueuedConnection)

    def submit(self,event):
        if QThread.currentThread()==self.thread():self._play(event)
        else:self.submitted.emit(event)

    @Slot(str)
    def _play(self,event):
        try:sound_for(self.config).play(self.config,event=event)
        except Exception:
            # A notification sound can never alter an already committed result.
            import logging
            logging.getLogger('nekori.sound').exception('Optional result sound failed: %s',event)


def install_operation_sounds(config):
    from PySide6.QtWidgets import QApplication
    app=QApplication.instance()
    if app is not None and QThread.currentThread()==app.thread() and not hasattr(config,'operation_sounds'):
        config.operation_sounds=OperationSounds(config,app)
    return getattr(config,'operation_sounds',None)


def completed_sound(config,event,changed=True):
    """One semantic result, not a signal for arbitrary membership/position writes."""
    if config is None or not changed or event not in EVENT_SOUNDS:return
    from fluent_ui.components.drop_contract import current_drop_operation
    operation=current_drop_operation()
    if event=='reorder' and operation is None:return  # drag sorting only
    if operation is not None:
        # A single operation owns one final cue. Wait for complete(), including
        # any deferred membership choice, before touching the audio backend.
        priority={'reorder':0,'category':1,'import':2,'delete':3,'send':4}
        pending=operation.result_sound
        if pending is None or priority[event]>priority[pending[1]]:
            operation.result_sound=(config,event)
        return
    dispatcher=install_operation_sounds(config)
    if dispatcher is not None:dispatcher.submit(event)


def flush_operation_sound(operation):
    pending,operation.result_sound=operation.result_sound,None
    if pending is not None:
        config,event=pending
        dispatcher=install_operation_sounds(config)
        if dispatcher is not None:dispatcher.submit(event)


def sound_for(config):
    from PySide6.QtWidgets import QApplication
    if not hasattr(config,'ui_sound'):config.ui_sound=SendSound(QApplication.instance())
    return config.ui_sound


def perceptual_volume(percent):
    from PySide6.QtMultimedia import QAudio
    value=max(0,min(100,float(percent)))/100
    return QAudio.convertVolume(value,QAudio.VolumeScale.LogarithmicVolumeScale,QAudio.VolumeScale.LinearVolumeScale)


class SendSound(QObject):
    preview_changed = Signal(str)
    preview_failed = Signal(str, str)

    def __init__(self,parent=None):
        super().__init__(parent)
        self.effect=None
        self.preview_event=''

    def _set_preview(self, event):
        if event != self.preview_event:
            self.preview_event=event
            self.preview_changed.emit(event)

    def stop_preview(self):
        if not self.preview_event:return
        try:
            if self.effect is not None:self.effect.stop()
        except RuntimeError:
            pass
        self._set_preview('')

    def _preview_error(self, event):
        self.stop_preview()
        self.preview_failed.emit(event,'无法试听此音效，请选择可用的 WAV 文件。')

    def _playing_changed(self):
        if not self.effect.isPlaying():self._set_preview('')

    def _status_changed(self):
        from PySide6.QtMultimedia import QSoundEffect
        if self.preview_event and self.effect.status()==QSoundEffect.Status.Error:
            self._preview_error(self.preview_event)

    def play(self,config,*,event='send',preview=False,path=None,volume=None):
        if event not in EVENT_SOUNDS:return
        prefix=event
        if not preview and not config.get(prefix+'_sound_enabled',False):return
        try:
            source=Path(path if path is not None else config.get(prefix+'_sound_path',''))
            if str(source)=='.':source=EVENT_SOUNDS[event]
            if not source.is_file():
                if preview:self._preview_error(event)
                return
            if self.effect is None:
                from PySide6.QtMultimedia import QSoundEffect
                self.effect=QSoundEffect(self);self.effect.setLoopCount(1)
                self.effect.playingChanged.connect(self._playing_changed)
                self.effect.statusChanged.connect(self._status_changed)
            self.effect.stop()
            self._set_preview(event if preview else '')
            self.effect.setVolume(perceptual_volume(config.get('sound_volume',85) if volume is None else volume))
            url=QUrl.fromLocalFile(str(source.resolve()))
            if self.effect.source()!=url:self.effect.setSource(url)
            if preview:
                # A cached failed source may not emit another statusChanged.
                self._status_changed()
                if self.preview_event != event:return
            self.effect.play()
        except (RuntimeError,ImportError,OSError,ValueError,TypeError):
            # Audio is optional; it must never change a completed send result.
            if preview:self._preview_error(event)
