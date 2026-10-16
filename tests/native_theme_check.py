"""Real Tk theme/lifecycle checks; isolated DB and no network calls.

Run again with --probe to change the central foreground before UI imports.
"""
import sys
import time
import tkinter as tk
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ui import theme, native
if '--probe' in sys.argv:
    theme.FG = '#57c785'
from core.config import Config
from desktop import DesktopApp
from tests.native_desktop_check import screenshot


root = tk.Tk()
app = DesktopApp(root, Config(database_path=':memory:', search_api_key=''))
errors = []
root.report_callback_exception = lambda kind, error, tb: errors.append(error)


def tick(seconds=.25):
    until = time.monotonic()+seconds
    while time.monotonic() < until:
        root.update()
        time.sleep(.01)
    assert not errors, errors


try:
    tick(1)
    assert app.ready and not app.failed
    terminal = app.get_terminal()
    terminal.show(); tick()
    app.open_settings(); tick()
    prefs = app.preferences
    assert not hasattr(prefs, 'key') and not hasattr(prefs, 'connect')
    prefs.model.configure(values=['local-one']+[f'local-{i}' for i in range(30)])
    prefs.model.set('local-one')
    root.tk.call('ttk::combobox::Post', str(prefs.model)); tick()
    popup = root.tk.call('ttk::combobox::PopdownWindow', str(prefs.model))
    listing = str(popup)+'.f.l'
    assert root.tk.call(listing, 'cget', '-background') == theme.BG
    assert root.tk.call(listing, 'cget', '-foreground') == theme.FG
    root.tk.call('ttk::combobox::Unpost', str(prefs.model))
    assert terminal.entry.cget('selectbackground') == theme.SELECTION
    assert terminal.entry.cget('insertbackground') == theme.FG
    terminal.entry.insert(0, 'seleção'); terminal.entry.selection_range(0, 'end')
    assert terminal.entry.selection_present()
    from tkinter import ttk
    style = ttk.Style(root)
    assert style.lookup('Sazabi.Vertical.TScrollbar', 'arrowcolor') == theme.FG
    assert style.lookup('Vertical.TScrollbar', 'troughcolor') == theme.BG
    assert style.lookup('Sazabi.Horizontal.TProgressbar', 'background') == theme.LOADING
    handle = native.hwnd(root)
    flags = native.api()[0].GetWindowLongW(handle, -20)
    assert flags & 0x08000000 and flags & 8  # NOACTIVATE and TOPMOST
    native.minimize(prefs.window); tick()
    assert root.winfo_viewable() and native.hwnd(root) == handle
    prefs.show(); tick()
    assert not native.api()[0].IsIconic(native.hwnd(prefs.window))
    prefs.window.destroy()
    terminal.hide(); tick()
    assert root.winfo_viewable()
    terminal.show(); tick()
    assert app.get_terminal() is terminal and native.hwnd(root) == handle
    app.context_menu(SimpleNamespace(x_root=app.x+50, y_root=app.y+80)); tick()
    assert app.interaction.rows
    assert 'Configuração · Tavily / Groq' not in app.interaction.rows
    assert all(row[3].cget('foreground') == theme.FG for row in app.interaction.rows.values())
    app.interaction.close()
    with patch('integrations.layla.session.LaylaBridge') as bridge:
        bridge.return_value.state = 'connected'
        app.open_ai(); tick()
        ai = app.ai_terminal
        assert ai.entry.cget('foreground') == theme.FG
        assert ai.output.cget('selectbackground') == theme.SELECTION
        ai.hide()
    app.open_settings(); tick()
    app.notify('Tema central: teste local'); tick()
    if app.bubble:
        assert app.bubble.winfo_children()[0].cget('foreground') == theme.FG
    screenshot(app.preferences.window, Path('data/desktop-previews/theme-settings'+('-probe' if '--probe' in sys.argv else '')+'.png'))
    # A conventional independent native window owns focus; pet remains topmost.
    other = tk.Toplevel(root); other.title('Janela de teste independente')
    other.geometry('300x160+30+30'); other.focus_force(); tick()
    active = native.api()[0].GetForegroundWindow()
    native.show_passive(root, app.x, app.y, app.atlas.width, app.atlas.height)
    tick()
    assert native.api()[0].GetForegroundWindow() == active
    assert root.winfo_viewable()
    other.destroy()
    print('PASS: native theme, combobox popup, selection, no key field, independent lifecycle, minimize/restore, passive topmost; probe=', '--probe' in sys.argv)
finally:
    app.close()
    deadline = time.monotonic()+8
    while app.worker.thread.is_alive() and time.monotonic()<deadline:
        try: root.update()
        except tk.TclError: break
        time.sleep(.02)
    try: root.destroy()
    except tk.TclError: pass
    assert not app.worker.thread.is_alive()
