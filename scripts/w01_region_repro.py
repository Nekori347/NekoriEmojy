"""Pure Win32 repro: window region versus Accent Acrylic; no Qt or Nekori host."""
import ctypes, time, json, sys, argparse
from ctypes import wintypes as wt
from pathlib import Path
import win32gui as g, win32con as c, win32api
from PIL import ImageGrab
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[2]/'DevData/post-021-wpa/w01-native-repro')
parser.add_argument('--hold',type=float,default=0,help='Seconds to keep each comparison window visible')
args=parser.parse_args()
OUT=args.output;OUT.mkdir(parents=True,exist_ok=True)
ctypes.windll.user32.SetProcessDPIAware()
def proc(h,m,w,l):
    if m==c.WM_NCCALCSIZE:return 0
    if m==c.WM_PAINT:g.ValidateRect(h,None);return 0
    return g.DefWindowProc(h,m,w,l)
klass=g.WNDCLASS();klass.lpfnWndProc=proc;klass.lpszClassName='NekoriW01NativeRegionProbe'
klass.hInstance=win32api.GetModuleHandle(None);g.RegisterClass(klass)
brush=g.CreateSolidBrush(win32api.RGB(255,0,255))
def board_proc(h,m,w,l):
    if m==c.WM_ERASEBKGND:g.FillRect(w,g.GetClientRect(h),brush);return 1
    return g.DefWindowProc(h,m,w,l)
bgklass=g.WNDCLASS();bgklass.lpfnWndProc=board_proc;bgklass.lpszClassName='NekoriW01ProbeBoard'
bgklass.hInstance=klass.hInstance;bgklass.hbrBackground=g.CreateSolidBrush(win32api.RGB(255,0,255));g.RegisterClass(bgklass)
# Prefer a secondary monitor when available; no application or user data is loaded.
monitor=next((win32api.GetMonitorInfo(h) for h,_,_ in win32api.EnumDisplayMonitors() if win32api.GetMonitorInfo(h)['Monitor'][0]<0),win32api.GetMonitorInfo(win32api.MonitorFromPoint((0,0))))
x,y=monitor['Work'][:2];x+=100;y+=180
board=g.CreateWindowEx(c.WS_EX_TOPMOST|c.WS_EX_TOOLWINDOW,bgklass.lpszClassName,'W-01 board',c.WS_POPUP|c.WS_VISIBLE,x-20,y-20,680,400,0,0,klass.hInstance,None)
class Accent(ctypes.Structure):_fields_=[('state',ctypes.c_int),('flags',ctypes.c_int),('color',wt.DWORD),('animation',ctypes.c_int)]
class Data(ctypes.Structure):_fields_=[('attribute',ctypes.c_int),('data',ctypes.c_void_p),('size',ctypes.c_size_t)]
setter=ctypes.windll.user32.SetWindowCompositionAttribute;setter.argtypes=[wt.HWND,ctypes.POINTER(Data)]
def settle():
    for _ in range(30):g.PumpWaitingMessages();time.sleep(.01)
rows=[]
for name,state,reapply in [('disabled',0,False),('acrylic',4,False),('acrylic-region-after',4,True)]:
    g.SetWindowPos(board,c.HWND_TOPMOST,0,0,0,0,c.SWP_NOMOVE|c.SWP_NOSIZE|c.SWP_SHOWWINDOW)
    h=g.CreateWindowEx(c.WS_EX_TOPMOST|c.WS_EX_TOOLWINDOW,klass.lpszClassName,'W-01 diagnostic: '+name,c.WS_POPUP|c.WS_THICKFRAME,x,y,640,360,0,0,klass.hInstance,None)
    pref=ctypes.c_int(1);ctypes.windll.dwmapi.DwmSetWindowAttribute(wt.HWND(h),33,ctypes.byref(pref),4)
    g.SetWindowRgn(h,g.CreateRoundRectRgn(0,0,641,361,28,28),True)
    accent=Accent(state,0,0x7de8f0ee,0);data=Data(19,ctypes.addressof(accent),ctypes.sizeof(accent));setter(wt.HWND(h),ctypes.byref(data))
    if reapply:g.SetWindowRgn(h,g.CreateRoundRectRgn(0,0,641,361,28,28),True)
    g.ShowWindow(h,c.SW_SHOWNOACTIVATE);settle()
    region=g.CreateRectRgnIndirect((0,0,0,0));g.GetWindowRgn(h,region)
    im=ImageGrab.grab(bbox=(x-10,y-10,x+650,y+370),all_screens=True);im.save(OUT/('w01-native-'+name+'.png'))
    row=dict(name=name,corner=im.getpixel((11,11)),outside=im.getpixel((1,1)),corner_in_region=bool(g.PtInRegion(region,1,1)),behind_is_board=g.WindowFromPoint((x+1,y+1))==board)
    row['leak_detected']=row['corner']!=row['outside'] and not row['corner_in_region'] and row['behind_is_board']
    rows.append(row)
    until=time.monotonic()+args.hold
    while time.monotonic()<until:g.PumpWaitingMessages();time.sleep(.01)
    g.DeleteObject(region);g.DestroyWindow(h);settle()
g.DestroyWindow(board)
report=dict(os=list(sys.getwindowsversion()),cases=rows)
(OUT/'w01-native-region.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))


