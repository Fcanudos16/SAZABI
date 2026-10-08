"""Bounded native effects. Sleep bubbles never receive focus or mouse clicks."""
import math
import time
import tkinter as tk
from ui import native
from ui.behavior import ease
from ui.terminal import BG, FG


class SleepBubbles:
    def __init__(self, app, rng):
        self.app, self.rng, self.items, self.next_at = app, rng, [], 0

    def clear(self):
        for item in self.items:
            item['window'].destroy()
        self.items.clear()
        self.next_at = 0

    def update(self, now, sleeping):
        if not sleeping:
            if self.items:
                self.clear()
            return
        if not self.next_at:
            self.next_at = now + self.rng.uniform(.3, 1.2)
        if now >= self.next_at and len(self.items) < 2:
            window = tk.Toplevel(self.app.root)
            window.withdraw()
            window.overrideredirect(True)
            window.attributes('-transparentcolor', '#ff00ff')
            window.attributes('-alpha', 0)
            canvas = tk.Canvas(window, width=32, height=32, bg='#ff00ff', bd=0, highlightthickness=0)
            canvas.pack()
            oval = canvas.create_oval(12, 12, 20, 20, outline='#73a4a8', width=2)
            window.update_idletasks()
            native.no_activate(window)
            native.click_through(window)
            window.deiconify()
            self.items.append(dict(window=window, canvas=canvas, oval=oval, born=now,
                                   duration=self.rng.uniform(2.8, 4.2), side=self.rng.uniform(-8, 8),
                                   size=self.rng.uniform(7, 11), drift=self.rng.uniform(-9, 9)))
            self.next_at = now+self.rng.uniform(1.8, 3.8)
        for item in self.items[:]:
            p = (now-item['born'])/item['duration']
            if p >= 1:
                item['window'].destroy()
                self.items.remove(item)
                continue
            radius = item['size']*(.45+.55*ease(p))
            item['canvas'].coords(item['oval'], 16-radius, 16-radius, 16+radius, 16+radius)
            item['window'].attributes('-alpha', .8*ease(p*5)*(1-ease(max(0, (p-.5)*2))))
            left, top, right, bottom = self.app.area
            x = self.app.x+122+item['side']+math.sin(p*math.pi)*item['drift']
            y = self.app.y+48-48*ease(p)
            native.show_passive(item['window'], round(max(left, min(x, right-32))),
                                round(max(top, min(y, bottom-32))), 32, 32, self.app.always_on_top.get())


class SazabiNotificationController:
    def __init__(self, app):
        self.app, self.job, self.window = app, None, None

    def clear(self):
        if self.job:
            self.app.root.after_cancel(self.job)
            self.job = None
        if self.window:
            self.window.destroy()
            self.window = None
        self.app.bubble = None

    def show(self, text):
        self.clear()
        if self.app.closing:
            return
        window = self.window = self.app.bubble = tk.Toplevel(self.app.root)
        window.withdraw()
        window.overrideredirect(True)
        window.configure(bg='#254331')
        label = tk.Label(window, text=text[:180], bg=BG, fg=FG, font=('Consolas', 9),
                         wraplength=240, padx=12, pady=9, justify='left')
        label.pack(padx=1, pady=1)
        label.bind('<Button-1>', lambda event: self.dismiss())
        window.update_idletasks()
        self.w, self.h = window.winfo_reqwidth(), window.winfo_reqheight()
        self.x, self.y = native.place_near(self.app.x, self.app.y, self.app.atlas.width,
                                         self.app.atlas.height, self.w, self.h, self.app.area)
        window.geometry(f'{self.w}x{self.h}{self.x:+d}{self.y:+d}')
        window.attributes('-alpha', 0)
        window.update_idletasks()
        native.no_activate(window)
        window.deiconify()
        native.show_passive(window, self.x, self.y, self.w, self.h, self.app.always_on_top.get())
        self.started, self.leaving = time.monotonic(), False
        self.tick()

    def dismiss(self):
        if not self.window:
            return
        if self.app.closing:
            self.clear()
            return
        if self.leaving:
            return
        self.initial_alpha = float(self.window.attributes('-alpha'))
        self.leaving, self.started = True, time.monotonic()
        if self.job:
            self.app.root.after_cancel(self.job)
        self.tick()

    def tick(self):
        self.job = None
        if not self.window:
            return
        elapsed = time.monotonic()-self.started
        duration = self.app.animation_settings['notification_transition_ms']/1000
        if self.leaving and elapsed >= duration:
            self.clear()
            return
        if not self.leaving and elapsed >= 5.5:
            self.dismiss()
            return
        progress = ease(elapsed/duration)
        alpha = self.initial_alpha*(1-progress) if self.leaving else progress
        self.window.attributes('-alpha', alpha)
        native.position(self.window, self.x, min(self.app.area[3]-self.h, self.y+round(5*(1-alpha))))
        delay = 33 if elapsed < duration or self.leaving else max(1, round((5.5-elapsed)*1000))
        self.job = self.app.root.after(delay, self.tick)
