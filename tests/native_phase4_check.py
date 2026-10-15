"""Native integrated phase-four fixtures; no external APIs or user database."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tempfile
import threading
import time
import tkinter as tk
from types import SimpleNamespace
from unittest.mock import patch
from core.config import Config
from tests.factories import build_agent
from desktop import DesktopApp
from tests.native_desktop_check import screenshot


def run(scale):
    with tempfile.TemporaryDirectory() as directory:
        entered,release=threading.Event(),threading.Event()
        block=[False]
        def factory(config,**kwargs):
            agent=build_agent(config,**kwargs)
            original=agent.finder.find
            def find(criteria):
                if block[0]: entered.set();release.wait(8)
                return original(criteria)
            agent.finder.find=find
            return agent
        root=tk.Tk();root.withdraw();root.tk.call('tk','scaling',scale)
        app=DesktopApp(root,Config(mock=True,database_path=str(Path(directory)/'test.db'),env_file=str(Path(directory)/'.env')),factory=factory)
        errors=[]
        root.report_callback_exception=lambda kind,error,tb:errors.append(error)
        def wait(check,timeout=12):
            deadline=time.monotonic()+timeout
            while not check() and time.monotonic()<deadline:
                root.update();time.sleep(.02)
            root.update()
            assert check() and not errors, errors
        def command(text):
            app.submit(text);wait(lambda:not app.busy)
        try:
            wait(lambda:app.ready)
            terminal=app.get_terminal();terminal.show();root.update()
            command('/search oficinas em Campinas')
            assert terminal.last_skill_result['status']=='completed'
            saved=terminal.last_result
            command('/leads min_score=0 ordem=score')
            assert terminal.last_result==saved
            assert 'Execução local #1' not in terminal.output.get('1.0','end')
            app.show_last_result();root.update()
            assert 'Pesquisa concluída' in terminal.output.get('1.0','end')
            block[0]=True
            app.submit('/research clínicas em Campinas')
            wait(entered.is_set)
            assert str(terminal.cancel['state'])=='normal'
            terminal.hide();app.toggle_terminal()
            assert str(terminal.cancel['state'])=='normal'
            terminal.cancel.invoke()
            assert app.cancel_requested and str(terminal.cancel['state'])=='disabled'
            release.set();wait(lambda:not app.busy)
            assert terminal.last_skill_result['status']=='cancelled' and app.state=='IDLE'
            assert 'Pesquisa concluída' not in terminal.output.get('1.0','end')
            app.notifications_enabled.set(False);app.notifications_changed()
            command('/status');assert app.bubble is None
            app.notifications_enabled.set(True);app.notifications_changed()
            terminal.hide();app.last_click=0
            event=SimpleNamespace(x_root=app.x+80,y_root=app.y+120)
            app.press(event);app.release(event)
            app.press(event);app.release(event)
            assert terminal.visible,'Double click must leave application access open'
            with patch('ui.native.work_area',return_value=(0,0,800,600)):
                app.x,app.y=5000,5000;app.area_checked=0
                if app.life_job: root.after_cancel(app.life_job)
                app.life_tick()
                assert 0<=app.x<=610 and 0<=app.y<=380
                terminal.show();root.update()
                assert terminal.window.winfo_rootx()+terminal.window.winfo_width()<=800
                assert terminal.window.winfo_rooty()+terminal.window.winfo_height()<=600
            def controls(widget):
                for child in widget.winfo_children():
                    if isinstance(child,tk.Button):yield child
                    yield from controls(child)
            for widget in controls(terminal.window):
                assert widget.winfo_ismapped(),widget.cget('text')
                assert widget.winfo_rootx()+widget.winfo_width()<=terminal.window.winfo_rootx()+terminal.window.winfo_width(),widget.cget('text')
            command('/profile')
            terminal.show();root.update()
            screenshot(terminal.window,Path('data/desktop-previews')/f'phase4-terminal-{scale}.png')
            app.open_settings();root.update()
            for widget in app.preferences.controls:
                assert widget.winfo_ismapped()
                assert widget.winfo_rooty()+widget.winfo_height()<=app.preferences.window.winfo_rooty()+app.preferences.window.winfo_height(),widget.cget('text')
            screenshot(app.preferences.window,Path('data/desktop-previews')/f'phase4-settings-{scale}.png')
            app.preferences.window.destroy();terminal.hide()
            warmed=time.monotonic()
            while time.monotonic()-warmed<3:root.update();time.sleep(.02)
            before_cpu=time.process_time();before=time.monotonic()
            while time.monotonic()-before<3:root.update();time.sleep(.02)
            print(f'Idle sample at Tk scale {scale}: CPU {time.process_time()-before_cpu:.3f}s / wall {time.monotonic()-before:.2f}s')
        finally:
            release.set();app.close();wait(lambda:not app.worker.thread.is_alive())
            try:root.destroy()
            except tk.TclError:pass
            assert not app.worker.thread.is_alive()
        print(f'PASS: phase4 native controls/cancellation/current-result/double-click/edges/settings at Tk scale {scale}')


if __name__=='__main__':
    for scale in (1.333333,2.0,2.666667):run(scale)
