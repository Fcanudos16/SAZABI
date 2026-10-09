"""On-demand native LAYLA terminal, independent of the prospecting worker."""
import tkinter as tk
from tkinter import ttk
from queue import Empty
from integrations.layla.session import LaylaSession
from ui import native
from ui.terminal import BG, FG, MUTED, BORDER, FONT, button

class AITerminal:
    def __init__(self, app, session_factory=LaylaSession):
        self.app, self.session_factory = app, session_factory
        self.session, self.job, self.closed = None, None, False
        self.history = []
        self.window = tk.Toplevel(app.root)
        self.window.withdraw()
        self.window.title('SAZABI AI TERMINAL')
        self.window.configure(bg=BORDER)
        self.window.resizable(False, False)
        body = tk.Frame(self.window, bg=BG)
        body.pack(fill='both', expand=True, padx=1, pady=1)
        header = tk.Frame(body, bg=BG)
        header.pack(fill='x', padx=12, pady=10)
        tk.Label(header, text='SAZABI AI TERMINAL', bg=BG, fg=FG, font=('Consolas', 12, 'bold')).pack(side='left')
        button(header, 'Fechar', self.hide).pack(side='right')
        actions = tk.Frame(body, bg=BG)
        actions.pack(fill='x', padx=12)
        self.connect_button = button(actions, 'Conectar', lambda: self.request('connect'))
        self.connect_button.pack(side='left')
        self.reset_button = button(actions, 'Nova sessão', lambda: self.request('reset'))
        self.reset_button.pack(side='left', padx=6)
        self.status = tk.StringVar(value='LAYLA · desconectada')
        tk.Label(body, textvariable=self.status, bg=BG, fg=MUTED, font=('Consolas', 9), anchor='w').pack(fill='x', padx=12, pady=8)
        composer = tk.Frame(body, bg=BG)
        composer.pack(side='bottom', fill='x', padx=12, pady=10)
        self.entry = tk.Entry(composer, bg=BG, fg=FG, insertbackground=FG, font=FONT, relief='flat')
        self.entry.pack(side='left', fill='x', expand=True, ipady=6)
        self.entry.bind('<Return>', lambda event: self.send())
        self.send_button = button(composer, 'Enviar', self.send)
        self.send_button.pack(side='right', padx=6)
        content = tk.Frame(body, bg=BG)
        content.pack(fill='both', expand=True, padx=12, pady=5)
        scrollbar = ttk.Scrollbar(content, style='Sazabi.Vertical.TScrollbar')
        scrollbar.pack(side='right', fill='y')
        self.output = tk.Text(content, bg=BG, fg=FG, font=FONT, wrap='word', state='disabled',
                              relief='flat', yscrollcommand=scrollbar.set, padx=8, pady=8)
        self.output.pack(fill='both', expand=True)
        scrollbar.configure(command=self.output.yview)
        self.window.protocol('WM_DELETE_WINDOW', self.hide)
        self.window.bind('<Escape>', lambda event: self.hide())
        self.append('SAZABI', 'Este terminal envia somente o texto que você escrever à LAYLA. As pesquisas não são enviadas automaticamente.')
        self.poll()

    def append(self, role, text):
        self.history.append((role, text))
        self.history = self.history[-100:]
        self.output.configure(state='normal')
        self.output.insert('end', role + '\n' + text + '\n\n')
        lines = int(self.output.index('end-1c').split('.')[0])
        if lines > 2500:
            self.output.delete('1.0', f'{lines-2500}.0')
        self.output.configure(state='disabled')
        self.output.see('end')

    def show(self, draft=''):
        area = native.work_area(self.app.root)
        width, height = min(620, area[2]-area[0]-24), min(480, area[3]-area[1]-24)
        x, y = native.place_near(self.app.x, self.app.y, self.app.atlas.width, self.app.atlas.height, width, height, area)
        self.window.geometry(f'{width}x{height}{x:+d}{y:+d}')
        self.window.attributes('-topmost', self.app.always_on_top.get())
        self.window.deiconify()
        native.position(self.window, x, y)
        self.window.lift()
        if draft and str(self.entry['state']) != 'disabled':
            self.entry.delete(0, 'end')
            self.entry.insert(0, draft)
        self.entry.focus_force()
        if self.session is None:
            self.request('connect')

    def busy(self, value):
        for control in (self.entry, self.send_button, self.connect_button, self.reset_button):
            control.configure(state='disabled' if value else 'normal')

    def request(self, action, text=''):
        if self.closed:
            return False
        try:
            if self.session is None:
                self.session = self.session_factory(self.app.config)
            accepted = self.session.submit(action, text)
        except ValueError:
            self.status.set('LAYLA · configuração inválida')
            self.append('SAZABI', 'Confira a configuração privada da integração LAYLA.')
            return False
        if not accepted:
            return False
        self.busy(True)
        self.status.set('LAYLA · processando…' if action == 'send' else 'LAYLA · conectando…')
        return True

    def send(self):
        text = self.entry.get().strip()
        if not text or len(text) > 2000:
            self.status.set('Digite uma mensagem de até 2.000 caracteres.')
            return
        import re
        if re.search(r'\btvly-[A-Za-z0-9_-]+', text):
            self.status.set('Não envie chaves ou credenciais no terminal.')
            return
        if self.request('send', text):
            self.entry.configure(state='normal')
            self.entry.delete(0, 'end')
            self.entry.configure(state='disabled')
            self.append('VOCÊ', text)

    def poll(self):
        self.job = None
        if self.closed:
            return
        if self.session:
            try:
                while True:
                    kind, message, state = self.session.events.get_nowait()
                    self.busy(False)
                    labels = {'connected': 'conectada', 'disconnected': 'desconectada',
                              'authentication_required': 'autenticação necessária', 'locked': 'STANDBY', 'rate_limited': 'limite de mensagens'}
                    self.status.set('LAYLA · ' + labels.get(state, 'desconectada'))
                    if kind == 'reset':
                        self.history.clear()
                        self.output.configure(state='normal')
                        self.output.delete('1.0', 'end')
                        self.output.configure(state='disabled')
                    self.append('LAYLA' if kind == 'reply' else 'SAZABI', message)
            except Empty:
                pass
        self.job = self.app.root.after(100, self.poll)

    def hide(self):
        self.window.withdraw()

    def close(self):
        self.closed = True
        if self.job:
            self.app.root.after_cancel(self.job)
            self.job = None
        if self.session:
            self.session.close()
