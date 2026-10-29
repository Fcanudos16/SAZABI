"""Native Tk test with synthetic cards and isolated in-memory database."""
import sys
import time
import tkinter as tk
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core.config import Config
from desktop import DesktopApp
from tests.factories import build_agent
from tests.test_search_brief import brief
from tests.native_desktop_check import screenshot


def main():
    root=tk.Tk(); errors=[]
    root.report_callback_exception=lambda kind,value,trace: errors.append(str(value))
    app=DesktopApp(root,Config(database_path=':memory:',mock=True),factory=build_agent)
    try:
        deadline=time.monotonic()+20
        while not app.ready and time.monotonic()<deadline:
            root.update();time.sleep(.02)
        assert app.ready
        cards=[brief('Precisamos automatizar o controle manual de pedidos.',name='Empresa Alfa'),
               brief('Utilizamos planilhas para controle manual de pedidos.',name='Empresa Beta')]
        cards[0]['company_id']='alfa';cards[1]['company_id']='beta'
        result=dict(success=True,status='completed',skill='search',message='Teste',data=dict(
            opportunities=cards,headline='2 empresas fictícias — validação local',pending_companies=[],diagnostics='Diagnóstico de teste'))
        terminal=app.get_terminal()
        terminal.begin('/search teste');terminal.render_skill(result);terminal.remember_result();terminal.show();root.update()
        first=terminal.result_controls[0].winfo_children()
        assert terminal.output.tag_cget('detail_alfa','elide')=='1'
        first[0].invoke();root.update()
        assert terminal.output.tag_cget('detail_alfa','elide')=='0'
        assert terminal.output.tag_cget('detail_beta','elide')=='1'
        first[1].invoke();root.update()
        assert root.clipboard_get()==cards[0]['outreach']
        first[0].invoke();root.update()
        assert terminal.output.tag_cget('detail_alfa','elide')=='1'
        terminal.begin('/help');terminal.show_last_result();root.update()
        assert len(terminal.result_controls)==3
        terminal.result_controls[1].winfo_children()[0].invoke();root.update()
        assert terminal.output.tag_cget('detail_beta','elide')=='0'
        output=Path('data/search-brief-check');output.mkdir(parents=True,exist_ok=True)
        screenshot(terminal.window,output/'terminal.png')
        assert terminal.window.winfo_width()<=620 and not errors,errors
        print('PASS: native expand/collapse isolation, copy-only message, restored interactive last result, compact window.')
    finally:
        app.close();app.worker.thread.join(10)
        assert not app.worker.thread.is_alive()
        try: root.update()
        except tk.TclError: pass


if __name__=='__main__': main()
