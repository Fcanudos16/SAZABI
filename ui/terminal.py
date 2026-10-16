"""Small secondary results console. Hiding it never stops the worker."""
import tkinter as tk
from tkinter import ttk
from ui import native

from ui.theme import BG, FG, MUTED, BORDER, FONT, BRIGHT, button, draggable


class ResultTerminal:
    def __init__(self, app):
        self.app = app
        self.window = tk.Toplevel(app.root)
        self.window.withdraw()
        self.window.title('SAZABI TERMINAL')
        self.window.overrideredirect(True)
        self.window.configure(bg=BORDER)
        self.window.resizable(False, False)
        self.visible, self.focus_seen = False, False
        self.focus_job = None
        body = self.body = tk.Frame(self.window, bg=BG)
        body.pack(fill='both', expand=True, padx=1, pady=1)
        header = tk.Frame(body, bg=BG)
        header.pack(fill='x', padx=12, pady=(8, 4))
        self.heading=tk.StringVar(value='SAZABI / TERMINAL')
        title = tk.Label(header, textvariable=self.heading, bg=BG, fg=FG, font=('Consolas', 11, 'bold'))
        title.pack(side='left')
        draggable(self.window, header, title)
        button(header, '×', self.hide).pack(side='right')
        actions = tk.Frame(body, bg=BG)
        actions.pack(fill='x', padx=12, pady=(0, 6))
        for column,(text, command) in enumerate([('Leads', '/leads'), ('Histórico', '/history'), ('Ajuda', '/help'), ('Visão geral', '/overview'), ('Tarefas', '/tasks')]):
            button(actions, text, lambda value=command: app.submit(value)).grid(row=0,column=column,sticky='w',padx=(0,5))
        button(actions, 'Último', app.show_last_result).grid(row=1,column=0,sticky='w')
        button(actions, 'Nova pesquisa', app.open_search).grid(row=1,column=1,sticky='w')
        self.cancel = button(actions, 'Cancelar', app.cancel_search)
        self.cancel.grid(row=1,column=2,sticky='w')
        button(actions, 'Perfil', lambda: app.submit('/profile')).grid(row=1,column=3,sticky='w')
        button(actions, 'Estratégias', lambda: app.submit('/strategies')).grid(row=1,column=4,sticky='w')
        for column,(label,command) in enumerate([('Saúde','/health'),('Backup','/backup'),('Manutenção','/maintenance')]):
            button(actions,label,lambda value=command:app.submit(value)).grid(row=2,column=column,sticky='w')
        self.cancel.configure(state='disabled')
        self.status = tk.StringVar(value='IDLE · clique direito no mascote para configurar')
        tk.Label(body, textvariable=self.status, anchor='w', bg=BG, fg=MUTED, font=('Consolas', 9)).pack(side='bottom', fill='x', padx=12, pady=8)
        composer = tk.Frame(body, bg=BG)
        composer.pack(side='bottom', fill='x', padx=12, pady=(5, 0))
        tk.Label(composer, text='>', bg=BG, fg=FG, font=FONT).pack(side='left', padx=(0, 8))
        self.entry = tk.Entry(composer, bg=BG, fg=FG, insertbackground=FG, font=FONT, relief='flat',
                              disabledbackground=BG, disabledforeground=MUTED)
        self.entry.pack(side='left', fill='x', expand=True, ipady=6)
        self.entry.bind('<Return>', self.enter)
        self.send = button(composer, 'Enviar', app.submit)
        self.send.pack(side='right', padx=(5, 0))
        from ui.countdown.embedded import ResearchTimer
        self.research_timer = ResearchTimer(self)
        content = self.content = tk.Frame(body, bg=BG)
        content.pack(fill='both', expand=True, padx=12, pady=5)
        scrollbar = self.scrollbar = ttk.Scrollbar(content, orient='vertical', style='Sazabi.Vertical.TScrollbar')
        scrollbar.pack(side='right', fill='y')
        self.output = tk.Text(content, bg=BG, fg=FG, font=FONT, relief='flat', wrap='word',
                              selectbackground=BORDER, state='disabled', yscrollcommand=scrollbar.set,
                              padx=5, pady=6, spacing3=6, takefocus=True)
        self.output.pack(fill='both', expand=True)
        scrollbar.configure(command=self.output.yview)
        self.output.tag_configure('event', foreground=MUTED)
        self.output.tag_configure('user', foreground=BRIGHT)
        self.output.tag_configure('error', foreground=BRIGHT)
        self.window.protocol('WM_DELETE_WINDOW', self.hide)
        self.window.bind('<Escape>', lambda event: self.hide())
        self.window.bind('<FocusIn>', lambda event: setattr(self, 'focus_seen', True), add='+')
        self.window.bind('<FocusOut>', self._focus_out, add='+')
        from ui.autocomplete import SlashAutocomplete
        self.autocomplete = SlashAutocomplete(self)
        self.last_skill_result = None
        self.execution_number=0
        self.current_query=''
        self.last_result=None
        self.append('Configurações de APIs e Groq: edite o .env e reinicie.\n/search e /research usam Tavily (créditos).\n/ai abre a LAYLA; o texto é um rascunho até você enviar.\n', 'event')

    def enter(self, event=None):
        if self.autocomplete.visible:
            return self.autocomplete.accept()
        self.app.submit()
        return 'break'

    def render_skill(self, result):
        self.last_skill_result = result
        labels={'completed':'Concluído','partial':'Parcial — confira limitações','failed':'Não concluído',
                'cancelled':'Cancelado','unconfigured':'Configuração necessária','needs_input':'Aguardando informação',
                'needs_confirmation':'Aguardando confirmação','ready':'Pronto'}
        self.status.set(labels.get(result['status'],result['status']))
        self.append(result.get('message') or result.get('error') or 'Sem resposta.',
                    'result' if result.get('success') else 'error')
        # Structured data is optional; render it without knowing the provider.
        if not result.get('message'):
            for company in result.get('data', {}).get('companies', []):
                self.append('\n'.join(str(company.get(key) or 'Não informado')
                            for key in ('name', 'segment', 'location', 'website')))
        self.output.yview_moveto(0)

    def begin(self, query):
        self.execution_number+=1
        self.current_query=query
        self.heading.set(f'SAZABI / EXECUÇÃO #{self.execution_number}')
        self.output.configure(state='normal')
        self.output.delete('1.0','end')
        self.output.configure(state='disabled')
        self.last_skill_result=None
        self.append(f'Execução local #{self.execution_number} · {query}', 'user')

    def remember_result(self):
        self.last_result=(self.output.get('1.0','end')[-200000:],self.status.get(),self.heading.get())

    def show_last_result(self):
        if self.last_result is None: return False
        text,status,heading=self.last_result
        self.output.configure(state='normal'); self.output.delete('1.0','end'); self.output.configure(state='disabled')
        self.append(text)
        self.status.set('Última pesquisa · '+status)
        self.heading.set(heading)
        self.output.yview_moveto(0)
        self.show()
        return True

    def _focus_out(self, event):
        if self.visible:
            if self.focus_job:
                self.app.root.after_cancel(self.focus_job)
            self.focus_job = self.app.root.after(100, self.check_focus)

    def check_focus(self):
        self.focus_job = None
        if self.visible and self.focus_seen and not native.is_foreground(self.window):
            self.hide()

    def append(self, text, tag='result'):
        self.output.configure(state='normal')
        self.output.insert('end', text + '\n', tag)
        # UI stays bounded. Complete research remains in SQLite, accessible via /results.
        lines = int(self.output.index('end-1c').split('.')[0])
        if lines > 2500:
            self.output.delete('1.0', f'{lines-2500}.0')
        self.output.configure(state='disabled')
        self.output.see('end')

    def show(self):
        left, top, right, bottom = native.work_area(self.app.root)
        width, height = min(620, right-left-24), min(440, bottom-top-24)
        x, y = native.place_near(self.app.x, self.app.y, self.app.atlas.width, self.app.atlas.height,
                                 width, height, (left, top, right, bottom))
        self.window.geometry(f'{width}x{height}{x:+d}{y:+d}')
        self.window.attributes('-topmost', self.app.always_on_top.get())
        self.visible, self.focus_seen = True, False
        self.window.deiconify()
        self.window.update_idletasks()
        native.position(self.window, x, y)
        self.window.lift()
        self.entry.focus_force()  # Only a deliberate user click opens/focuses this console.

    def hide(self):
        if self.focus_job:
            self.app.root.after_cancel(self.focus_job)
            self.focus_job = None
        self.visible = False
        self.autocomplete.hide()
        self.window.withdraw()

    def shutdown(self):
        if self.focus_job:
            self.app.root.after_cancel(self.focus_job)
            self.focus_job = None
        self.research_timer.close()

    def busy(self, busy):
        self.cancel.configure(state='normal' if busy and self.app.active_research and not (self.app.closing or self.app.failed or self.app.cancel_requested) else 'disabled')
        if busy:
            self.autocomplete.hide()
        self.entry.configure(state='disabled' if busy else 'normal')
        self.send.configure(state='disabled' if busy else 'normal')
