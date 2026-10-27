"""Real IPC processes, with the production guard before any Library startup."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def test_second_process_wakes_owner_without_loading_library(tmp_path):
    env=dict(os.environ, NEKORI_APP_DATA=str(tmp_path/'app'), QT_QPA_PLATFORM='offscreen')
    state=tmp_path/'state.json'
    program='''
import json,sys
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QWidget
from services.single_instance import SingleInstance
app=QApplication([]);app.setQuitOnLastWindowClosed(False)
guard=SingleInstance(app)
assert guard.start()
class Window(QWidget):
    def show_main_panel(self):self.show()
w=Window();w.resize(300,200);guard.set_window(w)
state=Path(sys.argv[1]);steps=[]
def step():
    command=state.read_text() if state.exists() else ''
    if command=='quit':app.quit();return
    if command in ('hide','minimize','show'):
        getattr(w,{'hide':'hide','minimize':'showMinimized','show':'show'}[command])()
        state.write_text(json.dumps(dict(pid=__import__('os').getpid(),ready=True)))
    elif command=='inspect':
        state.write_text(json.dumps(dict(visible=w.isVisible(),minimized=w.isMinimized())))
timer=QTimer();timer.timeout.connect(step);timer.start(10)
state.write_text('show')
app.exec()
'''
    owner=subprocess.Popen([sys.executable,'-c',program,str(state)],env=env)
    def wait(predicate):
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            if predicate():return
            time.sleep(.02)
        raise AssertionError('owner did not respond')
    def report():
        try:return json.loads(state.read_text())
        except (OSError,ValueError):return {}
    try:
        wait(lambda:report().get('ready'))
        for mode in ('show','minimize','hide'):
            state.write_text(mode);wait(lambda:report().get('ready'))
            # Actual main.py exits through the guard, before storage imports.
            result=subprocess.run([sys.executable,'main.py'],env=env,timeout=12,capture_output=True)
            assert result.returncode==0,result.stderr.decode(errors='replace')
            state.write_text('inspect');wait(lambda:'visible' in report())
            assert report()==dict(visible=True,minimized=False)
            assert owner.poll() is None
    finally:
        state.write_text('quit');owner.wait(timeout=8)
    # The old owner released the lock and endpoint; normal cold start possible.
    state.unlink()
    owner=subprocess.Popen([sys.executable,'-c',program,str(state)],env=env)
    try:wait(lambda:report().get('ready'))
    finally:state.write_text('quit');owner.wait(timeout=8)
