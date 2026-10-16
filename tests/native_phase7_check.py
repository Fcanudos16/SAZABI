"""Native strategy UI with synthetic sources and an isolated profile/database."""
from pathlib import Path
import sys
import tempfile
import time
import tkinter as tk
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core.config import Config
from analysis.commercial_profile import DEFAULT_PATH
from desktop import DesktopApp
from tests.factories import build_agent
from tests.native_desktop_check import screenshot


def main():
    with tempfile.TemporaryDirectory(prefix='sazabi-phase7-') as directory:
        profile=Path(directory)/'profile.json'
        profile.write_text(DEFAULT_PATH.read_text(encoding='utf-8'),encoding='utf-8')
        root=tk.Tk();errors=[]
        root.report_callback_exception=lambda kind,value,trace:errors.append(value)
        app=DesktopApp(root,Config(database_path=':memory:',commercial_profile_path=str(profile),mock=True),factory=build_agent)
        def wait(predicate):
            until=time.monotonic()+15
            while not predicate() and time.monotonic()<until:
                root.update();time.sleep(.02)
            assert predicate() and not errors,errors
        def run(command,success=True):
            app.submit(command);wait(lambda:not app.busy)
            assert app.terminal.last_skill_result['success']==success,app.terminal.last_skill_result
            return app.terminal.output.get('1.0','end')
        try:
            wait(lambda:app.ready)
            run('/profile set services automação;integrações')
            assert 'Possíveis processos manuais' in run('/search estratégia=manual oficinas em Campinas')
            run_id=app.terminal.last_skill_result['data']['run_id']
            run('/strategies disable manual')
            run('/search estratégia=manual oficinas em Campinas',False)
            assert 'manual' in run('/strategies run '+str(run_id))
            def descendants(widget):
                for child in widget.winfo_children():
                    yield child
                    yield from descendants(child)
            buttons={w.cget('text'):w for w in descendants(app.terminal.window) if isinstance(w,tk.Button)}
            buttons['Perfil'].invoke();wait(lambda:not app.busy)
            assert 'Perfil comercial local' in app.terminal.output.get('1.0','end')
            buttons['Estratégias'].invoke();wait(lambda:not app.busy)
            app.terminal.show();root.update()
            assert app.terminal.window.winfo_width()<=620 and not app.research_timer.visible
            path=Path('data/phase7');path.mkdir(parents=True,exist_ok=True)
            screenshot(app.terminal.window,path/'strategies.png')
            print('PASS: isolated profile editing, explicit strategy search, disabled strategy, historical plan, native toolbar, compact terminal.')
        finally:
            app.close();app.worker.thread.join(10)
            assert not app.worker.thread.is_alive()
            try:root.update()
            except tk.TclError:pass
            assert not errors,errors


if __name__=='__main__':main()
