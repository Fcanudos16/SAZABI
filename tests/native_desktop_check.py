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
    temporary = tempfile.TemporaryDirectory()
    root = tk.Tk()
    root.attributes('-alpha', 0)
    app = DesktopApp(root, Config(mock=mock, database_path=':memory:', search_api_key='',
                                 env_file=str(Path(temporary.name) / '.env')), factory=build_agent)
    failures = []
    root.report_callback_exception = lambda kind, error, tb: failures.append(error)
    def tick(seconds=.2):
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
    def capture(name):
        if '--screenshots' in sys.argv:
            screenshot(root, Path('data/desktop-previews') / name)
    try:
        wait()
        assert app.page == 'dashboard'
        assert app.dashboard.snapshot['found'] == 0
        assert app.indicator.state == 'ONLINE'
        capture('dashboard-empty.png')
        app.prepare_search('procure clínicas em Campinas')
        assert app.page == 'chat'
        app.submit() if mock else app.submit('/status')
        wait()
        assert ('Pesquisa concluída' if mock else 'Fontes ativas: nenhuma') in app.output.get('1.0', 'end')
        if mock:
            assert app.dashboard.snapshot['found'] > 0
        capture('conversation.png')
        app.show_page('dashboard')
        tick()
        capture('dashboard.png')
        app.open_settings()
        tick()
        if not mock:
            from utils.http_client import FetchError
            app.key_entry.insert(0, 'tvly-test-private-key')
            with patch('core.connection.TavilySearch.check_connection', side_effect=FetchError('Chave inválida', status=401)):
                app.connect_api()
                wait()
            assert 'inválida' in app.connection_status.get()
            assert not Path(app.config.env_file).exists()
            app.key_entry.insert(0, 'tvly-test-private-key')
            with patch.dict(os.environ), patch('core.connection.TavilySearch.check_connection', return_value={'usage': 0, 'limit': 1000}):
                app.connect_api()
                wait()
            assert 'conectada' in app.connection_status.get()
            assert Path(app.config.env_file).exists()
            assert not app.key_entry.get()
            assert 'tvly-' not in app.output.get('1.0', 'end')
            assert app.dashboard.source_label.cget('text') == 'Tavily conectada'
        app.toggle_pause()
        assert app.indicator.state == 'PAUSADO'
        app.submit('/help')
        assert not app.busy
        app.toggle_pause()
        assert app.indicator.state == 'ONLINE'
        app.reduced_motion.set(True)
        if '--screenshots' in sys.argv:
            screenshot(app.settings_window, Path('data/desktop-previews/settings.png'))
        app.settings_window.destroy()
        root.geometry('480x740')
        tick()
        assert app.compact and not app.sidebar.winfo_manager()
        assert app.dashboard.compact
        capture('compact.png')
        app.open_search()
        tick()
        assert app.entry.winfo_width() > 180
        app.entry.focus_force()
        app.entry.event_generate('<Control-k>')
        tick()
        app.submit('/help')
        wait()
        assert '/search' in app.output.get('1.0', 'end')
        app.close()
        app.worker.thread.join(timeout=5)
        assert not app.worker.thread.is_alive()
        print('PASS: native UI, ' + ('mock' if mock else 'without API') + ', metrics, navigation, pause, compact layout')
    finally:
        app.worker.close()
        app.worker.thread.join(timeout=5)
        root.destroy()
        temporary.cleanup()


if __name__ == '__main__':
    run(False)
    run(True)
