"""Native phase-two smoke test: seeded fixture, isolated file DB, real worker/Tk."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tempfile
import time
import tkinter as tk
from core.config import Config
from core.bootstrap import build_agent
from database.models import CompanyProfile
from database.database import Database
from database.leads import LeadRepository
from desktop import DesktopApp


def run():
    with tempfile.TemporaryDirectory() as temporary:
        path=Path(temporary)/'leads.db'
        identity='abc123abc123abc123abc123abc123ab'
        def factory(config,**kwargs):
            agent=build_agent(config,**kwargs)
            agent.companies.add(CompanyProfile(id=identity,name='Empresa de teste nativo',city='Campinas'))
            return agent
        root=tk.Tk();root.withdraw()
        app=DesktopApp(root,Config(database_path=str(path),env_file=str(Path(temporary)/'.env')),factory=factory)
        failures=[]
        root.report_callback_exception=lambda kind,error,tb: failures.append(error)
        def wait(check):
            deadline=time.monotonic()+12
            while not check() and time.monotonic()<deadline:
                root.update();time.sleep(.02)
            assert check() and not failures, failures
        def command(text):
            app.submit(text)
            wait(lambda:not app.busy)
        try:
            wait(lambda:app.ready)
            terminal=app.get_terminal();terminal.show()
            root.update()
            def buttons(widget):
                for child in widget.winfo_children():
                    if isinstance(child,tk.Button): yield child
                    yield from buttons(child)
            for control in buttons(terminal.window):
                assert control.winfo_ismapped(), (control.cget("text"), terminal.window.state(), terminal.visible)
                assert control.winfo_rootx()+control.winfo_width() <= terminal.window.winfo_rootx()+terminal.window.winfo_width()
            command('/leads')
            assert identity in terminal.output.get('1.0','end')
            command('/stage '+identity+' negotiating')
            command('/note '+identity+' Conversa registrada no teste')
            command('/lead '+identity)
            assert 'Em negociação' in terminal.output.get('1.0','end')
            assert 'Conversa registrada no teste' in terminal.output.get('1.0','end')
            command('/archive '+identity)
            command('sim')
            command('/leads arquivados')
            assert identity in terminal.last_skill_result['message']
            command('/restore '+identity)
            command('/export json '+identity)
            assert len(list((path.parent/'exports').glob('*.json')))==1
            assert terminal.window.winfo_width()<=620 and terminal.window.winfo_height()<=440
        finally:
            app.close();app.worker.thread.join(5)
            root.destroy()
            assert not app.worker.thread.is_alive()
        db=Database(str(path))
        try:
            row=LeadRepository(db).resolve(identity)
            assert row['commercial_status']=='negotiating' and not row['archived']
            assert row['notes']=='Conversa registrada no teste'
        finally: db.close()
        print('PASS: native leads/list/detail/stage/note/archive/restore/export and persisted restart; fixture only.')


if __name__=='__main__':run()
