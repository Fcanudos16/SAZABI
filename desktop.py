"""Native local desktop window. No browser, HTTP server or listening port."""
import argparse
import logging
from pathlib import Path
from queue import Queue, Empty
from threading import Thread
from dataclasses import dataclass, field

from core.bootstrap import build_agent
from core.config import load_config
from notifications.notifier import NullNotifier
from utils.logger import setup_logging


@dataclass
class ConnectRequest:
    key: str = field(repr=False)


@dataclass
class OllamaRequest:
    action: str
    model: str = ''


class AgentWorker:
    """Creates, uses and closes SQLite on its owning worker thread."""
    def __init__(self, config, factory=build_agent, snapshots=False):
        self.snapshots = snapshots
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
                             else 'Abra Configuração para conectar a Tavily. Histórico local disponível.'))
            self._snapshot(agent)
            while True:
                command = self.commands.get()
                if command is None:
                    break
                if isinstance(command, OllamaRequest):
                    try:
                        from analysis.ai_provider import list_models
                        from core.connection import configure_ollama
                        if command.action == 'list':
                            self.events.put(('ollama_models', list_models()))
                        else:
                            configure_ollama(agent, command.model)
                            self.events.put(('ollama_ready', 'IA local ativada: ' + command.model if command.model else 'IA local desativada.'))
                    except (ValueError, OSError) as error:
                        self.events.put(('ollama_error', str(error) if isinstance(error, ValueError) else 'Não foi possível salvar a configuração local.'))
                    except Exception:
                        self.events.put(('ollama_error', 'Falha ao configurar Ollama. Tente novamente.'))
                    continue
                if isinstance(command, ConnectRequest):
                    from core.connection import connect
                    from utils.http_client import FetchError
                    try:
                        connect(agent, command.key)
                        self.events.put(('connected', 'Tavily conectada. Chave salva. Você já pode pesquisar.'))
                    except (FetchError, ValueError) as error:
                        self.events.put(('connection_error', str(error)))
                    except OSError:
                        self.events.put(('connection_error', 'Não foi possível salvar o .env. Confira a permissão da pasta.'))
                    except Exception:
                        self.events.put(('connection_error', 'Falha ao conectar. Confira a rede e tente novamente.'))
                    finally:
                        command.key = ''
                    continue
                try:
                    reply = agent.handle(command)
                    self.events.put(('reply', reply))
                    self._snapshot(agent)
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

    def _snapshot(self, agent):
        if self.snapshots:
            try:
                from core.dashboard import dashboard_snapshot
                self.events.put(('snapshot', dashboard_snapshot(agent.db)))
            except Exception:
                logging.getLogger('sazabi.desktop').exception('Falha ao atualizar painel')
                self.events.put(('dashboard_error', 'Não foi possível atualizar as métricas locais.'))

    def close(self):
        self.commands.put(None)


class DesktopApp:
    def __init__(self, root, config, factory=build_agent):
        from ui.layout import build_layout
        self.root, self.busy, self.closing = root, True, False
        self.config, self.paused, self.failed = config, False, False
        self.ready, self.page, self.settings_window = False, 'dashboard', None
        build_layout(self, root, config)
        self.worker = AgentWorker(config, factory=factory, snapshots=True)
        self.set_busy(True)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.bind('<Destroy>', self._on_destroy, add='+')
        self.poll_job = root.after(75, self.poll)

    def _on_destroy(self, event):
        if event.widget is self.root:
            if self.poll_job:
                self.root.after_cancel(self.poll_job)
                self.poll_job = None
            self.worker.close()

    def append(self, author, text):
        self.welcome.pack_forget()
        self.transcript.pack(fill='both', expand=True)
        self.output.configure(state='normal')
        self.output.insert('end', author + '\n', 'user' if author == 'Você' else 'assistant')
        self.output.insert('end', text + '\n\n', 'user_body' if author == 'Você' else 'assistant_body')
        self.output.configure(state='disabled')
        self.output.see('end')

    def prepare_search(self, text='procure empresas em '):
        if self.busy or self.closing or self.paused or self.failed:
            return
        self.show_page('chat')
        self.entry.delete(0, 'end')
        self.entry.insert(0, text)
        self.entry.focus_set()
        self.entry.icursor('end')

    def open_search(self):
        self.prepare_search()
        return 'break'

    def show_page(self, page):
        self.page = page
        self.dashboard.pack_forget()
        self.chat_page.pack_forget()
        (self.dashboard if page == 'dashboard' else self.chat_page).pack(fill='both', expand=True)
        title = 'Painel' if page == 'dashboard' else 'Conversa'
        heading = 'Visão geral' if page == 'dashboard' else 'Pesquisa e memória'
        if self.config.mock:
            heading += ' · Demonstração'
        self.page_title.configure(text=heading)
        self.nav_choice.set(title)
        for name, button in self.nav_buttons.items():
            button.select(name == title)

    def toggle_pause(self):
        if self.busy or self.closing or self.failed or not self.ready:
            return
        self.paused = not self.paused
        self.set_busy(False)
        self.status.set('Pausado. Retome na configuração para executar novos comandos.' if self.paused else 'Pronto. Comandos disponíveis.')
        if self.settings_window and self.settings_window.winfo_exists():
            self.pause_button.configure(text='Retomar comandos' if self.paused else 'Pausar comandos')

    def open_settings(self):
        import tkinter as tk
        from ui.tokens import COLORS as C, SPACE as S
        from ui.components import label, wrapping_label
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return
        window = tk.Toplevel(self.root)
        self.settings_window = window
        window.title('Configuração — SAZABI')
        window.configure(bg=C['surface'])
        width = min(510, self.root.winfo_screenwidth()-40)
        window.geometry(f'{width}x710')
        window.minsize(400, 600)
        window.transient(self.root)
        from ui.window_chrome import dark_titlebar
        window.after_idle(lambda: dark_titlebar(window))
        body = tk.Frame(window, bg=C['surface'])
        body.pack(fill='both', expand=True, padx=S['xl'], pady=S['xl'])
        label(body, 'Seu ambiente', self.fonts, 'heading').pack(anchor='w', pady=(0, 14))
        mode = 'Demonstração, sem chamadas externas' if self.config.mock else 'Local, com dados reais'
        wrapping_label(body, mode, self.fonts, color='text').pack(fill='x', pady=(0, 14))
        source = 'Chave Tavily configurada; conexão ainda não verificada.' if self.config.search_api_key else 'Pesquisa online não configurada.'
        self.connection_status = tk.StringVar(value=source)
        self.connection_label = wrapping_label(body, '', self.fonts)
        self.connection_label.configure(textvariable=self.connection_status)
        self.connection_label.pack(fill='x')
        wrapping_label(body, 'Chave Tavily · obtenha em app.tavily.com. A validação consulta sua conta; as pesquisas usam o saldo do seu plano.', self.fonts).pack(fill='x', pady=(10, 8))
        self.key_entry = tk.Entry(body, show='•', bg=C['raised'], fg=C['text'], insertbackground=C['text'], font=self.fonts['body'])
        self.key_entry.pack(fill='x', ipady=8)
        self.connect_button = self.action_button(body, 'Salvar e conectar', self.connect_api, navigation=True, width=185)
        self.connect_button.pack(anchor='w', pady=(10, 12))
        self.connect_button.configure(state='disabled' if self.busy or self.failed else 'normal')
        wrapping_label(body, 'Deixe vazio para verificar a chave já configurada. A chave fica no .env local, fora do histórico e do Git.', self.fonts, 'small').pack(fill='x', pady=(0, 16))
        wrapping_label(body, 'Automações: execução sob demanda. Nenhum contato é enviado automaticamente.', self.fonts).pack(fill='x', pady=(0, 16))
        self.action_button(body, 'IA local (Ollama)', self.open_ollama, navigation=True, width=185).pack(anchor='w', pady=(0, 12))
        motion = tk.Checkbutton(body, text='Reduzir animações', variable=self.reduced_motion,
            bg=C['surface'], fg=C['text'], selectcolor=C['raised'], activebackground=C['surface'],
            activeforeground=C['text'], font=self.fonts['body'], highlightcolor=C['focus'],
            command=lambda: self.indicator.set(self.indicator.state))
        motion.pack(anchor='w', pady=(0, 16))
        self.pause_button = self.action_button(body, 'Retomar comandos' if self.paused else 'Pausar comandos',
                                               self.toggle_pause, navigation=True, width=185)
        self.pause_button.pack(anchor='w')
        self.pause_button.configure(state='disabled' if self.busy or self.failed or not self.ready else 'normal')
        wrapping_label(body, 'A pausa bloqueia novos comandos nesta janela. Não interrompe operações em andamento.', self.fonts, 'small').pack(fill='x', pady=(10, 16))
        close = self.action_button(body, 'Fechar', window.destroy, navigation=True)
        close.pack(side='bottom', anchor='e')
        window.bind('<Escape>', lambda e: window.destroy())
        window.grab_set()
        close.focus_set()

    def connect_api(self):
        if self.busy or self.failed or self.closing:
            return
        key = self.key_entry.get().strip() or self.config.search_api_key
        self.key_entry.delete(0, 'end')
        if not key:
            self.connection_status.set('Cole a chave Tavily no campo acima.')
            return
        self.set_busy(True)
        self.connection_status.set('Validando a chave na Tavily…')
        self.worker.commands.put(ConnectRequest(key))

    def open_ollama(self):
        import tkinter as tk
        from tkinter import ttk
        from ui.components import wrapping_label
        from ui.tokens import COLORS as C
        if getattr(self, 'ollama_window', None) and self.ollama_window.winfo_exists():
            self.ollama_window.lift()
            return
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.destroy()
        window = self.ollama_window = tk.Toplevel(self.root)
        window.title('IA local — Ollama')
        window.configure(bg=C['surface'])
        window.geometry('510x480')
        window.transient(self.root)
        body = tk.Frame(window, bg=C['surface'])
        body.pack(fill='both', expand=True, padx=24, pady=24)
        wrapping_label(body, 'Interpretação local das evidências', self.fonts, 'heading', 'text').pack(fill='x')
        wrapping_label(body, 'Instale o Ollama em ollama.com/download e baixe um modelo de texto local. Mantenha o Ollama aberto e clique em Atualizar modelos.', self.fonts).pack(fill='x', pady=12)
        self.ollama_status = tk.StringVar(value='Modelo atual: ' + (self.config.ollama_model if self.config.ai_provider == 'ollama' else 'IA desativada'))
        status = wrapping_label(body, '', self.fonts)
        status.configure(textvariable=self.ollama_status)
        status.pack(fill='x', pady=10)
        self.ollama_model = ttk.Combobox(body, state='readonly', values=[])
        self.ollama_model.pack(fill='x', pady=8)
        self.ollama_controls = []
        for text, action in [('Atualizar modelos', lambda: self.ollama_action('list')),
                             ('Ativar modelo', lambda: self.ollama_action('activate')),
                             ('Desativar IA', lambda: self.ollama_action('disable'))]:
            button = self.action_button(body, text, action, navigation=True, width=190)
            button.pack(anchor='w', pady=3)
            self.ollama_controls.append(button)
        wrapping_label(body, 'Depois, use /ai Nome da empresa na conversa. A IA lê evidências salvas e não altera o banco ou a pontuação.', self.fonts, 'small').pack(fill='x', pady=12)
        window.bind('<Escape>', lambda e: window.destroy())
        window.grab_set()
        self.set_busy(self.busy)

    def ollama_action(self, action):
        if self.busy or self.failed or self.closing:
            return
        model = self.ollama_model.get() if action == 'activate' else ''
        if action == 'activate' and not model:
            self.ollama_status.set('Atualize a lista e selecione um modelo instalado.')
            return
        self.set_busy(True)
        self.ollama_status.set('Consultando o Ollama local…')
        self.worker.commands.put(OllamaRequest(action, model))

    def set_busy(self, value):
        self.busy = value
        disabled = value or self.paused or self.failed or self.closing
        for button in self.buttons:
            button.configure(state='disabled' if disabled else 'normal')
        self.entry.configure(state='disabled' if disabled else 'normal')
        self.send_button.configure(text='Aguarde' if value else 'Enviar')
        state = 'ERRO' if self.failed else 'PAUSADO' if self.paused else 'PROCESSANDO' if value else 'ONLINE'
        if not self.ready and not self.failed:
            state = 'OFFLINE'
        self.indicator.set(state)
        if getattr(self, 'ollama_window', None) and self.ollama_window.winfo_exists():
            for button in self.ollama_controls:
                button.configure(state='disabled' if value or self.failed or self.closing else 'normal')
        if self.settings_window and self.settings_window.winfo_exists():
            self.pause_button.configure(state='disabled' if value or self.failed or self.closing else 'normal')
            self.connect_button.configure(state='disabled' if value or self.failed or self.closing else 'normal')
        if not disabled and self.page == 'chat':
            self.entry.focus_set()

    def submit(self, command=None):
        if self.busy or self.closing or self.paused or self.failed:
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
        self.show_page('chat')
        self.append('Você', text)
        self.set_busy(True)
        self.status.set('Processando… você pode rolar e copiar os resultados.')
        self.worker.commands.put(text)

    def poll(self):
        self.poll_job = None
        try:
            while True:
                kind, text = self.worker.events.get_nowait()
                if kind in ('ready', 'reply'):
                    self.ready = True
                    if kind == 'reply':
                        self.append('SAZABI', text)
                    if not self.closing:
                        self.set_busy(False)
                        self.status.set(text if kind == 'ready' else 'Pronto.')
                        if kind == 'reply' and text.startswith(('Ocorreu um erro interno', 'Falha ao processar')):
                            self.indicator.set('ERRO')
                            self.status.set('O comando falhou. Consulte o log ou tente outra ação.')
                elif kind == 'snapshot':
                    self.dashboard.update_snapshot(text)
                elif kind.startswith('ollama_'):
                    self.set_busy(False)
                    if getattr(self, 'ollama_window', None) and self.ollama_window.winfo_exists():
                        if kind == 'ollama_models':
                            self.ollama_model.configure(values=text)
                            self.ollama_model.set(self.config.ollama_model if self.config.ollama_model in text else text[0] if text else '')
                            self.ollama_status.set(f'{len(text)} modelo(s) local(is) disponível(is).' if text else 'Nenhum modelo local. Baixe um pelo Ollama e atualize a lista.')
                        else:
                            self.ollama_status.set(text)
                    self.status.set('Lista de modelos atualizada.' if kind == 'ollama_models' else text)
                elif kind in ('connected', 'connection_error'):
                    self.set_busy(False)
                    self.status.set(text)
                    if self.settings_window and self.settings_window.winfo_exists():
                        self.connection_status.set(text)
                    if kind == 'connection_error':
                        self.indicator.set('ERRO')
                    else:
                        self.dashboard.source_label.configure(text='Tavily conectada')
                        self.chat_source.configure(text='Tavily conectada · pesquisas reais sob demanda')
                elif kind == 'dashboard_error':
                    self.status.set(text)
                elif kind == 'error':
                    self.failed = True
                    self.show_page('chat')
                    self.append('SAZABI', text)
                    self.set_busy(False)
                    self.status.set(text)
                elif kind == 'closed' and self.closing:
                    self.root.destroy()
                    return
                elif kind == 'closed':
                    self.failed = True
                    self.set_busy(False)
                    self.indicator.set('ERRO' if not self.ready else 'OFFLINE')
        except Empty:
            pass
        if self.closing and not self.worker.thread.is_alive():
            self.root.destroy()
            return
        self.poll_job = self.root.after(75, self.poll)

    def close(self):
        if self.closing:
            return
        self.closing = True
        self.set_busy(True)
        self.status.set('Encerrando após a operação atual para fechar o banco com segurança…')
        self.worker.close()


def main():
    parser = argparse.ArgumentParser(description='SAZABI desktop local')
    parser.add_argument('--env', default=str(Path(__file__).parent / '.env'))
    args = parser.parse_args()
    base = Path(__file__).resolve().parent
    config = load_config(args.env, str(base / 'services.yaml'))
    if config.database_path != ':memory:' and not Path(config.database_path).is_absolute():
        config.database_path = str(base / config.database_path)
    if not Path(config.log_file).is_absolute():
        config.log_file = str(base / config.log_file)
    setup_logging(config.log_level, config.log_file)
    return run_desktop(config)


def run_desktop(config):
    """Open the desktop independently of external API configuration."""
    try:
        import tkinter as tk
    except ImportError:
        print('Tkinter ausente. Instale o componente Tcl/Tk do Python para abrir a interface.')
        return 1
    try:
        root = tk.Tk()
    except tk.TclError:
        print('Não foi possível iniciar Tcl/Tk. Verifique a instalação do Python e a sessão gráfica.')
        return 1
    DesktopApp(root, config)
    root.mainloop()
    return 0


if __name__ == '__main__':
    main()
