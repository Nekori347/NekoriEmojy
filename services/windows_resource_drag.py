"""Local OLE adapter for resource dragging; targets still use Qt's drop events.

Only CF_HDROP/text expose files, through ResourceDragMimeData's disposable-copy
provider. IDataObject owns an immutable internal MIME snapshot and remains
usable if an asynchronous target retains it beyond the Qt source's lifetime.
No Shell feedback invokes application UI from inside an OLE callback.
"""
import os
import struct
import uuid
import ctypes

import pythoncom
import win32clipboard
import winerror
from win32com.server.exception import COMException
from win32com.server.util import NewEnum, wrap
from PySide6.QtCore import QCoreApplication, QUrl

RECYCLE_BIN = uuid.UUID('645ff040-5081-101b-9f08-00aa002f954e')


class ResourceDataObject:
    _com_interfaces_ = [pythoncom.IID_IDataObject]
    _public_methods_ = ('GetData GetDataHere QueryGetData GetCanonicalFormatEtc '
                        'SetData EnumFormatEtc DAdvise DUnadvise EnumDAdvise').split()

    def __init__(self, mime):
        self.files = mime._files
        self.target = None
        self.logical_effect = 0
        self.completed = False
        self.delivered_files = False
        self.target_format = win32clipboard.RegisterClipboardFormat('TargetCLSID')
        self.logical_format = win32clipboard.RegisterClipboardFormat('Logical Performed DropEffect')
        self.payloads = {
            win32clipboard.RegisterClipboardFormat(name): bytes(mime.data(name))
            for name in mime.formats() if name not in ('text/uri-list', 'text/plain')
        }
        preferred = win32clipboard.RegisterClipboardFormat('Preferred DropEffect')
        self.payloads[preferred] = struct.pack('<I', 1)  # default copy, retain supported Move
        self.has_files = mime.hasUrls()
        self.url_wide = win32clipboard.RegisterClipboardFormat('UniformResourceLocatorW')
        self.url_ansi = win32clipboard.RegisterClipboardFormat('UniformResourceLocator')
        # Match Qt's local URL/text representations, including older receivers.
        self.file_formats = [15, 13, 1, self.url_wide, self.url_ansi] if self.has_files else []

    def QueryGetData(self, format):
        cf, _, aspect, index, medium = format
        if cf not in self.payloads and cf not in self.file_formats:
            raise COMException(hresult=winerror.DV_E_FORMATETC)
        if aspect != pythoncom.DVASPECT_CONTENT or index != -1:
            raise COMException(hresult=winerror.DV_E_FORMATETC)
        if not medium & pythoncom.TYMED_HGLOBAL:
            raise COMException(hresult=winerror.DV_E_TYMED)

    def GetData(self, format):
        self.QueryGetData(format)
        cf = format[0]
        if cf in self.file_formats:
            files = self.files()
            self.delivered_files = bool(files)
        if cf == 15:
            names = '\0'.join(files) + '\0\0'
            body = struct.pack('<IiiII', 20, 0, 0, 0, 1) + names.encode('utf-16le')
        elif cf == 13:
            body = os.pathsep.join(files)
        elif cf == 1:
            body = os.pathsep.join(files).encode('mbcs', errors='replace') + b'\0'
        elif cf in (self.url_wide, self.url_ansi):
            url = QUrl.fromLocalFile(files[0]).toString() if files else ''
            body = (url.encode('utf-16le') + b'\0\0' if cf == self.url_wide
                    else url.encode('mbcs', errors='replace') + b'\0')
        else:
            body = self.payloads[cf]
        result = pythoncom.STGMEDIUM()
        # bytes is interpreted as a C string by pywin32 and appends a NUL.
        # A buffer preserves the exact binary MIME and CF_HDROP lengths.
        result.set(pythoncom.TYMED_HGLOBAL, memoryview(body) if isinstance(body, bytes) else body)
        return result

    def SetData(self, format, medium, release):
        # The pywin32 gateway handles STGMEDIUM ownership according to release.
        # Do not ReleaseStgMedium here or retain its borrowed memory.
        if self.completed or medium.tymed != pythoncom.TYMED_HGLOBAL:
            return
        cf = format[0]
        if cf == self.target_format:
            data = medium.data
            if len(data) >= 16:
                self.target = uuid.UUID(bytes_le=data[:16])
        elif cf == self.logical_format:
            data = medium.data
            if len(data) >= 4:
                self.logical_effect = struct.unpack('<I', data[:4])[0]

    def EnumFormatEtc(self, direction):
        if direction != pythoncom.DATADIR_GET:
            raise COMException(hresult=winerror.E_NOTIMPL)
        formats = list(self.payloads) + self.file_formats
        return NewEnum([(cf, None, 1, -1, 1) for cf in formats], iid=pythoncom.IID_IEnumFORMATETC)

    def GetDataHere(self, *args):
        raise COMException(hresult=winerror.E_NOTIMPL)

    def GetCanonicalFormatEtc(self, *args):
        raise COMException(hresult=winerror.E_NOTIMPL)

    def DAdvise(self, *args):
        raise COMException(hresult=winerror.OLE_E_ADVISENOTSUPPORTED)

    DUnadvise = DAdvise
    EnumDAdvise = DAdvise


class ResourceDropSource:
    _com_interfaces_ = [pythoncom.IID_IDropSource]
    _public_methods_ = ['QueryContinueDrag', 'GiveFeedback']

    def __init__(self, image=None):
        self.image = image
        self.released = False
        self.cancelled = False

    def QueryContinueDrag(self, escape, keys):
        if self.image:
            self.image.move()
        if escape:
            self.cancelled = True
            return winerror.DRAGDROP_S_CANCEL
        # Like Qt's QWindowsOleDropSource: OLE's grfKeyState can remain stale
        # when a button is released without further pointer movement. Qt event
        # dispatch can also consume the queued release while servicing timers.
        if not self.left_pressed():
            self.released = True
            return winerror.DRAGDROP_S_DROP
        QCoreApplication.processEvents()
        return winerror.S_OK

    @staticmethod
    def left_pressed():
        return bool(ctypes.windll.user32.GetAsyncKeyState(1) & 0x8000)

    def GiveFeedback(self, effect):
        if self.image:
            self.image.move()
        return winerror.DRAGDROP_S_USEDEFAULTCURSORS


class NativeDragImage:
    """The existing QDrag pixmap, displayed by Windows' standard drag image."""
    def __init__(self, pixmap, hotspot):
        import win32gui
        from PySide6.QtGui import QImage
        self.api = ctypes.WinDLL('comctl32')
        for name, args, result in (
            ('ImageList_BeginDrag', [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int], ctypes.c_int),
            ('ImageList_DragEnter', [ctypes.c_void_p, ctypes.c_int, ctypes.c_int], ctypes.c_int),
            ('ImageList_DragMove', [ctypes.c_int, ctypes.c_int], ctypes.c_int),
            ('ImageList_DragLeave', [ctypes.c_void_p], ctypes.c_int),
            ('ImageList_EndDrag', [], None),
        ):
            function = getattr(self.api, name)
            function.argtypes, function.restype = args, result
        image = pixmap.toImage().convertToFormat(QImage.Format_ARGB32_Premultiplied)
        width, height = image.width(), image.height()
        header = ctypes.create_string_buffer(struct.pack('<IiiHHIIiiII',
            40, width, -height, 1, 32, 0, image.sizeInBytes(), 0, 0, 0, 0))
        gdi = ctypes.WinDLL('gdi32', use_last_error=True)
        gdi.CreateDIBSection.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint,
                                       ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, ctypes.c_uint]
        gdi.CreateDIBSection.restype = ctypes.c_void_p
        bits = ctypes.c_void_p()
        bitmap = gdi.CreateDIBSection(None, header, 0, ctypes.byref(bits), None, 0)
        if not bitmap:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            ctypes.memmove(bits, bytes(image.constBits()), image.sizeInBytes())
            self.images = win32gui.ImageList_Create(width, height, 32, 1, 0)
            win32gui.ImageList_Add(self.images, bitmap, 0)
        finally:
            win32gui.DeleteObject(bitmap)
        self.api.ImageList_BeginDrag(self.images, 0, hotspot.x(), hotspot.y())
        x, y = win32gui.GetCursorPos()
        self.api.ImageList_DragEnter(None, x, y)

    def move(self):
        import win32gui
        self.api.ImageList_DragMove(*win32gui.GetCursorPos())

    def close(self):
        import win32gui
        self.api.ImageList_DragLeave(None)
        self.api.ImageList_EndDrag()
        win32gui.ImageList_Destroy(self.images)


def execute(drag):
    """Return recycle completion only after native DoDragDrop has unwound.

    Logical MOVE validates completion *after* the exact CLSID check; neither
    the return effect nor a missing exported file is used to infer identity.
    """
    data = ResourceDataObject(drag.mimeData())
    image = NativeDragImage(drag.pixmap(), drag.hotSpot()) if not drag.pixmap().isNull() else None
    source = ResourceDropSource(image)
    try:
        pythoncom.DoDragDrop(wrap(data, pythoncom.IID_IDataObject),
                             wrap(source, pythoncom.IID_IDropSource), 3)
        return (source.released and not source.cancelled
                and data.target == RECYCLE_BIN and data.logical_effect == 2
                and data.delivered_files and drag.mimeData().error is None)
    finally:
        data.completed = True  # late target feedback cannot affect another session
        if image:
            image.close()
