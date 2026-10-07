"""Reusable native surfaces, buttons, feedback and scroll containers."""
import tkinter as tk
from tkinter import ttk
import math
from ui.tokens import COLORS as C, SPACE as S, RADIUS, SIZE, MOTION, STATES, mix


def rounded(canvas, x, y, box_width, height, radius, **options):
    width = box_width
    r = min(radius, width/2, height/2)
    return canvas.create_polygon(x+r, y, x+width-r, y, x+width, y,
        x+width, y+r, x+width, y+height-r, x+width, y+height,
        x+width-r, y+height, x+r, y+height, x, y+height,
        x, y+height-r, x, y+r, x, y, smooth=True, splinesteps=24, **options)


def label(parent, text, fonts, kind='body', color='text', **kwargs):
    return tk.Label(parent, text=text, bg=parent.cget('bg'), fg=C[color],
                    font=fonts[kind], anchor='w', **kwargs)


def wrapping_label(parent, text, fonts, kind='body', color='muted'):
    widget = label(parent, text, fonts, kind, color, justify='left')
    widget.bind('<Configure>', lambda e: widget.configure(wraplength=max(100, e.width-4)))
    return widget


class AtmosphereHeader(tk.Canvas):
    """Static low-intensity radial light; no continuous repaint or animation."""
    def __init__(self, parent, fonts):
        super().__init__(parent, bg=C['background'], height=128, highlightthickness=0)
        self.fonts = fonts
        self.bind('<Configure>', self._draw)

    def _draw(self, event):
        self.delete('all')
        width = event.width
        for y in range(0, 128, 8):
            for x in range(0, width, 8):
                distance = ((x-width*.82)/max(1, width*.32))**2 + ((y-30)/90)**2
                color = mix(C['background'], C['wine'], .48*math.exp(-distance*2))
                self.create_rectangle(x, y, x+8, y+8, fill=color, outline='')
        self.create_text(0, 7, anchor='nw', text='VISÃO GERAL', font=self.fonts['label'], fill=C['muted'])
        title_font = self.fonts['title'] if width > 490 else (self.fonts['title'][0], 20, 'bold')
        self.create_text(0, 36, anchor='nw', text='Prospecção com direção.', font=title_font, fill=C['text'], width=width)
        self.create_text(0, 84, anchor='nw', text='Da descoberta à próxima conversa. Tudo parte de uma evidência.',
                         font=self.fonts['body'], fill=C['muted'], width=width)


class Surface(tk.Canvas):
    """Opaque native approximation of restrained glass, with an inner highlight."""
    def __init__(self, parent, padding=S['xl'], **kwargs):
        super().__init__(parent, bg=parent.cget('bg'), highlightthickness=0, bd=0, **kwargs)
        self.padding = padding
        self.content = tk.Frame(self, bg=C['surface'])
        self.window = self.create_window(padding, padding, anchor='nw', window=self.content)
        self.bind('<Configure>', self._layout)
        self.content.bind('<Configure>', self._height)

    def _height(self, event):
        wanted = self.content.winfo_reqheight() + 2*self.padding
        if abs(int(float(self.cget('height'))) - wanted) > 1:
            self.configure(height=wanted)

    def _layout(self, event):
        self.delete('chrome')
        rounded(self, 1, 1, max(1, event.width-2), max(1, event.height-2), RADIUS['surface'],
                fill=C['surface'], outline=C['border'], tags='chrome')
        self.create_line(16, 2, max(16, event.width-16), 2, fill=C['highlight'], tags='chrome')
        self.tag_lower('chrome')
        self.itemconfigure(self.window, width=max(1, event.width-2*self.padding))


class GlassButton(tk.Frame):
    """Native keyboard-focusable button inside a rounded, animated frame."""
    def __init__(self, parent, text, command, fonts, primary=False, motion=lambda: True, width=140):
        super().__init__(parent, bg=parent.cget('bg'), height=SIZE['button'], width=width)
        self.pack_propagate(False)
        self.primary, self.motion, self.selected = primary, motion, False
        self.disabled, self.hovered, self.focused = False, False, False
        self.timer = None
        self.base = C['primary'] if primary else C['surface']
        self.current = self.base
        self.canvas = tk.Canvas(self, bg=self.cget('bg'), highlightthickness=0)
        self.canvas.place(relwidth=1, relheight=1)
        self.button = tk.Button(self, text=text, command=command, font=fonts['body'],
            bg=self.base, fg=C['text'], activebackground=C['deep_red'], activeforeground=C['text'],
            disabledforeground=C['disabled'], relief='flat', bd=0, highlightthickness=0,
            cursor='hand2', takefocus=True, padx=6, pady=0)
        self.button.place(x=9, y=4, relwidth=1, width=-18, relheight=1, height=-8)
        self.button.bind('<Enter>', lambda e: self._hover(True))
        self.button.bind('<Leave>', lambda e: self._hover(False))
        self.button.bind('<FocusIn>', lambda e: self._focus(True))
        self.button.bind('<FocusOut>', lambda e: self._focus(False))
        self.button.bind('<Return>', lambda e: self.invoke())
        self.canvas.bind('<Configure>', lambda e: self._paint())
        self.bind('<Destroy>', self._destroy, add='+')

    def _destroy(self, event):
        if event.widget is self and self.timer:
            self.after_cancel(self.timer)

    def invoke(self):
        if not self.disabled:
            self.button.invoke()
        return 'break'

    def focus_set(self):
        self.button.focus_set()

    def configure(self, cnf=None, **kwargs):
        if 'state' in kwargs:
            self.disabled = kwargs.pop('state') == 'disabled'
            self.button.configure(state='disabled' if self.disabled else 'normal')
        if 'text' in kwargs:
            self.button.configure(text=kwargs.pop('text'))
        if kwargs or cnf:
            super().configure(cnf, **kwargs)
        if hasattr(self, 'canvas'):
            self._paint()

    config = configure

    def select(self, selected):
        self.selected = selected
        self.current = C['hover'] if selected else self.base
        self.button.configure(bg=self.current)
        self._paint()

    def _focus(self, value):
        self.focused = value
        self._paint()

    def _paint(self):
        self.canvas.delete('all')
        border = C['focus'] if self.focused else C['primary_border'] if self.primary or self.hovered or self.selected else C['border']
        rounded(self.canvas, 1, 1, max(1, self.winfo_width()-2), max(1, self.winfo_height()-2),
                RADIUS['button'], fill=self.current, outline=border, width=2 if self.focused else 1)
        if self.selected:
            self.canvas.create_line(3, 12, 3, max(12, self.winfo_height()-12), fill=C['red'], width=2)

    def _hover(self, value):
        self.hovered = value
        if self.disabled:
            return
        if self.timer:
            self.after_cancel(self.timer)
            self.timer = None
        start = self.current
        target = C['hover'] if value or self.selected else self.base
        def step(n):
            self.timer = None
            self.current = mix(start, target, n/MOTION['steps'])
            self.button.configure(bg=self.current)
            self._paint()
            if n < MOTION['steps']:
                self.timer = self.after(MOTION['step'], lambda: step(n+1))
        step(1 if self.motion() else MOTION['steps'])


class StatusIndicator(tk.Frame):
    def __init__(self, parent, fonts, motion=lambda: True):
        super().__init__(parent, bg=parent.cget('bg'))
        self.motion, self.state, self.phase, self.timer = motion, 'OFFLINE', False, None
        self.dot = tk.Canvas(self, width=18, height=18, bg=self.cget('bg'), highlightthickness=0)
        self.dot.pack(side='left', padx=(0, S['xs']))
        self.text = label(self, 'SAZABI OFFLINE', fonts, 'label')
        self.text.pack(side='left')
        self.bind('<Destroy>', self._destroy, add='+')
        self.set('OFFLINE')

    def _destroy(self, event):
        if event.widget is self and self.timer:
            self.after_cancel(self.timer)

    def set(self, state):
        self.state = state
        self.text.configure(text='SAZABI ' + state, fg=C[STATES[state]])
        if self.timer:
            self.after_cancel(self.timer)
            self.timer = None
        self._paint()

    def _paint(self):
        self.timer = None
        self.phase = not self.phase
        color = C[STATES[self.state]]
        self.dot.delete('all')
        glow = self.dot.create_oval(2, 2, 16, 16, fill=mix(C['background'], color, .14), outline='')
        self.dot.create_oval(6, 6, 12, 12, fill=color, outline='')
        if self.state == 'PROCESSANDO' and self.motion():
            self.dot.itemconfigure(glow, fill=mix(C['background'], color, .28 if self.phase else .12))
            self.timer = self.after(MOTION['pulse'], self._paint)


class ScrollPage(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=C['background'])
        self.canvas = tk.Canvas(self, bg=C['background'], highlightthickness=0)
        scroll = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        scroll.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.canvas.configure(yscrollcommand=scroll.set)
        self.content = tk.Frame(self.canvas, bg=C['background'])
        self.window = self.canvas.create_window(0, 0, anchor='nw', window=self.content)
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfigure(self.window, width=e.width))
        self.content.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<MouseWheel>', self._wheel)

    def _wheel(self, event):
        if self.content.winfo_height() > self.canvas.winfo_height():
            self.canvas.yview_scroll(-int(event.delta/120), 'units')

    def bind_wheel(self):
        def walk(widget):
            widget.bind('<MouseWheel>', self._wheel)
            for child in widget.winfo_children():
                walk(child)
        walk(self.content)
