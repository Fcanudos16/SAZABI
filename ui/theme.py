"""Single source for all desktop chrome; original mascot pixels are excluded.

Change these tokens before startup to theme every window in the Tk interpreter.
"""
import tkinter as tk
from tkinter import ttk

BG = '#080d0a'
SHELL_BG = '#0b140e'
FG = '#8fdfa7'
MUTED = '#72937b'
BORDER = '#254331'
ACCENT = BORDER
FOCUS = '#659f76'
HOVER = '#3e7050'
BRIGHT = '#c9fbd5'
SELECTION = BORDER
LOADING = FG
FONT = ('Consolas', 10)


def install(root):
    """Options cover widgets created later, including Tcl combobox popdowns."""
    options = dict(background=BG, foreground=FG, insertBackground=FG,
                   selectBackground=SELECTION, selectForeground=BRIGHT,
                   activeBackground=HOVER, activeForeground=BRIGHT,
                   disabledForeground=MUTED, disabledBackground=BG,
                   highlightBackground=BORDER, highlightColor=FOCUS,
                   troughColor=BG, font=FONT)
    for name, value in options.items():
        root.option_add('*' + name, value)
    root.option_add('*Entry.highlightThickness', 1)
    root.option_add('*Text.highlightThickness', 1)
    for name, value in dict(background=BG, foreground=FG, selectBackground=SELECTION,
                            selectForeground=BRIGHT).items():
        root.option_add('*TCombobox*Listbox.' + name, value)
    style = ttk.Style(root)
    style.theme_use('clam')
    # The combobox creates its own unnamed scrollbar; style its base too.
    for name in ('Vertical.TScrollbar', 'Sazabi.Vertical.TScrollbar'):
        style.configure(name, background=BORDER, troughcolor=BG,
                        bordercolor=BG, lightcolor=BORDER, darkcolor=BORDER,
                        arrowcolor=FG, width=12, arrowsize=12)
        style.map(name, background=[('pressed', FOCUS), ('active', HOVER)],
                  lightcolor=[('active', HOVER)], darkcolor=[('active', HOVER)])
    style.configure('Sazabi.TCombobox', fieldbackground=BG, background=BORDER,
                    foreground=FG, arrowcolor=FG, bordercolor=BORDER,
                    lightcolor=BORDER, darkcolor=BORDER, padding=4)
    style.map('Sazabi.TCombobox', fieldbackground=[('readonly', BG), ('disabled', BG)],
              foreground=[('disabled', MUTED), ('readonly', FG)],
              background=[('active', HOVER)], bordercolor=[('focus', FOCUS)],
              selectbackground=[('readonly', SELECTION)], selectforeground=[('readonly', BRIGHT)])
    style.configure('Sazabi.Horizontal.TProgressbar', background=LOADING, troughcolor=BG,
                    bordercolor=BORDER, lightcolor=LOADING, darkcolor=LOADING)


def button(parent, text, command):
    return tk.Button(parent, text=text, command=command, bg=BG, fg=FG,
                     activebackground=HOVER, activeforeground=BRIGHT,
                     font=FONT, relief='flat', bd=0, padx=9, pady=5,
                     highlightthickness=1, highlightbackground=BORDER,
                     highlightcolor=FOCUS, takefocus=True)


def titlebar(window, title, close):
    """Solid themed chrome for compact windows; hiding never destroys the pet."""
    window.overrideredirect(True)
    bar = tk.Frame(window, bg=SHELL_BG, highlightbackground=BORDER, highlightthickness=1)
    bar.pack(fill='x')
    label = tk.Label(bar, text=title, bg=SHELL_BG, fg=FG, font=FONT, padx=10, pady=6)
    label.pack(side='left', fill='x', expand=True)
    button(bar, '×', close).pack(side='right')
    from ui import native
    button(bar, '−', lambda: native.minimize(window)).pack(side='right')
    draggable(window, bar, label)
    return bar


def draggable(window, *widgets):
    """Attach drag only to title surfaces, never to inputs or window buttons."""
    start = []
    def press(event):
        start[:] = [event.x_root, event.y_root, window.winfo_rootx(), window.winfo_rooty()]
    def drag(event):
        if start:
            from ui import native
            native.position(window, start[2]+event.x_root-start[0], start[3]+event.y_root-start[1])
    for widget in widgets:
        widget.bind('<ButtonPress-1>', press)
        widget.bind('<B1-Motion>', drag)
