"""On-demand connection settings, separate from the results terminal."""
import tkinter as tk
from tkinter import ttk
from core.worker import ConnectRequest, OllamaRequest
from ui.terminal import BG, FG, MUTED, FONT, button
from ui import native


class Preferences:
    def __init__(self, app):
        self.app = app
        self.window = tk.Toplevel(app.root)
        self.window.title('SAZABI · conexões locais')
        self.window.configure(bg=BG)
        self.window.resizable(False, False)
        self.window.attributes('-topmost', app.always_on_top.get())
        area = native.work_area(app.root)
        x, y = native.place_near(app.x, app.y, app.atlas.width, app.atlas.height, 460, 410, area)
        self.window.geometry(f'460x410{x:+d}{y:+d}')
        self.status = tk.StringVar(value='Tavily configurada.' if app.config.search_api_key else 'Informe a chave Tavily para pesquisar.')
        body = tk.Frame(self.window, bg=BG)
        body.pack(fill='both', expand=True, padx=18, pady=14)
        tk.Label(body, text='CONEXÕES / SAZABI', bg=BG, fg=FG, font=('Consolas', 12, 'bold')).pack(anchor='w')
        tk.Label(body, text='Tavily · chave em app.tavily.com', bg=BG, fg=MUTED, font=FONT).pack(anchor='w', pady=(14, 5))
        self.key = tk.Entry(body, show='•', bg=BG, fg=FG, insertbackground=FG, font=FONT)
        self.key.pack(fill='x', ipady=4)
        self.controls = []
        self.add_button(body, 'Salvar e conectar', self.connect).pack(anchor='w', pady=7)
        tk.Label(body, text='Ollama · modelo instalado neste computador', bg=BG, fg=MUTED, font=FONT).pack(anchor='w', pady=(12, 5))
        self.model = ttk.Combobox(body, state='readonly')
        self.model.pack(fill='x')
        if app.config.ai_provider == 'ollama':
            self.model.configure(values=[app.config.ollama_model])
            self.model.set(app.config.ollama_model)
        row = tk.Frame(body, bg=BG)
        row.pack(fill='x', pady=7)
        for label, action in [('Atualizar', 'list'), ('Ativar', 'activate'), ('Desativar', 'disable')]:
            self.add_button(row, label, lambda value=action: self.ollama(value)).pack(side='left', padx=(0, 7))
        tk.Label(body, text='Ollama deve estar aberto. Use /ai Nome da empresa\npara interpretar evidências já coletadas.',
                 bg=BG, fg=MUTED, font=('Consolas', 9), justify='left').pack(anchor='w', pady=5)
        tk.Label(body, textvariable=self.status, bg=BG, fg=FG, font=FONT, wraplength=420, justify='left').pack(fill='x', pady=12)
        self.window.bind('<Escape>', lambda event: self.window.destroy())
        self.window.update_idletasks()
        native.position(self.window, x, y)
        self.busy(app.busy)

    def add_button(self, parent, text, command):
        widget = button(parent, text, command)
        self.controls.append(widget)
        return widget

    def show(self):
        self.window.deiconify()
        self.window.attributes('-topmost', self.app.always_on_top.get())
        self.window.lift()
        self.key.focus_force()

    def busy(self, value):
        for widget in self.controls:
            widget.configure(state='disabled' if value or self.app.failed or self.app.closing else 'normal')

    def connect(self):
        if self.app.busy:
            return
        key = self.key.get().strip() or self.app.config.search_api_key
        self.key.delete(0, 'end')
        if not key:
            self.status.set('Cole sua chave Tavily acima.')
            return
        self.app.queue_request(ConnectRequest(key))
        self.status.set('Validando a conexão Tavily…')

    def ollama(self, action):
        if self.app.busy:
            return
        model = self.model.get() if action == 'activate' else ''
        if action == 'activate' and not model:
            self.status.set('Atualize a lista e selecione um modelo instalado.')
            return
        self.app.queue_request(OllamaRequest(action, model))
        self.status.set('Consultando Ollama local…')

    def event(self, kind, value):
        if kind == 'ollama_models':
            self.model.configure(values=value)
            self.model.set(self.app.config.ollama_model if self.app.config.ollama_model in value else value[0] if value else '')
            self.status.set(f'{len(value)} modelo(s) local(is).' if value else 'Nenhum modelo local. Instale um pelo Ollama e atualize.')
        else:
            self.status.set(value)
