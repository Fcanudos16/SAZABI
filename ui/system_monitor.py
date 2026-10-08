"""Native, on-demand presentation of the integrated System monitor."""
import time
import tkinter as tk
from tkinter import ttk
from system_monitor.service import MonitorSampler
from system_monitor.formatter import format_bytes, format_uptime
from ui import native
from ui.terminal import BG, FG, MUTED, BORDER, FONT, button


class SystemMonitorWindow:
    def __init__(self, app):
        self.app = app
        self.window = tk.Toplevel(app.root)
        self.window.withdraw()
        self.window.title('SAZABI · Monitor do sistema')
        self.window.configure(bg=BG)
        self.window.resizable(False, False)
        self.visible, self.running, self.job = False, False, None
        self.last_snapshot, self.sample_count = None, 0
        self.sampler = MonitorSampler()
        body = tk.Frame(self.window, bg=BG)
        body.pack(fill='both', expand=True, padx=18, pady=14)
        tk.Label(body, text='MONITOR DO SISTEMA', bg=BG, fg=FG, font=('Consolas', 13, 'bold')).pack(anchor='w')
        self.system = tk.StringVar(value='Lendo informações locais…')
        tk.Label(body, textvariable=self.system, bg=BG, fg=MUTED, font=('Consolas', 9),
                 wraplength=560, height=4, justify='left', anchor='w').pack(fill='x', pady=(8, 10))
        style = ttk.Style(self.window)
        style.theme_use('clam')
        style.configure('Sazabi.Horizontal.TProgressbar', background=FG, troughcolor=BG,
                        bordercolor=BORDER, lightcolor=FG, darkcolor=FG)
        self.labels, self.bars = {}, {}
        for key, title in [('cpu', 'CPU'), ('memory', 'RAM'), ('disk', 'DISCO')]:
            self.labels[key] = tk.StringVar(value=title + ' · aguardando leitura')
            tk.Label(body, textvariable=self.labels[key], bg=BG, fg=FG, font=FONT,
                     justify='left', anchor='w', wraplength=560, height=2).pack(fill='x', pady=(8, 4))
            bar = self.bars[key] = ttk.Progressbar(body, maximum=100, style='Sazabi.Horizontal.TProgressbar')
            bar.pack(fill='x')
        self.uptime = tk.StringVar(value='Tempo ligado: aguardando leitura')
        tk.Label(body, textvariable=self.uptime, bg=BG, fg=FG, font=FONT).pack(anchor='w', pady=(14, 5))
        self.status = tk.StringVar(value='Primeira amostra em aproximadamente 1 segundo.')
        tk.Label(body, textvariable=self.status, bg=BG, fg=MUTED, font=('Consolas', 9),
                 wraplength=560, height=2, justify='left').pack(anchor='w', pady=5)
        self.close_button = button(body, 'Fechar monitor', self.hide)
        self.close_button.pack(anchor='e', pady=(5, 0))
        self.window.protocol('WM_DELETE_WINDOW', self.hide)
        self.window.bind('<Escape>', lambda event: self.hide())
        self.window.bind('<Unmap>', self.unmapped)
        self.window.bind('<Map>', self.mapped)

    def show(self):
        self.visible = True
        self.window.update_idletasks()
        width, height = 600, self.window.winfo_reqheight()
        x, y = native.place_near(self.app.x, self.app.y, self.app.atlas.width, self.app.atlas.height,
                                 width, height, native.work_area(self.app.root))
        self.window.geometry(f'{width}x{height}{x:+d}{y:+d}')
        self.window.attributes('-topmost', self.app.always_on_top.get())
        self.window.deiconify()
        self.window.update_idletasks()
        native.position(self.window, x, y)
        self.window.lift()
        self.window.focus_force()
        self.resume()

    def mapped(self, event):
        if event.widget is self.window and self.visible:
            self.resume()

    def unmapped(self, event):
        if event.widget is self.window:
            self.pause()

    def resume(self):
        if self.running:
            return
        self.running = True
        self.clear_values()
        self.status.set('Coletando nova amostra…')
        self.sampler.set_active(True)
        self.poll()

    def pause(self):
        self.running = False
        self.sampler.set_active(False)
        if self.job:
            self.window.after_cancel(self.job)
            self.job = None

    def hide(self):
        self.visible = False
        self.pause()
        self.window.withdraw()

    def clear_values(self):
        for key, label in self.labels.items():
            label.set(key.upper() + ' · sem leitura atual')
            self.bars[key]['value'] = 0
        self.system.set('Informações do computador: aguardando leitura')
        self.uptime.set('Tempo ligado: aguardando leitura')
        self.last_snapshot = None

    def poll(self):
        self.job = None
        if not self.running:
            return
        value = self.sampler.latest()
        if value is not None:
            self.render(value)
        self.job = self.window.after(200, self.poll)

    def render(self, value):
        self.clear_values()
        if 'error' in value:
            self.status.set(value['error'])
            return
        self.last_snapshot = value
        self.sample_count += 1
        info = value.get('system')
        if info:
            self.system.set(f"{info['os']} · {info['hostname']} · {info['architecture']}\n{info['processor']}\n"
                            f"Núcleos físicos: {info['physical'] if info['physical'] is not None else 'indisponível'} · Lógicos: {info['logical']}")
        for key in self.labels:
            data = value.get(key)
            if data is None:
                self.labels[key].set(key.upper() + ' · leitura indisponível')
                continue
            percent = data['percent']
            self.bars[key]['value'] = max(0, min(100, percent))
            if key == 'cpu':
                frequency = data.get('frequency')
                detail = f" · {frequency/1000:.2f} GHz" if frequency else ' · frequência indisponível'
                self.labels[key].set(f'CPU · {percent:.1f}%{detail}')
            else:
                free = data['available'] if key == 'memory' else data['free']
                title = 'RAM' if key == 'memory' else f"DISCO ({data['path']})"
                self.labels[key].set(f"{title} · {percent:.1f}%\n{format_bytes(data['used'])} usados · "
                                     f"{format_bytes(free)} disponíveis · {format_bytes(data['total'])} total")
        if value.get('uptime') is not None:
            self.uptime.set('Tempo ligado: ' + format_uptime(value['uptime']))
        errors = value.get('errors', {})
        message = 'Leitura indisponível: ' + ', '.join(errors) if errors else 'Somente leitura local · atualização a cada 1 segundo'
        self.status.set(time.strftime('%H:%M:%S', time.localtime(value['timestamp'])) + ' · ' + message)

    def close(self):
        self.pause()
        self.sampler.close()
