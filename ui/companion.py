"""Mascot-first desktop shell. All research runs on the existing worker thread."""
import json
import re
import time
import tkinter as tk
from pathlib import Path
from queue import Empty

from core.bootstrap import build_agent
from core.worker import AgentWorker
from ui.sprites import SpriteAtlas
from ui.terminal import ResultTerminal, BG, FG, FONT
from ui import native


STATE_EVENTS = {
    'COMMAND_STARTED': 'ANALYZING', 'SEARCH_STARTED': 'RESEARCHING',
    'SEARCH_PROCESSING': 'WORKING', 'TASK_PROCESSING': 'WORKING',
    'SEARCH_RESULT_FOUND': 'FOUND', 'SEARCH_COMPLETED': 'RESPONDING',
    'RESPONSE_READY': 'RESPONDING', 'TASK_ERROR': 'IDLE',
}


class CompanionApp:
    def __init__(self, root, config, factory=build_agent):
        self.root, self.config = root, config
        root.withdraw()
        self.busy, self.ready, self.failed, self.closing = True, False, False, False
        self.terminal, self.preferences, self.bubble = None, None, None
        self.poll_job, self.idle_job, self.bubble_job = None, None, None
        self.response_job, self.fade_job, self.found_until = None, None, 0
        self.state, self.notice, self.operation_failed = 'IDLE', None, False
        self.state_history = ['IDLE']
        self.always_on_top = tk.BooleanVar(root, True)
        self.reduced_motion = tk.BooleanVar(root, False)
        self.atlas = SpriteAtlas(root)
        self.x, self.y = 0, 0
        self.position_file = None if config.database_path == ':memory:' else Path(config.database_path).parent / 'companion.json'
        self._restore()
        root.title('SAZABI')
        root.overrideredirect(True)
        root.resizable(False, False)
        root.configure(bg='white')
        self.canvas = tk.Canvas(root, width=self.atlas.width, height=self.atlas.height,
                                bg='white', highlightthickness=0, borderwidth=0, cursor='hand2')
        self.canvas.pack()
        self.sprite = self.canvas.create_image(0, 0, anchor='nw', image=self.atlas.images['IDLE'])
        root.geometry(f'{self.atlas.width}x{self.atlas.height}+0+0')
        root.update_idletasks()
        native.position(root, self.x, self.y)
        area = native.work_area(root)
        if self.x == self.y == 0:
            self.x, self.y = area[2]-self.atlas.width-35, area[3]-self.atlas.height-25
        self._clamp(area)
        root.geometry(f'{self.atlas.width}x{self.atlas.height}{self.x:+d}{self.y:+d}')
        root.update_idletasks()
        native.no_activate(root)
        native.shape(root, self.atlas.regions['IDLE'])
        root.attributes('-topmost', self.always_on_top.get())
        root.deiconify()
        native.show_passive(root, self.x, self.y, self.atlas.width, self.atlas.height, self.always_on_top.get())
        self._drag = None
        self.canvas.bind('<ButtonPress-1>', self.press)
        self.canvas.bind('<B1-Motion>', self.drag)
        self.canvas.bind('<ButtonRelease-1>', self.release)
        self.canvas.bind('<Button-3>', self.context_menu)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.bind('<Destroy>', self._destroyed, add='+')
        self.worker = AgentWorker(config, factory=factory, progress=True)
        self.poll_job = root.after(75, self.poll)

    def _restore(self):
        if self.position_file:
            try:
                data = json.loads(self.position_file.read_text(encoding='utf-8'))
                self.x, self.y = int(data['x']), int(data['y'])
                if not (-100000 < self.x < 100000 and -100000 < self.y < 100000):
                    self.x = self.y = 0
                self.always_on_top.set(bool(data.get('topmost', True)))
                self.reduced_motion.set(bool(data.get('reduced_motion', False)))
            except (OSError, ValueError, TypeError, KeyError):
                pass

    def _save(self):
        if self.position_file:
            try:
                self.position_file.parent.mkdir(parents=True, exist_ok=True)
                temporary = self.position_file.with_suffix('.tmp')
                temporary.write_text(json.dumps({'x': self.x, 'y': self.y, 'topmost': self.always_on_top.get(),
                                                'reduced_motion': self.reduced_motion.get()}), encoding='utf-8')
                temporary.replace(self.position_file)
            except OSError:
                self.notify('Não foi possível salvar a posição do mascote.')

    def _clamp(self, area):
        left, top, right, bottom = area
        self.x = max(left, min(self.x, right-self.atlas.width))
        self.y = max(top, min(self.y, bottom-self.atlas.height))

    def press(self, event):
        self.dismiss_bubble()
        self._drag = (event.x_root, event.y_root, self.x, self.y, False)

    def drag(self, event):
        if self._drag:
            mx, my, x, y, moved = self._drag
            dx, dy = event.x_root-mx, event.y_root-my
            if moved or abs(dx)+abs(dy) > 6:
                self._drag = (mx, my, x, y, True)
                self.x, self.y = x+dx, y+dy
                native.show_passive(self.root, self.x, self.y, self.atlas.width, self.atlas.height, self.always_on_top.get())

    def release(self, event):
        if not self._drag:
            return
        moved = self._drag[4]
        self._drag = None
        if moved:
            self._clamp(native.work_area(self.root))
            native.show_passive(self.root, self.x, self.y, self.atlas.width, self.atlas.height, self.always_on_top.get())
            self._save()
        else:
            self.toggle_terminal()

    def get_terminal(self):
        if self.terminal is None:
            self.terminal = ResultTerminal(self)
        return self.terminal

    def toggle_terminal(self):
        terminal = self.get_terminal()
        self.dismiss_bubble()
        if terminal.visible:
            terminal.hide()
        else:
            terminal.show()
            terminal.busy(self.busy or self.failed or self.closing)

    def open_search(self):
        terminal = self.get_terminal()
        terminal.show()
        if not self.busy:
            terminal.entry.delete(0, 'end')
            terminal.entry.insert(0, 'procure empresas em ')
            terminal.entry.icursor('end')

    def open_settings(self):
        if self.preferences and self.preferences.window.winfo_exists():
            self.preferences.window.lift()
            return
        from ui.preferences import Preferences
        self.preferences = Preferences(self)

    def context_menu(self, event):
        menu = tk.Menu(self.root, tearoff=False, bg=BG, fg=FG, font=FONT)
        menu.add_command(label='Abrir / fechar terminal', command=self.toggle_terminal)
        menu.add_command(label='Nova pesquisa', command=self.open_search)
        menu.add_command(label='Configuração · Tavily / Ollama', command=self.open_settings)
        menu.add_separator()
        menu.add_checkbutton(label='Sempre no topo', variable=self.always_on_top, command=self.topmost_changed)
        menu.add_checkbutton(label='Reduzir movimento', variable=self.reduced_motion, command=self._save)
        menu.add_separator()
        menu.add_command(label='Encerrar SAZABI', command=self.close)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
            menu.destroy()

    def topmost_changed(self):
        self.root.attributes('-topmost', self.always_on_top.get())
        for window in (self.terminal.window if self.terminal else None,
                       self.preferences.window if self.preferences else None, self.bubble):
            if window and window.winfo_exists():
                window.attributes('-topmost', self.always_on_top.get())
        self._save()

    def set_state(self, state):
        if state == 'RESPONDING' and self.state == 'FOUND' and time.monotonic() < self.found_until:
            if self.response_job:
                self.root.after_cancel(self.response_job)
            self.response_job = self.root.after(max(1, int((self.found_until-time.monotonic())*1000)), self._respond)
            return
        if self.response_job:
            self.root.after_cancel(self.response_job)
            self.response_job = None
        if state == self.state:
            return
        self.state = state
        self.state_history.append(state)
        self.state_history = self.state_history[-100:]
        self.canvas.itemconfigure(self.sprite, image=self.atlas.images[state])
        native.shape(self.root, self.atlas.regions[state])
        if self.fade_job:
            self.root.after_cancel(self.fade_job)
            self.fade_job = None
        if not self.reduced_motion.get():
            # Fade the window, never change or scale the source image pixels.
            self.root.attributes('-alpha', .94)
            self.fade_job = self.root.after(80, self._end_fade)
        else:
            self.root.attributes('-alpha', 1)
        if self.terminal:
            self.terminal.status.set(state + (' · tarefa em andamento' if self.busy else ' · pronto'))

    def set_busy(self, value):
        self.busy = value
        if self.terminal:
            self.terminal.busy(value or self.failed or self.closing)
            self.terminal.status.set(self.state + (' · tarefa em andamento' if value else ' · resposta disponível'))
        if self.preferences and self.preferences.window.winfo_exists():
            self.preferences.busy(value)

    def submit(self, command=None):
        if self.busy or self.failed or self.closing:
            return
        terminal = self.get_terminal()
        text = command if command is not None else terminal.entry.get().strip()
        if not text:
            return
        if len(text) > 2000:
            terminal.status.set('Limite: 2.000 caracteres.')
            return
        terminal.entry.delete(0, 'end')
        if re.search(r'\btvly-[A-Za-z0-9_-]+', text):
            self.notify('Informe a chave somente em Conexões.')
            return
        if text.lower() in ('sair', '/exit', '/quit', '/sair'):
            self.close()
            return
        terminal.append('> ' + text, 'user')
        self.notice, self.operation_failed = None, False
        if self.idle_job:
            self.root.after_cancel(self.idle_job)
            self.idle_job = None
        self.dismiss_bubble()
        self.set_busy(True)
        self.set_state('ANALYZING')
        self.worker.commands.put(text)

    def queue_request(self, request):
        if self.busy or self.failed or self.closing:
            return
        if self.idle_job:
            self.root.after_cancel(self.idle_job)
            self.idle_job = None
        self.set_busy(True)
        self.set_state('WORKING')
        self.worker.commands.put(request)

    def notify(self, text):
        self.dismiss_bubble()
        if self.closing:
            return
        window = self.bubble = tk.Toplevel(self.root)
        window.withdraw()
        window.overrideredirect(True)
        window.configure(bg='#254331')
        label = tk.Label(window, text=text[:180], bg=BG, fg=FG, font=('Consolas', 9),
                         wraplength=240, padx=12, pady=9, justify='left')
        label.pack(padx=1, pady=1)
        label.bind('<Button-1>', lambda e: self.dismiss_bubble())
        window.update_idletasks()
        w, h = window.winfo_reqwidth(), window.winfo_reqheight()
        x, y = native.place_near(self.x, self.y, self.atlas.width, self.atlas.height, w, h, native.work_area(self.root))
        window.geometry(f'{w}x{h}{x:+d}{y:+d}')
        window.update_idletasks()
        native.no_activate(window)
        window.deiconify()
        native.show_passive(window, x, y, w, h, self.always_on_top.get())
        self.bubble_job = self.root.after(5500, self.dismiss_bubble)

    def dismiss_bubble(self):
        if self.bubble_job:
            self.root.after_cancel(self.bubble_job)
            self.bubble_job = None
        if self.bubble and self.bubble.winfo_exists():
            self.bubble.destroy()
        self.bubble = None

    def activity(self, data):
        kind = data['kind']
        if kind == 'SEARCH_RESULT_FOUND':
            self.found_until = time.monotonic() + .45
        if kind in STATE_EVENTS:
            self.set_state(STATE_EVENTS[kind])
        message = data.get('message')
        if message:
            self.get_terminal().append('· ' + message, 'error' if kind == 'TASK_ERROR' else 'event')
        if kind in ('SEARCH_COMPLETED', 'TASK_ERROR'):
            self.notice = message
        if kind == 'TASK_ERROR':
            self.operation_failed = True

    def poll(self):
        self.poll_job = None
        try:
            while True:
                kind, value = self.worker.events.get_nowait()
                if kind == 'ready':
                    self.ready = True
                    self.set_busy(False)
                    # No console, dashboard or persistent bubble is opened at startup.
                elif kind == 'activity':
                    self.activity(value)
                elif kind == 'reply':
                    self.get_terminal().append(value + '\n')
                    self.set_busy(False)
                    self.notify(self.notice or 'Resposta disponível. Clique para consultar.')
                    self.idle_job = self.root.after(1200, self.to_idle)
                elif kind in ('connected', 'connection_error', 'ollama_models', 'ollama_ready', 'ollama_error'):
                    self.set_busy(False)
                    if self.preferences and self.preferences.window.winfo_exists():
                        self.preferences.event(kind, value)
                    self.set_state('IDLE')
                    if kind.endswith('error'):
                        self.notify(value)
                elif kind == 'error':
                    self.failed = True
                    self.set_busy(False)
                    self.get_terminal().append(value, 'error')
                    self.notify(value)
                elif kind == 'closed':
                    if self.closing:
                        self.root.destroy()
                        return
                    self.failed = True
                    self.set_busy(False)
        except Empty:
            pass
        if self.closing and not self.worker.thread.is_alive():
            self.root.destroy()
            return
        self.poll_job = self.root.after(75, self.poll)

    def to_idle(self):
        self.idle_job = None
        if not self.busy:
            self.set_state('IDLE')

    def _respond(self):
        self.response_job = None
        self.set_state('RESPONDING')

    def _end_fade(self):
        self.fade_job = None
        self.root.attributes('-alpha', 1)

    def close(self):
        if self.closing:
            return
        self._save()
        self.closing = True
        self.dismiss_bubble()
        self.set_busy(True)
        if self.terminal:
            self.terminal.status.set('Encerrando após a tarefa em andamento…')
        self.worker.close()

    def _destroyed(self, event):
        if event.widget is self.root:
            for job in (self.poll_job, self.idle_job, self.bubble_job, self.response_job, self.fade_job):
                if job:
                    self.root.after_cancel(job)
            self.worker.close()
