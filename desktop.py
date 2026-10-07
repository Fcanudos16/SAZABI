"""Native local desktop window. No browser, HTTP server or listening port."""
import argparse
import logging
from pathlib import Path
from queue import Queue, Empty
from threading import Thread

from core.bootstrap import build_agent
from core.config import load_config
from notifications.notifier import NullNotifier
from utils.logger import setup_logging


class AgentWorker:
    """Creates, uses and closes SQLite on its owning worker thread."""
    def __init__(self, config, factory=build_agent):
        self.commands, self.events = Queue(), Queue()
        self.thread = Thread(target=self._run, args=(config, factory), daemon=False)
        self.thread.start()

    def _run(self, config, factory):
        agent = None
        try:
            agent = factory(config, notifier=NullNotifier())
            if not config.mock and config.database_path != ':memory:':
                agent.db.backup()
            self.events.put(('ready', 'Pronto para pesquisar.' if config.mock or config.search_api_key
                             else 'Configure SEARCH_API_KEY da Tavily no .env e reinicie. Histórico local disponível.'))
            while True:
                command = self.commands.get()
                if command is None:
                    break
                try:
                    reply = agent.handle(command)
                    self.events.put(('reply', reply))
                except Exception:
                    logging.getLogger('sazabi.desktop').exception('Falha no comando desktop')
                    self.events.put(('reply', 'Falha ao processar o comando. Consulte o log.'))
        except Exception:
            logging.getLogger('sazabi.desktop').exception('Falha ao iniciar desktop')
            self.events.put(('error', 'Não foi possível iniciar. Confira a configuração e o log.'))
        finally:
            if agent is not None:
                agent.db.close()
            self.events.put(('closed', ''))

    def close(self):
        self.commands.put(None)


class DesktopApp:
    def __init__(self, root, config):
        import tkinter as tk
        from tkinter import ttk
        from tkinter.scrolledtext import ScrolledText
        self.root, self.busy, self.closing = root, True, False
        self.worker = AgentWorker(config)
        root.title('SAZABI • Inteligência comercial')
        root.geometry('920x680')
        root.minsize(720, 440)
        root.configure(bg='#12151b')
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('TFrame', background='#12151b')
        style.configure('TLabel', background='#12151b', foreground='#e6e9ef', font=('Segoe UI', 10))
        style.configure('TButton', font=('Segoe UI', 10), padding=(12, 8))
        style.configure('Title.TLabel', font=('Segoe UI', 23, 'bold'), foreground='#ff626d')
        frame = ttk.Frame(root, padding=20)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='SAZABI', style='Title.TLabel').pack(anchor='w')
        mode = 'DEMONSTRAÇÃO • dados fictícios' if config.mock else 'LOCAL • pesquisa Tavily'
        ttk.Label(frame, text=mode + '  |  Evidências antes de oportunidades').pack(anchor='w', pady=(0, 14))
        shortcuts = ttk.Frame(frame)
        shortcuts.pack(fill='x', pady=(0, 12))
        self.buttons = []
        for label, command in [('Resultados', '/results'), ('Oportunidades', '/interesting'),
                               ('Histórico', '/history'), ('Status', '/status'), ('Ajuda', '/help')]:
            button = ttk.Button(shortcuts, text=label, command=lambda c=command: self.submit(c))
            button.pack(side='left', padx=(0, 5))
            self.buttons.append(button)
        self.output = ScrolledText(frame, wrap='word', font=('Segoe UI', 11), bg='#1c212b',
                                  fg='#e6e9ef', insertbackground='white', relief='flat', padx=14, pady=14)
        self.output.pack(fill='both', expand=True)
        self.output.tag_configure('user', foreground='#ff8b92', font=('Segoe UI', 11, 'bold'))
        self.output.configure(state='disabled')
        ttk.Label(frame, text='Exemplo: procure clínicas em Campinas • /investigate Nome • /save Nome').pack(anchor='w', pady=(12, 5))
        composer = ttk.Frame(frame)
        composer.pack(fill='x')
        self.entry = ttk.Entry(composer, font=('Segoe UI', 12))
        self.entry.pack(side='left', fill='x', expand=True, ipady=7)
        self.entry.bind('<Return>', lambda event: self.submit())
        send = ttk.Button(composer, text='Enviar', command=self.submit)
        send.pack(side='left', padx=(8, 0))
        self.buttons.append(send)
        self.status = tk.StringVar(value='Iniciando…')
        ttk.Label(frame, textvariable=self.status, wraplength=800).pack(anchor='w', pady=(10, 0))
        self.append('SAZABI', 'Pesquise empresas, revise as fontes e guarde oportunidades.\n'
                    'Use /ignore Nome para ignorar ou /forget Nome para apagar com confirmação.')
        self.set_busy(True)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(75, self.poll)

    def append(self, author, text):
        self.output.configure(state='normal')
        self.output.insert('end', author + '\n', 'user' if author == 'Você' else ())
        self.output.insert('end', text + '\n\n')
        self.output.configure(state='disabled')
        self.output.see('end')

    def set_busy(self, value):
        self.busy = value
        for button in self.buttons:
            button.configure(state='disabled' if value else 'normal')
        self.entry.configure(state='disabled' if value else 'normal')
        if not value:
            self.entry.focus_set()

    def submit(self, command=None):
        if self.busy or self.closing:
            return
        text = command or self.entry.get().strip()
        if not text:
            return
        if len(text) > 2000:
            self.status.set('Limite: 2.000 caracteres por comando.')
            return
        if text.lower() in ('sair', '/exit', '/quit', '/sair'):
            self.close()
            return
        self.entry.delete(0, 'end')
        self.append('Você', text)
        self.set_busy(True)
        self.status.set('Processando… você pode rolar e copiar os resultados.')
        self.worker.commands.put(text)

    def poll(self):
        try:
            while True:
                kind, text = self.worker.events.get_nowait()
                if kind in ('ready', 'reply'):
                    if kind == 'reply':
                        self.append('SAZABI', text)
                    if not self.closing:
                        self.set_busy(False)
                        self.status.set(text if kind == 'ready' else 'Pronto.')
                elif kind == 'error':
                    self.append('SAZABI', text)
                    self.status.set(text)
                elif kind == 'closed' and self.closing:
                    self.root.destroy()
                    return
        except Empty:
            pass
        if self.closing and not self.worker.thread.is_alive():
            self.root.destroy()
            return
        self.root.after(75, self.poll)

    def close(self):
        if self.closing:
            return
        self.closing = True
        self.set_busy(True)
        self.status.set('Encerrando após a operação atual para fechar o banco com segurança…')
        self.worker.close()


def main():
    parser = argparse.ArgumentParser(description='SAZABI desktop local')
    parser.add_argument('--mock', action='store_true')
    parser.add_argument('--env', default=str(Path(__file__).parent / '.env'))
    args = parser.parse_args()
    base = Path(__file__).resolve().parent
    config = load_config(args.env, str(base / 'services.yaml'), mock=args.mock)
    if config.database_path != ':memory:' and not Path(config.database_path).is_absolute():
        config.database_path = str(base / config.database_path)
    if not Path(config.log_file).is_absolute():
        config.log_file = str(base / config.log_file)
    setup_logging(config.log_level, config.log_file)
    try:
        import tkinter as tk
    except ImportError:
        parser.exit(1, 'Tkinter ausente. Instale o componente Tcl/Tk do Python para abrir a interface.\n')
    try:
        root = tk.Tk()
    except tk.TclError:
        parser.exit(1, 'Não foi possível iniciar Tcl/Tk. Verifique a instalação do Python e a sessão gráfica.\n')
    DesktopApp(root, config)
    root.mainloop()


if __name__ == '__main__':
    main()
