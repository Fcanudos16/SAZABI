"""Mascot-first desktop shell. All research runs on the existing worker thread."""
import json
import re
import time
import tkinter as tk
from pathlib import Path
from queue import Empty

from core.bootstrap import build_agent
from core.worker import AgentWorker
from ui.sprites import SpriteAtlas, ASSETS
from ui.terminal import ResultTerminal, BG, FG, FONT
from ui import native
from ui.motion import offset
from ui.behavior import SazabiAnimationController, SazabiDragController, validate_settings
from ui.interaction import SazabiInteractionController
from ui.presentation import SazabiPresentationController
from ui.renderer import SazabiRenderer, SazabiTransitionController
from ui.effects import SleepBubbles, SazabiNotificationController


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
        self.system_monitor = None
        self.menu, self.menu_action_job = None, None
        self.poll_job, self.idle_job = None, None
        self.response_job, self.found_until = None, 0
        self.motion_job, self.motion_offset = None, (0, 0)
        self.motion_started, self.hovered = time.monotonic(), False
        self.state, self.notice, self.operation_failed = 'IDLE', None, False
        self.state_history = ['IDLE']
        self.always_on_top = tk.BooleanVar(root, True)
        self.atlas = SpriteAtlas(root)
        self.animation_settings = validate_settings(json.loads((ASSETS / 'animation.json').read_text(encoding='utf-8')))
        self.animation = SazabiAnimationController(time.monotonic(), self.animation_settings)
        self.drag_controller = SazabiDragController(self.animation_settings)
        self.presentation = SazabiPresentationController()
        self.visual_started = time.monotonic()
        self.wake_job, self.visual_state = None, 'IDLE'
        self.visual_history = ['IDLE']
        self.sleep_after = tk.IntVar(root, self.animation_settings['sleep_after_seconds'])
        self.life_job = None
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
        self.area = area
        root.geometry(f'{self.atlas.width}x{self.atlas.height}{self.x:+d}{self.y:+d}')
        root.update_idletasks()
        native.no_activate(root)
        native.shape(root, self.atlas.regions['IDLE'])
        root.attributes('-topmost', self.always_on_top.get())
        root.deiconify()
        native.show_passive(root, self.x, self.y, self.atlas.width, self.atlas.height, self.always_on_top.get())
        self._drag = None
        self.renderer = SazabiRenderer(self)
        self.transitions = SazabiTransitionController(self, self.renderer)
        self.interaction = SazabiInteractionController(self)
        self.sleep_bubbles = SleepBubbles(self, self.animation.rng)
        self.notifications = SazabiNotificationController(self)
        self.canvas.bind('<ButtonPress-1>', self.press)
        self.canvas.bind('<B1-Motion>', self.drag)
        self.canvas.bind('<ButtonRelease-1>', self.release)
        self.canvas.bind('<Button-3>', self.context_menu)
        self.canvas.bind('<Enter>', lambda event: self.hover(True))
        self.canvas.bind('<Leave>', lambda event: self.hover(False))
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.bind('<Destroy>', self._destroyed, add='+')
        self.worker = AgentWorker(config, factory=factory, progress=True)
        self.poll_job = root.after(75, self.poll)
        self.motion_tick()
        self.life_tick()

    def hover(self, value):
        self.hovered = value  # Hold still while the user aims at or drags the mascot.
        if value and self.animation_settings['hover_wakes']:
            self.touch()

    def touch(self):
        self.animation.touch(time.monotonic())
        self.sleep_bubbles.clear()
        self.refresh_visual()

    def wake_gate(self, action=None):
        if self.animation.sleep.phase not in ('SLEEPING', 'FALLING_ASLEEP', 'WAKE_UP'):
            return False
        self.touch()
        if action is not None:
            if self.wake_job:
                self.root.after_cancel(self.wake_job)
            remaining = max(0, self.animation.sleep.wake-(time.monotonic()-self.animation.sleep.started))
            def run():
                self.wake_job = None
                self.animation.sleep.update(time.monotonic())
                if not self.closing:
                    action()
            self.wake_job = self.root.after(max(1, int(remaining*1000)+10), run)
        return True

    def temporary_state(self):
        phase = self.drag_controller.sample(time.monotonic())[0]
        if phase:
            return phase
        if self.interaction.menu_open:
            return 'EXIT_HOVER' if self.interaction.exit_hover else 'CONFIGURATION'
        return None

    def refresh_visual(self):
        state = self.animation.states.resolve(self.state, self.busy, self.failed,
                                               self.animation.sleep.phase, self.temporary_state())
        self.animation.visual_state = state
        if state != self.visual_state:
            self.visual_state = state
            self.visual_started = time.monotonic()
            self.visual_history = (self.visual_history+[state])[-100:]
            key = {'JUMPING': 'jump_transition_ms', 'LANDING': 'landing_transition_ms',
                   'WAKE_UP': 'wake_transition_ms', 'FALLING_ASLEEP': 'sleep_transition_ms'}.get(state, 'transition_ms')
            self.transitions.start(self.atlas.state_models[state], self.animation_settings[key]/1000)

    def sleep_timeout_changed(self):
        self.animation.sleep.timeout = self.sleep_after.get()
        self.touch()
        self._save()

    def life_tick(self):
        self.life_job = None
        if self.closing:
            return
        self.animation.sleep.update(time.monotonic(), self.busy or self.failed or self.state != 'IDLE'
                                    or bool(self._drag) or self.interaction.menu_open or bool(self.terminal and self.terminal.visible))
        self.refresh_visual()
        self.life_job = self.root.after(250, self.life_tick)

    def motion_tick(self):
        self.motion_job = None
        if self.closing:
            return
        if not self.root.winfo_viewable():
            self.sleep_bubbles.clear()
            self.motion_job = self.root.after(500, self.motion_tick)
            return
        now = time.monotonic()
        mx, my, blink, phase = self.animation.sample(now, self.state, self.busy, self.failed,
                                                    bool(self._drag) or self.interaction.menu_open or bool(self.terminal and self.terminal.visible), self.temporary_state())
        self.refresh_visual()
        self.renderer.blink(blink if self.animation_settings['blink_enabled'] else 0)
        self.sleep_bubbles.update(now, phase == 'SLEEPING')
        drag_state, drag_y, scale = self.drag_controller.sample(now)
        angle, body_scale = self.presentation.sample(now, self.visual_state, self.animation.sleep.depth(now),
                                                     mx, scale, now-self.visual_started)
        self.renderer.transform(angle, body_scale)
        if drag_state or not self.hovered:
            dx, dy = mx, my
            if drag_state:
                dx, dy = 0, drag_y
            elif self.state in ('FOUND', 'RESPONDING'):
                rx, ry = offset(self.state, now-self.motion_started)
                dx, dy = dx+round(rx*.35), dy+round(ry*.35)
            left, top, right, bottom = self.area
            if not self._drag:
                dx = max(left, min(self.x+dx, right-self.atlas.width))-self.x
                dy = max(top, min(self.y+dy, bottom-self.atlas.height))-self.y
            if (dx, dy) != self.motion_offset:
                native.position(self.root, self.x+dx, self.y+dy)
                self.motion_offset = (dx, dy)
        self.motion_job = self.root.after(160 if phase == 'SLEEPING' else 50, self.motion_tick)

    def _restore(self):
        if self.position_file:
            try:
                data = json.loads(self.position_file.read_text(encoding='utf-8'))
                self.x, self.y = int(data['x']), int(data['y'])
                if not (-100000 < self.x < 100000 and -100000 < self.y < 100000):
                    self.x = self.y = 0
                self.always_on_top.set(bool(data.get('topmost', True)))
                timeout = data.get('sleep_after_seconds', self.animation.sleep.timeout)
                if isinstance(timeout, int) and 0 <= timeout <= 86400:
                    self.sleep_after.set(timeout)
                    self.animation.sleep.timeout = timeout
            except (OSError, ValueError, TypeError, KeyError):
                pass

    def _save(self):
        if self.position_file:
            try:
                self.position_file.parent.mkdir(parents=True, exist_ok=True)
                temporary = self.position_file.with_suffix('.tmp')
                temporary.write_text(json.dumps({'x': self.x, 'y': self.y, 'topmost': self.always_on_top.get(),
                                                'sleep_after_seconds': self.sleep_after.get()}), encoding='utf-8')
                temporary.replace(self.position_file)
            except OSError:
                self.notify('Não foi possível salvar a posição do mascote.')

    def _clamp(self, area):
        left, top, right, bottom = area
        self.x = max(left, min(self.x, right-self.atlas.width))
        self.y = max(top, min(self.y, bottom-self.atlas.height))

    def press(self, event):
        self.interaction.close()
        if self.wake_gate():
            self._drag = None
            return
        self.touch()
        self.dismiss_bubble()
        self.motion_offset = (0, 0)
        native.position(self.root, self.x, self.y)
        self._drag = (event.x_root, event.y_root, self.x, self.y, False)

    def drag(self, event):
        if self._drag:
            mx, my, x, y, moved = self._drag
            dx, dy = event.x_root-mx, event.y_root-my
            if moved or abs(dx)+abs(dy) > 6:
                if not moved:
                    self.drag_controller.start(time.monotonic())
                    self.refresh_visual()
                self._drag = (mx, my, x, y, True)
                self.presentation.drag(x+dx-self.x)
                self.x, self.y = x+dx, y+dy
                jump_y = self.drag_controller.sample(time.monotonic())[1]
                self.motion_offset = (0, jump_y)
                native.show_passive(self.root, self.x, self.y+jump_y, self.atlas.width, self.atlas.height, self.always_on_top.get())

    def release(self, event):
        if not self._drag:
            return
        moved = self._drag[4]
        self._drag = None
        if moved:
            self.drag_controller.release(time.monotonic())
            self.refresh_visual()
            self.area = native.work_area(self.root)
            self._clamp(self.area)
            dy = self.drag_controller.sample(time.monotonic())[1]
            self.motion_offset = (0, dy)
            native.show_passive(self.root, self.x, self.y+dy, self.atlas.width, self.atlas.height, self.always_on_top.get())
            self._save()
        else:
            self.toggle_terminal()

    def get_terminal(self):
        if self.terminal is None:
            self.terminal = ResultTerminal(self)
        return self.terminal

    def toggle_terminal(self):
        if self.wake_gate(lambda: self.toggle_terminal()):
            return
        self.touch()
        terminal = self.get_terminal()
        self.dismiss_bubble()
        if terminal.visible:
            terminal.hide()
        else:
            terminal.show()
            terminal.busy(self.busy or self.failed or self.closing)

    def open_search(self):
        if self.wake_gate(self.open_search):
            return
        self.touch()
        terminal = self.get_terminal()
        terminal.busy(self.busy or self.failed or self.closing)
        terminal.show()
        if not (self.busy or self.failed or self.closing):
            terminal.entry.delete(0, 'end')
            terminal.entry.insert(0, 'procure empresas em ')
            terminal.entry.icursor('end')

    def open_settings(self):
        if self.wake_gate(self.open_settings):
            return
        self.touch()
        if self.preferences and self.preferences.window.winfo_exists():
            self.preferences.show()
            return
        from ui.preferences import Preferences
        self.preferences = Preferences(self)
        self.preferences.show()

    def menu_action(self, command):
        # Let Tk release the popup's native focus before opening another window.
        if self.menu:
            self.menu.unpost()
            self.menu.grab_release()
        self.interaction.close()
        if self.menu_action_job:
            self.root.after_cancel(self.menu_action_job)
        def run():
            self.menu_action_job = None
            if not self.closing:
                command()
        self.menu_action_job = self.root.after_idle(run)

    def open_system_monitor(self):
        self.touch()
        if self.system_monitor is None:
            from ui.system_monitor import SystemMonitorWindow
            self.system_monitor = SystemMonitorWindow(self)
        self.system_monitor.show()

    def context_menu(self, event):
        if self.wake_gate(lambda: self.context_menu(event)):
            return
        self.touch()
        self.menu_terminal_visible = bool(self.terminal and self.terminal.visible)
        if self.menu is not None:
            self.interaction.open(self.menu, event.x_root, event.y_root)
            return
        menu = tk.Menu(self.root, tearoff=False, bg=BG, fg=FG, font=FONT)
        self.menu = menu
        menu.add_command(label='Abrir / fechar terminal', command=lambda: self.menu_action(self.menu_toggle_terminal))
        menu.add_command(label='Nova pesquisa', command=lambda: self.menu_action(self.open_search))
        menu.add_command(label='Configuração · Tavily / Ollama', command=lambda: self.menu_action(self.open_settings))
        menu.add_command(label='Monitor do sistema', command=lambda: self.menu_action(self.open_system_monitor))
        menu.add_separator()
        menu.add_checkbutton(label='Sempre no topo', variable=self.always_on_top, command=self.topmost_changed)
        sleep_menu = tk.Menu(menu, tearoff=False, bg=BG, fg=FG, font=FONT)
        for label, seconds in [('Nunca', 0), ('1 minuto', 60), ('2 minutos', 120), ('5 minutos', 300)]:
            sleep_menu.add_radiobutton(label=label, value=seconds, variable=self.sleep_after,
                                       command=self.sleep_timeout_changed)
        menu.add_cascade(label='Dormir após', menu=sleep_menu)
        menu.add_separator()
        menu.add_command(label='Encerrar SAZABI', command=lambda: self.menu_action(self.close))
        self.interaction.open(menu, event.x_root, event.y_root)

    def menu_toggle_terminal(self):
        if self.menu_terminal_visible:
            self.get_terminal().hide()
        else:
            self.get_terminal().show()
            self.get_terminal().busy(self.busy or self.failed or self.closing)

    def topmost_changed(self):
        self.root.attributes('-topmost', self.always_on_top.get())
        for window in (self.terminal.window if self.terminal else None,
                       self.preferences.window if self.preferences else None, self.bubble,
                       self.system_monitor.window if self.system_monitor else None):
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
        self.motion_started = time.monotonic()
        self.state_history.append(state)
        self.state_history = self.state_history[-100:]
        self.refresh_visual()
        if self.terminal:
            self.terminal.status.set(state + (' · tarefa em andamento' if self.busy else ' · pronto'))

    def set_busy(self, value):
        self.busy = value
        self.touch()
        if self.terminal:
            self.terminal.busy(value or self.failed or self.closing)
            self.terminal.status.set(self.state + (' · tarefa em andamento' if value else ' · resposta disponível'))
        if self.preferences and self.preferences.window.winfo_exists():
            self.preferences.busy(value)

    def submit(self, command=None):
        if self.wake_gate(lambda: self.submit(command)):
            return
        self.touch()
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
        if self.wake_gate(lambda: self.queue_request(request)):
            return
        self.touch()
        if self.busy or self.failed or self.closing:
            return
        if self.idle_job:
            self.root.after_cancel(self.idle_job)
            self.idle_job = None
        self.set_busy(True)
        self.set_state('WORKING')
        self.worker.commands.put(request)

    def notify(self, text):
        self.notifications.show(text)

    def dismiss_bubble(self):
        self.notifications.dismiss()

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

    def close(self):
        if self.closing:
            return
        self._save()
        self.closing = True
        self.interaction.close()
        if self.system_monitor:
            self.system_monitor.close()
        self.transitions.finish()
        self.sleep_bubbles.clear()
        self.notifications.clear()
        if self.life_job:
            self.root.after_cancel(self.life_job)
            self.life_job = None
        if self.motion_job:
            self.root.after_cancel(self.motion_job)
            self.motion_job = None
        self.dismiss_bubble()
        self.set_busy(True)
        if self.terminal:
            self.terminal.status.set('Encerrando após a tarefa em andamento…')
        self.worker.close()

    def _destroyed(self, event):
        if event.widget is self.root:
            if self.system_monitor:
                self.system_monitor.sampler.close()
            for job in (self.poll_job, self.idle_job, self.response_job, self.motion_job, self.life_job, self.menu_action_job, self.wake_job, self.interaction.focus_job,
                        self.transitions.job, self.notifications.job):
                if job:
                    self.root.after_cancel(job)
            self.worker.close()
