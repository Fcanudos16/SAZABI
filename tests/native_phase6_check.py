"""Native workflow with a synthetic provider and in-memory DB; no network."""
import re
import sys
import time
import tkinter as tk
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core.config import Config
from desktop import DesktopApp
from tests.factories import build_agent
from tests.native_desktop_check import screenshot


def main():
    root=tk.Tk()
    errors=[]
    root.report_callback_exception=lambda kind,value,trace: errors.append(value)
    app=DesktopApp(root,Config(database_path=':memory:',mock=True),factory=build_agent)
    def wait(predicate):
        until=time.monotonic()+15
        while not predicate() and time.monotonic()<until:
            root.update();time.sleep(.02)
        assert predicate(), 'Native operation timed out'
        assert not errors,errors
    def run(command):
        app.submit(command)
        wait(lambda:not app.busy)
        assert app.terminal.last_skill_result['success'],app.terminal.last_skill_result
        return app.terminal.output.get('1.0','end')
    try:
        wait(lambda:app.ready)
        run('/search oficinas em Campinas')
        rows=run('/leads')
        identity=re.search(r'\b[a-f0-9]{32}\b',rows).group()
        assert 'Em verificação' in run(f'/stage {identity} verifying Conferir dados da fonte')
        assert 'Tarefa #' in run(f'/task {identity} 2020-01-01 Confirmar atividade | Teste sintético')
        tasks=run('/tasks vencidas')
        assert 'VENCIDA' in tasks
        number=re.search(r'^#(\d+)',tasks,re.M).group(1)
        assert 'Tarefas vencidas: 0' in run('/taskdone '+number)
        run(f'/note {identity} Nota sintética do teste nativo')
        detail=run('/lead '+identity)
        assert 'Nota sintética' in detail and 'Concluída em' in detail
        run('/overview')
        app.terminal.show();root.update()
        assert app.terminal.window.winfo_width()<=620
        assert not app.research_timer.visible
        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)
        buttons={w.cget('text'):w for w in descendants(app.terminal.window) if isinstance(w,tk.Button)}
        buttons['Tarefas'].invoke();wait(lambda:not app.busy)
        assert 'Tarefas comerciais' in app.terminal.output.get('1.0','end')
        buttons['Visão geral'].invoke();wait(lambda:not app.busy)
        app.terminal.show();root.update()
        output=Path('data/phase6');output.mkdir(parents=True,exist_ok=True)
        screenshot(app.terminal.window,output/'overview.png')
        print('PASS: native search, lead, stage, task, completion, notes, details, overview; toolbar; timer hidden; compact terminal.')
    finally:
        app.close();app.worker.thread.join(10)
        assert not app.worker.thread.is_alive()
        try: root.update()
        except tk.TclError: pass
        assert not errors,errors


if __name__=='__main__': main()
