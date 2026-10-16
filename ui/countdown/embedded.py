"""Read-only elapsed-time HUD owned exclusively by the search terminal."""
import tkinter as tk

from .renderer import HudRenderer
from .stopwatch import Stopwatch
from . import theme as t


class ResearchTimer(HudRenderer):
    def __init__(self, terminal):
        self.terminal = terminal
        self.root = terminal.app.root
        self.research = True
        self.stopwatch = Stopwatch()
        self.width = 300
        self.jp = None
        self.visible = False
        self.closed = False
        self.job = None
        self.frame = tk.Frame(terminal.body, bg=t.BG)
        self.canvas = tk.Canvas(self.frame, width=self.width, height=round(self.width*340/700),
                                bg=t.BG, highlightthickness=0, takefocus=False)
        self.canvas.pack(anchor='center')

    def start_research(self):
        if self.closed or self.stopwatch.running:
            return
        self.stopwatch.start()
        self.visible = True
        self.frame.pack(fill='x', before=self.terminal.content)
        self.refresh()

    def refresh(self):
        self.job = None
        if self.closed or not self.stopwatch.running:
            return
        if self.terminal.visible:
            self.draw()
        self.job = self.root.after(40, self.refresh)

    def finish_research(self, status):
        self.stopwatch.finish(status)
        if self.job:
            self.root.after_cancel(self.job)
            self.job = None
        self.visible = False
        if not self.closed and self.frame.winfo_exists():
            self.frame.pack_forget()

    def close(self):
        self.finish_research('closed')
        self.closed = True
