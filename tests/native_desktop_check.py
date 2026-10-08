"""Manual native smoke test: python tests/native_desktop_check.py [--screenshots].

Uses an in-memory database; never calls an external API. Screenshots capture
only this test window, not the user's desktop or other applications.
"""
import ctypes
from ctypes import wintypes
from pathlib import Path
import struct
import sys
import time
import zlib
import tempfile
import os
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tkinter as tk
from core.config import Config
from tests.factories import build_agent
from desktop import DesktopApp


def screenshot(root, path):
    user, gdi = ctypes.windll.user32, ctypes.windll.gdi32
    user.GetParent.argtypes, user.GetParent.restype = [wintypes.HWND], wintypes.HWND
    hwnd = user.GetParent(root.winfo_id())
    rect = wintypes.RECT()
    user.GetWindowRect(hwnd, ctypes.byref(rect))
    width, height = rect.right-rect.left, rect.bottom-rect.top
    user.GetWindowDC.argtypes, user.GetWindowDC.restype = [wintypes.HWND], wintypes.HDC
    gdi.CreateCompatibleDC.argtypes, gdi.CreateCompatibleDC.restype = [wintypes.HDC], wintypes.HDC
    gdi.CreateCompatibleBitmap.argtypes, gdi.CreateCompatibleBitmap.restype = [wintypes.HDC, ctypes.c_int, ctypes.c_int], wintypes.HBITMAP
    gdi.SelectObject.argtypes, gdi.SelectObject.restype = [wintypes.HDC, wintypes.HANDLE], wintypes.HANDLE
    user.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
    gdi.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]
    gdi.DeleteObject.argtypes = [wintypes.HANDLE]
    gdi.DeleteDC.argtypes = [wintypes.HDC]
    user.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    source = user.GetWindowDC(hwnd)
    target = gdi.CreateCompatibleDC(source)
    bitmap = gdi.CreateCompatibleBitmap(source, width, height)
    previous = gdi.SelectObject(target, bitmap)
    try:
        assert user.PrintWindow(hwnd, target, 2), 'Could not render test window'
        header = struct.pack('<IiiHHIIiiII', 40, width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
        info = ctypes.create_string_buffer(header)
        pixels = ctypes.create_string_buffer(width*height*4)
        gdi.SelectObject(target, previous)
        assert gdi.GetDIBits(target, bitmap, 0, height, pixels, info, 0)
        data = pixels.raw
        rows = bytearray()
        for y in range(height):
            rows.append(0)
            for x in range(width):
                i = (y*width+x)*4
                rows.extend((data[i+2], data[i+1], data[i]))
        def chunk(kind, value):
            return struct.pack('!I', len(value)) + kind + value + struct.pack('!I', zlib.crc32(kind+value) & 0xffffffff)
        png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', width, height, 8, 2, 0, 0, 0))
        png += chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b'')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(png)
    finally:
        gdi.SelectObject(target, previous)
        gdi.DeleteObject(bitmap)
        gdi.DeleteDC(target)
        user.ReleaseDC(hwnd, source)


def run(mock=False):
    from types import SimpleNamespace
    from ui import native
    temporary = tempfile.TemporaryDirectory()
    root = tk.Tk()
    root.withdraw()
    app = DesktopApp(root, Config(mock=mock, database_path=':memory:', search_api_key='',
                                 env_file=str(Path(temporary.name) / '.env')), factory=build_agent)
    app.reduced_motion.set(True)
    failures = []
    root.report_callback_exception = lambda kind, error, tb: failures.append(error)
    def tick(seconds=.15):
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            root.update()
            time.sleep(.01)
        assert not failures, failures
    def wait():
        deadline = time.monotonic()+15
        while app.busy and time.monotonic() < deadline:
            tick(.05)
        assert not app.busy
        tick()
    def capture(window, name):
        if '--screenshots' in sys.argv:
            screenshot(window, Path('data/desktop-previews') / (('fixture-' if mock else '') + name))
    try:
        wait()
        assert app.terminal is None, 'Startup must not create/show the old UI or console'
        assert root.overrideredirect()
        assert bool(root.attributes('-topmost'))
        assert app.state == 'IDLE' and len(app.atlas.images) == 6
        anchor = (app.x, app.y)
        app.hover(False)
        app.reduced_motion.set(False)
        positions = set()
        for _ in range(15):
            tick(.1)
            positions.add(app.motion_offset)
        assert len(positions) > 1, 'Idle animation must move the native window'
        assert (app.x, app.y) == anchor, 'Animation must not drift the saved position'
        app.hover(True)
        held = app.motion_offset
        tick(.3)
        assert app.motion_offset == held, 'Hover must hold the mascot still for clicking'
        app.reduced_motion.set(True)
        assert app.motion_job is None and app.motion_offset == (0, 0)
        app.hover(False)
        # Exercise the actual compositor, sleep effects and wake-up on Windows.
        app.reduced_motion.set(False)
        foreground = native.api()[0].GetForegroundWindow()
        app.set_state('ANALYZING')
        tick(.12)
        assert app.transitions.ghost is not None
        assert 0 < float(root.attributes('-alpha')) < 1
        tick(.4)
        assert app.transitions.ghost is None and float(root.attributes('-alpha')) == 1
        assert native.api()[0].GetForegroundWindow() == foreground
        app.set_state('IDLE')
        tick(.4)
        app.animation.idle.blink_start = time.monotonic()
        tick(.1)
        assert app.renderer.level > 0, 'Blink overlay must close the original eyes'
        capture(root, 'mascot-blinking.png')
        tick(.2)
        assert app.renderer.level == 0
        app.press(SimpleNamespace(x_root=app.x+80, y_root=app.y+120))
        app.drag(SimpleNamespace(x_root=app.x+65, y_root=app.y+110))
        app.animation.idle.blink_start = time.monotonic()
        tick(.1)
        assert app.renderer.level > 0 and app.state == 'IDLE', 'Drag must keep presentation animation alive'
        app.release(None)
        tick(.2)
        app.animation.sleep.last_activity = time.monotonic()-121
        tick(1.6)
        assert app.animation.sleep.phase == 'SLEEPING'
        assert app.renderer.level == 8
        assert all(app.renderer.lids[state] for state in app.atlas.images)
        app.sleep_bubbles.next_at = time.monotonic()
        tick(.4)
        assert 1 <= len(app.sleep_bubbles.items) <= 2
        assert native.api()[0].GetForegroundWindow() == foreground
        capture(root, 'mascot-sleeping.png')
        capture(app.sleep_bubbles.items[0]['window'], 'sleep-effect.png')
        app.touch()
        assert app.animation.sleep.phase == 'WAKE_UP'
        assert not app.sleep_bubbles.items
        tick(.8)
        assert app.animation.sleep.phase == 'IDLE'
        app.animation.sleep.last_activity = time.monotonic()-121
        app.set_busy(True)
        tick(1.5)
        assert app.animation.sleep.phase == 'IDLE', 'Working must block sleep'
        app.set_busy(False)
        app.sleep_after.set(0)
        app.sleep_timeout_changed()
        app.animation.sleep.last_activity = time.monotonic()-999
        tick(.3)
        assert app.animation.sleep.phase == 'IDLE'
        app.sleep_after.set(120)
        app.sleep_timeout_changed()
        app.notify('Animação de notificação · teste local')
        tick(.12)
        assert 0 < float(app.bubble.attributes('-alpha')) < 1
        app.dismiss_bubble()
        tick(.3)
        assert app.bubble is None
        app.reduced_motion.set(True)
        # Windows owns the exact shape: exterior pixels are not clickable, eyes are.
        user, gdi = native.api()
        gdi.CreateRectRgn.argtypes, gdi.CreateRectRgn.restype = [ctypes.c_int]*4, wintypes.HANDLE
        user.GetWindowRgn.argtypes = [wintypes.HWND, wintypes.HANDLE]
        gdi.PtInRegion.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_int]
        region = gdi.CreateRectRgn(0, 0, 0, 0)
        assert user.GetWindowRgn(native.hwnd(root), region)
        assert not gdi.PtInRegion(region, 0, 0)
        mask = app.atlas.masks['IDLE']
        eye = next(i for i, on in enumerate(mask) if on and tuple(app.atlas.images['IDLE'].get(i % app.atlas.width, i // app.atlas.width)) == (255, 255, 255))
        assert gdi.PtInRegion(region, eye % app.atlas.width, eye // app.atlas.width)
        gdi.DeleteObject(region)
        for state in app.atlas.images:
            app.set_state(state)
            tick(.05)
            capture(root, 'mascot-' + state.lower() + '.png')
        app.set_state('IDLE')
        before = (app.x, app.y)
        app.press(SimpleNamespace(x_root=app.x+80, y_root=app.y+120))
        app.drag(SimpleNamespace(x_root=app.x+45, y_root=app.y+95))
        app.release(None)
        assert (app.x, app.y) != before
        assert app.terminal is None, 'Dragging must not open results'
        app.press(SimpleNamespace(x_root=app.x+80, y_root=app.y+120))
        app.release(None)
        tick()
        assert app.terminal.visible
        assert app.terminal.window.winfo_width() <= 700
        assert app.terminal.window.winfo_height() <= 500
        app.state_history = ['IDLE']
        app.submit('procure clínicas em Campinas')
        app.terminal.hide()
        foreground = native.api()[0].GetForegroundWindow()
        wait()
        tick(.5)
        assert not app.terminal.visible, 'Completion must not show results automatically'
        assert native.api()[0].GetForegroundWindow() == foreground, 'Completion stole focus'
        text = app.terminal.output.get('1.0', 'end')
        assert ('Pesquisa concluída' if mock else 'Pesquisa não iniciada') in text
        if mock:
            assert set(app.atlas.images) <= set(app.state_history)
            assert app.notice and 'empresas' in app.notice
        else:
            assert app.operation_failed
        assert app.bubble is not None
        capture(app.bubble, 'mascot-notice.png')
        app.toggle_terminal()
        tick()
        capture(app.terminal.window, 'mascot-terminal.png')
        app.toggle_terminal()
        assert not app.terminal.visible
        # A different, owned test window takes focus: terminal must dismiss.
        app.toggle_terminal()
        other = tk.Toplevel(root)
        other.title('SAZABI focus test')
        other.geometry('120x80+0+0')
        other.focus_force()
        tick(.3)
        assert not app.terminal.visible, 'Click/focus outside should dismiss the terminal'
        other.destroy()
        app.open_settings()
        tick()
        preferences = app.preferences
        preferences.key.insert(0, 'tvly-test-private-key')
        with patch.dict(os.environ), patch('core.connection.TavilySearch.check_connection', return_value={'usage': 0, 'limit': 1000}):
            preferences.connect()
            wait()
        assert 'conectada' in preferences.status.get()
        assert not preferences.key.get()
        with patch('analysis.ai_provider.list_models', return_value=['test-local:1']):
            preferences.ollama('list')
            wait()
        with patch.dict(os.environ), patch('analysis.ai_provider.OllamaProvider.check_model'):
            preferences.ollama('activate')
            wait()
            assert app.config.ai_provider == 'ollama'
            preferences.ollama('disable')
            wait()
            assert app.config.ai_provider == 'none'
        capture(preferences.window, 'mascot-settings.png')
        preferences.window.destroy()
        app.always_on_top.set(False)
        app.topmost_changed()
        assert not bool(root.attributes('-topmost'))
        app.close()
        app.worker.thread.join(timeout=5)
        assert not app.worker.thread.is_alive()
        print('PASS: mascot, crossfade, blinking, sleep/wake, bubbles, notifications, task priority, reduced motion, drag/click, terminal, focus, settings, shutdown')
    finally:
        app.worker.close()
        app.worker.thread.join(timeout=5)
        root.destroy()
        temporary.cleanup()


if __name__ == '__main__':
    run(False)
    run(True)
