"""Small Win32 window helpers, no hooks, shell commands, or global mouse capture."""
import ctypes as c
from ctypes import wintypes as w
import sys


def api():
    if sys.platform != 'win32':
        return None
    user, gdi = c.WinDLL('user32'), c.WinDLL('gdi32')
    user.GetAncestor.argtypes, user.GetAncestor.restype = [w.HWND, w.UINT], w.HWND
    user.SetWindowRgn.argtypes = [w.HWND, w.HANDLE, w.BOOL]
    user.SetWindowPos.argtypes = [w.HWND, w.HWND, c.c_int, c.c_int, c.c_int, c.c_int, w.UINT]
    user.GetForegroundWindow.restype = w.HWND
    user.IsChild.argtypes = [w.HWND, w.HWND]
    user.GetWindowLongW.argtypes, user.GetWindowLongW.restype = [w.HWND, c.c_int], c.c_long
    user.SetWindowLongW.argtypes = [w.HWND, c.c_int, c.c_long]
    gdi.ExtCreateRegion.argtypes, gdi.ExtCreateRegion.restype = [c.c_void_p, w.DWORD, c.c_void_p], w.HANDLE
    gdi.DeleteObject.argtypes = [w.HANDLE]
    return user, gdi


def hwnd(window):
    return api()[0].GetAncestor(window.winfo_id(), 2)


def shape(window, region):
    user, gdi = api()
    buffer = c.create_string_buffer(region)
    handle = gdi.ExtCreateRegion(None, len(region), buffer)
    if not handle:
        raise RuntimeError('Falha ao criar a região transparente do mascote.')
    if not user.SetWindowRgn(hwnd(window), handle, True):
        gdi.DeleteObject(handle)
        raise RuntimeError('Falha ao aplicar a transparência do mascote.')
    # Windows owns the region after successful SetWindowRgn.


def no_activate(window):
    user, _ = api()
    handle = hwnd(window)
    flags = user.GetWindowLongW(handle, -20)
    user.SetWindowLongW(handle, -20, flags | 0x08000000 | 0x00000080)  # NOACTIVATE | TOOLWINDOW


def show_passive(window, x, y, width, height, topmost=True):
    user, _ = api()
    user.SetWindowPos(hwnd(window), w.HWND(-1 if topmost else -2), x, y, width, height,
                      0x0010 | 0x0040)  # NOACTIVATE | SHOWWINDOW


def position(window, x, y):
    # Unlike Tk's negative geometry offsets, these are absolute desktop coordinates.
    user, _ = api()
    user.SetWindowPos(hwnd(window), None, x, y, 0, 0, 0x0010 | 0x0001 | 0x0004)


def is_foreground(window):
    user, _ = api()
    active, handle = user.GetForegroundWindow(), hwnd(window)
    return active == handle or bool(user.IsChild(handle, active))


def work_area(window):
    user, _ = api()
    class MonitorInfo(c.Structure):
        _fields_ = [('size', w.DWORD), ('monitor', w.RECT), ('work', w.RECT), ('flags', w.DWORD)]
    user.MonitorFromWindow.argtypes, user.MonitorFromWindow.restype = [w.HWND, w.DWORD], w.HANDLE
    user.GetMonitorInfoW.argtypes = [w.HANDLE, c.POINTER(MonitorInfo)]
    info = MonitorInfo()
    info.size = c.sizeof(info)
    monitor = user.MonitorFromWindow(hwnd(window), 2)
    if user.GetMonitorInfoW(monitor, c.byref(info)):
        return info.work.left, info.work.top, info.work.right, info.work.bottom
    return 0, 0, window.winfo_screenwidth(), window.winfo_screenheight()


def place_near(x, y, mascot_w, mascot_h, width, height, area):
    left, top, right, bottom = area
    px = x + mascot_w + 10 if x + mascot_w + 10 + width <= right else x-width-10
    py = y if y+height <= bottom else y-height-10
    return max(left, min(px, right-width)), max(top, min(py, bottom-height))
