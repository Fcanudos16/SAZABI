"""Best-effort dark title bar on Windows; harmless on other platforms."""
import sys


def dark_titlebar(window):
    if sys.platform != 'win32':
        return
    try:
        import ctypes
        from ctypes import wintypes
        from ui.tokens import COLORS
        user = ctypes.windll.user32
        user.GetParent.argtypes = [wintypes.HWND]
        user.GetParent.restype = wintypes.HWND
        handle = user.GetParent(window.winfo_id())
        set_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
        set_attribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        enabled = ctypes.c_int(1)
        set_attribute(handle, 20, ctypes.byref(enabled), ctypes.sizeof(enabled))
        color = COLORS['sidebar'].lstrip('#')
        bgr = int(color[4:6]+color[2:4]+color[0:2], 16)
        caption = wintypes.DWORD(bgr)
        set_attribute(handle, 35, ctypes.byref(caption), ctypes.sizeof(caption))
    except (AttributeError, OSError):
        pass
