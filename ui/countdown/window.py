"""Tk adaptation of SAZABI_COUNTDOWN's seven-segment HUD and command terminal."""
import time
import tkinter as tk
from tkinter import font

from ui import native
from . import theme as t
from .commands import CommandProcessor
from .renderer import HudRenderer
from .timer_engine import State, TimerEngine, split_cs


class CountdownWindow(HudRenderer):
    def __init__(self, root):
        self.root, self.research = root, False
        self.engine = TimerEngine()
        self.width = t.DEFAULT_WIDTH
        self.top = True
        self.visible = False
        self.terminal_open = False
        self.closed = False
        self.job = None
        self.drag = None
        self.window = tk.Toplevel(root)
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.title('SAZABI COUNTDOWN')
        self.window.configure(bg=t.BG)
        self.window.attributes('-topmost', True)
        self.canvas = tk.Canvas(self.window, bg=t.BG, highlightthickness=0)
        self.canvas.pack()
        self.terminal = tk.Frame(self.window, bg=t.BG)
        self.output = tk.Text(self.terminal, height=4, bg=t.BG, fg=t.GREEN_LUM,
                              font=('Consolas', 10), relief='flat', state='disabled', wrap='word')
        self.output.pack(fill='both', expand=True, padx=10)
        self.entry = tk.Entry(self.terminal, bg=t.BG, fg=t.GREEN, insertbackground=t.GREEN,
                              font=('Consolas', 10), relief='flat')
        self.entry.pack(fill='x', padx=10, pady=5)
        self.entry.bind('<Return>', self.enter)
        self.window.bind('<Return>', self.open_terminal_key)
        self.window.bind('<slash>', self.open_terminal_key)
        self.window.bind('<space>', self.space)
        self.window.bind('<Escape>', self.escape)
        self.canvas.bind('<ButtonPress-1>', self.press)
        self.canvas.bind('<B1-Motion>', self.move)
        self.canvas.bind('<ButtonRelease-1>', lambda e: setattr(self, 'drag', None))
        self.window.protocol('WM_DELETE_WINDOW', self.hide)
        self.processor = CommandProcessor(self.engine, self.set_top, self.hide)
        families = set(font.families(root))
        self.jp = next((f for f in t.JP_FAMILIES if f in families), None)
        self.log('SAZABI COUNTDOWN ONLINE\ncinco minutos | 5:00:00 | iniciar | help')
        self.apply_size()
        self.draw()
        left, top, right, bottom = native.work_area(root)
        self.x = right - self.width - 24
        self.y = top + 24

    def apply_size(self):
        left, top, right, bottom = native.work_area(self.root)
        max_width = min(t.MAX_WIDTH, right-left-24, int((bottom-top-24-(120 if self.terminal_open else 0))*700/340))
        self.width = min(max(t.MIN_WIDTH, self.width), max_width)
        self.height = round(self.width * 340 / 700)
        self.canvas.configure(width=self.width, height=self.height)
        self.window.geometry(f'{self.width}x{self.height+(120 if self.terminal_open else 0)}')

    def show(self, focus=True):
        if self.closed:
            return
        self.visible = True
        self.apply_size()
        self.window.deiconify()
        self.window.update_idletasks()
        self.clamp()
        if focus:
            self.window.lift()
            self.canvas.focus_set()
        self.refresh()

    def clamp(self):
        left, top, right, bottom = native.work_area(self.root)
        self.x = max(left, min(self.x, right-self.width))
        self.y = max(top, min(self.y, bottom-self.height-(120 if self.terminal_open else 0)))
        native.position(self.window, self.x, self.y)

    def hide(self):
        self.visible = False
        self.window.withdraw()
        self.refresh()

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.job:
            self.root.after_cancel(self.job)
            self.job = None
        if self.window.winfo_exists():
            self.window.destroy()

    def set_top(self, value=None):
        self.top = not self.top if value is None else value
        self.window.attributes('-topmost', self.top)
        self.draw()
        return self.top

    def log(self, text):
        self.output.configure(state='normal')
        self.output.insert('end', text+'\n')
        if int(self.output.index('end-1c').split('.')[0]) > 200:
            self.output.delete('1.0', '50.0')
        self.output.see('end')
        self.output.configure(state='disabled')

    def run_command(self, text):
        result = self.processor.execute(text)
        if result.clear:
            self.output.configure(state='normal')
            self.output.delete('1.0', 'end')
            self.output.configure(state='disabled')
        for line in result.lines:
            self.log(line)
        self.refresh()
        return result

    def enter(self, event=None):
        text = self.entry.get()
        self.entry.delete(0, 'end')
        self.run_command(text)
        return 'break'

    def toggle_terminal(self):
        self.terminal_open = not self.terminal_open
        if self.terminal_open:
            self.terminal.pack(fill='both', expand=True)
            self.entry.focus_set()
        else:
            self.terminal.pack_forget()
            self.canvas.focus_set()
        self.apply_size()
        self.clamp()
        self.draw()

    def open_terminal_key(self, event):
        if event.widget is not self.entry:
            self.toggle_terminal()
            return 'break'

    def space(self, event):
        if event.widget is self.entry:
            return
        command = 'pause' if self.engine.state is State.RUNNING else 'resume' if self.engine.state is State.PAUSED else 'start'
        self.run_command(command)
        return 'break'

    def escape(self, event=None):
        if self.terminal_open:
            self.toggle_terminal()
        else:
            self.engine.dismiss()
            self.refresh()
        return 'break'

    def press(self, event):
        x, y = event.x*700/self.width, event.y*340/self.height
        if 20 <= y <= 44:
            if 654 <= x <= 684:
                self.hide(); return
            if 588 <= x <= 646:
                self.toggle_terminal(); return
            if 520 <= x <= 580:
                self.set_top(); return
        if self.engine.state is State.COMPLETE and 153 <= x <= 690 and 98 <= y <= 267:
            self.engine.dismiss(); self.refresh(); return
        self.drag = ('resize' if x >= 655 and y >= 312 else 'move', event.x_root, event.y_root,
                     self.width, self.window.winfo_x(), self.window.winfo_y())

    def move(self, event):
        if self.drag:
            mode, x, y, width, ox, oy = self.drag
            if mode == 'resize':
                self.width = width+event.x_root-x
                self.apply_size()
                self.draw()
            else:
                self.x, self.y = ox+event.x_root-x, oy+event.y_root-y
            self.clamp()

    def refresh(self):
        if self.closed:
            return
        if self.job:
            self.root.after_cancel(self.job)
            self.job = None
        if self.engine.tick():
            self.log('COUNTDOWN COMPLETE')
        if self.visible:
            self.draw()
        active = self.engine.state in (State.RUNNING, State.COMPLETE)
        if active:
            self.job = self.root.after(20 if self.visible else 250, self.refresh)

