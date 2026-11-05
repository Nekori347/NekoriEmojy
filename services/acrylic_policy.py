"""Windows 10 Acrylic opt-in policy, independent of animation preferences."""
import sys

def is_windows10():
    return sys.platform == 'win32' and 10240 <= sys.getwindowsversion().build < 22000

def default_acrylic():return not is_windows10()

def allowed(config):
    return bool(config.get('window_acrylic_enabled',default_acrylic())) and (not is_windows10() or config.get('win10_acrylic_confirmed',False) is True)
