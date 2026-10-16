"""On-demand connection settings, separate from the results terminal."""
import tkinter as tk
from tkinter import ttk
from core.worker import GroqRequest
from ui.theme import SHELL_BG as BG, FG, MUTED, FONT, button, titlebar
from ui import native


class Preferences:
    def __init__(self, app):
        self.app = app
        self.window = tk.Toplevel(app.root)
        self.window.title('SAZABI · conexões locais')
        self.window.configure(bg=BG)
        self.window.resizable(False, False)
        chrome = titlebar(self.window, 'SAZABI / CONFIGURAÇÃO', self.window.destroy)
        self.window.attributes('-topmost', app.always_on_top.get())
        area = native.work_area(app.root)
        x, y = native.place_near(app.x, app.y, app.atlas.width, app.atlas.height, 460, 450, area)
        self.window.geometry(f'460x450{x:+d}{y:+d}')
        self.status = tk.StringVar(value='Tavily configurada no backend.' if app.config.search_api_key else 'Tavily ausente. Configure SEARCH_API_KEY no .env e reinicie.')
        body = tk.Frame(self.window, bg=BG)
        body.pack(fill='both', expand=True, padx=18, pady=14)
        tk.Label(body, text='CONEXÕES / SAZABI', bg=BG, fg=FG, font=('Consolas', 12, 'bold')).pack(anchor='w')
        tk.Label(body, text='Credenciais somente no arquivo .env.\nApós alterar o arquivo, reinicie o SAZABI.', bg=BG, fg=MUTED, font=FONT, justify='left').pack(anchor='w', pady=12)
        self.controls = []
        tk.Label(body, text='Groq · modelo hospedado na nuvem', bg=BG, fg=MUTED, font=FONT).pack(anchor='w', pady=(12, 5))
        self.model = ttk.Combobox(body, state='readonly',style='Sazabi.TCombobox')
        self.model.pack(fill='x')
        if app.config.ai_provider == 'groq':
            self.model.configure(values=[app.config.groq_model])
            self.model.set(app.config.groq_model)
        row = tk.Frame(body, bg=BG)
        row.pack(fill='x', pady=7)
        for label, action in [('Atualizar', 'list'), ('Ativar', 'activate'), ('Desativar', 'disable')]:
            self.add_button(row, label, lambda value=action: self.groq(value)).pack(side='left', padx=(0, 7))
        tk.Label(body, text='Configure GROQ_API_KEY no .env. Use /groq Nome da empresa\npara interpretar evidências já coletadas.',
                 bg=BG, fg=MUTED, font=('Consolas', 9), justify='left').pack(anchor='w', pady=5)
        self.add_button(body,'Perfil comercial / configurações de qualificação',app.open_profile).pack(anchor='w',pady=4)
        tk.Label(body, textvariable=self.status, bg=BG, fg=FG, font=FONT, wraplength=420, justify='left').pack(fill='x', pady=12)
        self.window.bind('<Escape>', lambda event: self.window.destroy())
        self.window.update_idletasks()
        width=min(max(460,body.winfo_reqwidth()+36),area[2]-area[0]-24)
        height=min(max(450,body.winfo_reqheight()+28+chrome.winfo_reqheight()),area[3]-area[1]-24)
        x,y=native.place_near(app.x,app.y,app.atlas.width,app.atlas.height,width,height,area)
        self.window.geometry(f'{width}x{height}{x:+d}{y:+d}')
        native.position(self.window, x, y)
        self.busy(app.busy)

    def add_button(self, parent, text, command):
        widget = button(parent, text, command)
        self.controls.append(widget)
        return widget

    def show(self):
        native.restore(self.window)
        self.window.deiconify()
        self.window.attributes('-topmost', self.app.always_on_top.get())
        self.window.lift()
        self.model.focus_force()

    def busy(self, value):
        for widget in self.controls:
            widget.configure(state='disabled' if value or self.app.failed or self.app.closing else 'normal')

    def groq(self, action):
        if self.app.busy:
            return
        model = self.model.get() if action == 'activate' else ''
        if action == 'activate' and not model:
            self.status.set('Atualize a lista e selecione um modelo disponível.')
            return
        self.app.queue_request(GroqRequest(action, model))
        self.status.set('Consultando Groq…')

    def event(self, kind, value):
        if kind == 'groq_models':
            self.model.configure(values=value)
            self.model.set(self.app.config.groq_model if self.app.config.groq_model in value else value[0] if value else '')
            self.status.set(f'{len(value)} modelo(s) disponível(is).' if value else 'Nenhum modelo disponível no Groq.')
        else:
            self.status.set(value)
