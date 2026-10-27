"""Keep the existing instance lock; a second process only requests activation."""
import hashlib
import os
import sys

from PySide6.QtCore import QObject, QSharedMemory
from PySide6.QtNetwork import QLocalServer, QLocalSocket


def instance_key():
    key = 'NekoriEmojy_App_Instance'
    if os.environ.get('NEKORI_APP_DATA'):
        from services.app_paths import app_data_dir
        key += '_' + hashlib.sha256(str(app_data_dir()).casefold().encode()).hexdigest()[:20]
    if '--smoke-test' in sys.argv:
        key += f'_Smoke_{os.getpid()}'
    return key


class SingleInstance(QObject):
    def __init__(self, parent=None, *, key=None):
        super().__init__(parent)
        self.key = key or instance_key()
        self.lock = QSharedMemory(self.key, self)
        self.server = QLocalServer(self)
        self.callback = None
        self.pending = False
        self.clients = set()
        self.server.newConnection.connect(self._connected)

    def start(self):
        if not self.lock.create(1):
            if self.lock.error() != QSharedMemory.AlreadyExists:
                raise RuntimeError(self.lock.errorString())
            self._notify()
            return False
        # Only the holder of the existing lock may remove an orphan endpoint.
        QLocalServer.removeServer(self.key)
        self.server.setSocketOptions(QLocalServer.UserAccessOption)
        if not self.server.listen(self.key):
            raise RuntimeError(self.server.errorString())
        return True

    def _notify(self):
        client = QLocalSocket()
        client.connectToServer(self.key)
        if not client.waitForConnected(1500):
            print('[WARNING] Existing instance is not ready for activation.')
            return
        if client.waitForReadyRead(1500):
            pid = bytes(client.readLine()).strip()
            if sys.platform == 'win32' and pid.isdigit():
                import ctypes
                # A user-launched foreground process can grant the owner one
                # activation attempt. No topmost flag or focus retry loop.
                ctypes.windll.user32.AllowSetForegroundWindow(int(pid))
        client.write(b'activate\n')
        client.waitForBytesWritten(1500)
        client.disconnectFromServer()

    def _connected(self):
        while self.server.hasPendingConnections():
            client = self.server.nextPendingConnection()
            self.clients.add(client)
            client.write(f'{os.getpid()}\n'.encode())
            client.readyRead.connect(lambda c=client: self._read(c))
            client.disconnected.connect(lambda c=client: self._disconnected(c))
            self._read(client)

    def _read(self, client):
        while client.canReadLine():
            if bytes(client.readLine()).strip() == b'activate':
                if self.callback:
                    self.callback()
                else:
                    self.pending = True

    def _disconnected(self, client):
        self.clients.discard(client)
        client.deleteLater()

    def set_window(self, window):
        self.callback = lambda: activate_window(window)
        if self.pending:
            self.pending = False
            self.callback()


def activate_window(window):
    from PySide6.QtCore import Qt
    window.show_main_panel()
    if window.isMinimized():
        window.setWindowState(window.windowState() & ~Qt.WindowMinimized)
    window.raise_()
    window.activateWindow()
