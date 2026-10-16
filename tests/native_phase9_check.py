"""Native maintenance smoke with disposable data and injected disk failure."""
import sys
from pathlib import Path
import tempfile
import time
import tkinter as tk
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core.config import Config
from desktop import DesktopApp
from tests.factories import build_agent
from tests.native_desktop_check import screenshot


def main():
    with tempfile.TemporaryDirectory(prefix='sazabi-phase9-') as directory:
        root=tk.Tk();errors=[];fail=[False]
        root.report_callback_exception=lambda kind,value,trace:errors.append(value)
        def factory(config,notifier):
            agent=build_agent(config,notifier=notifier)
            original=agent.db.backup
            def backup(*args,**kwargs):
                if fail[0]:raise OSError('synthetic disk full')
                return original(*args,**kwargs)
            agent.db.backup=backup
            return agent
        app=DesktopApp(root,Config(database_path=str(Path(directory)/'test.db'),mock=True),factory=factory)
        def wait(predicate):
            until=time.monotonic()+15
            while not predicate() and time.monotonic()<until:root.update();time.sleep(.02)
            assert predicate() and not errors,errors
        def run(command,success=True):
            app.submit(command);wait(lambda:not app.busy)
            assert app.terminal.last_skill_result['success']==success,app.terminal.last_skill_result
            return app.terminal.output.get('1.0','end')
        try:
            wait(lambda:app.ready)
            assert 'Backup validado' in run('/backup')
            assert list((Path(directory)/'backups').glob('*.db'))
            assert 'true' in run('/integrity')
            fail[0]=True
            run('/backup',False)
            assert 'last_backup' in run('/health')
            assert 'false' in run('/maintenance set auto_refresh false')
            def descendants(widget):
                for child in widget.winfo_children():
                    yield child
                    yield from descendants(child)
            buttons={w.cget('text'):w for w in descendants(app.terminal.window) if isinstance(w,tk.Button)}
            buttons['Saúde'].invoke();wait(lambda:not app.busy)
            assert app.terminal.last_skill_result['success']
            app.terminal.show();root.update()
            assert app.terminal.window.winfo_width()<=620
            assert app.research_timer is None or not app.research_timer.visible
            target=Path('data/phase9');target.mkdir(parents=True,exist_ok=True)
            screenshot(app.terminal.window,target/'health.png')
            print('PASS: native backup, integrity, injected failure, recovery to health, configuration, toolbar and bounded terminal.')
        finally:
            app.close();app.worker.thread.join(10)
            assert not app.worker.thread.is_alive()
            try:root.update()
            except tk.TclError:pass
            assert not errors,errors


if __name__=='__main__':main()
