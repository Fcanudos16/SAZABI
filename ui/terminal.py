"""Small secondary results console. Hiding it never stops the worker."""
import tkinter as tk
from tkinter import ttk
from ui import native

BG, FG, MUTED, BORDER = '#080d0a', '#8fdfa7', '#72937b', '#254331'
FONT = ('Consolas', 10)


def button(parent, text, command):
    return tk.Button(parent, text=text, command=command, bg=BG, fg=FG, activebackground=BORDER,
                     activeforeground='#c9fbd5', font=FONT, relief='flat', bd=0, padx=9, pady=5,
                     highlightthickness=1, highlightbackground=BORDER, takefocus=True)


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
        body = tk.Frame(self.window, bg=BG)
        body.pack(fill='both', expand=True, padx=1, pady=1)
        header = tk.Frame(body, bg=BG)
        header.pack(fill='x', padx=12, pady=(8, 4))
        tk.Label(header, text='SAZABI / TERMINAL', bg=BG, fg=FG, font=('Consolas', 11, 'bold')).pack(side='left')
        button(header, '×', self.hide).pack(side='right')
        actions = tk.Frame(body, bg=BG)
        actions.pack(fill='x', padx=12, pady=(0, 6))
        for text, command in [('Resultados', '/results'), ('Histórico', '/history'), ('Ajuda', '/help')]:
            button(actions, text, lambda value=command: app.submit(value)).pack(side='left', padx=(0, 5))
        self.status = tk.StringVar(value='IDLE · clique direito no mascote para configurar')
        tk.Label(body, textvariable=self.status, anchor='w', bg=BG, fg=MUTED, font=('Consolas', 9)).pack(side='bottom', fill='x', padx=12, pady=8)
        composer = tk.Frame(body, bg=BG)
        composer.pack(side='bottom', fill='x', padx=12, pady=(5, 0))
        tk.Label(composer, text='>', bg=BG, fg=FG, font=FONT).pack(side='left', padx=(0, 8))
        self.entry = tk.Entry(composer, bg=BG, fg=FG, insertbackground=FG, font=FONT, relief='flat',
                              disabledbackground=BG, disabledforeground=MUTED)
        self.entry.pack(side='left', fill='x', expand=True, ipady=6)
        self.entry.bind('<Return>', lambda event: app.submit())
        self.send = button(composer, 'Enviar', app.submit)
        self.send.pack(side='right', padx=(5, 0))
        content = tk.Frame(body, bg=BG)
        content.pack(fill='both', expand=True, padx=12, pady=5)
        # Native Windows themes ignore scrollbar colors; use a dedicated clam style.
        style = ttk.Style(self.window)
        style.theme_use('clam')
        style.configure('Sazabi.Vertical.TScrollbar', background=BORDER, troughcolor=BG,
                        bordercolor=BG, lightcolor=BORDER, darkcolor=BORDER,
                        arrowcolor=FG, width=12, arrowsize=12)
        style.map('Sazabi.Vertical.TScrollbar', background=[('pressed', '#659f76'), ('active', '#3e7050')],
                  lightcolor=[('active', '#3e7050')], darkcolor=[('active', '#3e7050')])
        scrollbar = self.scrollbar = ttk.Scrollbar(content, orient='vertical', style='Sazabi.Vertical.TScrollbar')
        scrollbar.pack(side='right', fill='y')
        self.output = tk.Text(content, bg=BG, fg=FG, font=FONT, relief='flat', wrap='word',
                              selectbackground=BORDER, state='disabled', yscrollcommand=scrollbar.set,
                              padx=5, pady=6, spacing3=6, takefocus=True)
        self.output.pack(fill='both', expand=True)
        scrollbar.configure(command=self.output.yview)
        self.output.tag_configure('event', foreground=MUTED)
        self.output.tag_configure('user', foreground='#c9fbd5')
        self.output.tag_configure('error', foreground='#edb58b')
        self.window.protocol('WM_DELETE_WINDOW', self.hide)
        self.window.bind('<Escape>', lambda event: self.hide())
        self.window.bind('<FocusIn>', lambda event: setattr(self, 'focus_seen', True), add='+')
        self.window.bind('<FocusOut>', self._focus_out, add='+')
        self.append('Clique direito no mascote → Configuração para Tavily/Ollama.\nDigite uma pesquisa ou /help.\n', 'event')

    def _focus_out(self, event):
        if self.visible:
            self.window.after(100, self.check_focus)

    def check_focus(self):
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
        self.visible = False
        self.window.withdraw()

    def busy(self, busy):
        self.entry.configure(state='disabled' if busy else 'normal')
        self.send.configure(state='disabled' if busy else 'normal')
