"""Nonmodal native Tk popup: animations remain alive while choosing an action."""
import tkinter as tk
from ui import native
from ui.terminal import BG, FG, BORDER, FONT


class SazabiInteractionController:
    def __init__(self, app):
        self.app, self.windows, self.rows = app, [], {}
        self.active, self.focus_job = None, None
        self.menu_open, self.exit_hover = False, False

    def open(self, model, x, y):
        self.close()
        self.menu_open = True
        self.app.refresh_visual()
        self.build(model, x, y)

    def build(self, model, x, y, child=False):
        window = tk.Toplevel(self.app.root)
        window.withdraw()
        window.overrideredirect(True)
        window.configure(bg=BORDER)
        rows = []
        for i in range(model.index('end')+1):
            kind = model.type(i)
            if kind == 'separator':
                tk.Frame(window, bg=BORDER, height=1).pack(fill='x', pady=4)
                continue
            label = model.entrycget(i, 'label')
            prefix = ''
            if kind in ('checkbutton', 'radiobutton'):
                value = window.getvar(model.entrycget(i, 'variable'))
                expected = model.entrycget(i, 'value') if kind == 'radiobutton' else model.entrycget(i, 'onvalue')
                prefix = '✓ ' if str(value) == str(expected) else '  '
            button = tk.Button(window, text=prefix+label+('  ›' if kind == 'cascade' else ''),
                               anchor='w', bg=BG, fg=FG, activebackground=BORDER, activeforeground=FG,
                               relief='flat', bd=0, font=FONT, padx=12, pady=6, takefocus=False)
            button.pack(fill='x', padx=1)
            row = (model, i, label, button, window, kind)
            rows.append(row)
            self.rows[label] = row
            button.configure(command=lambda r=row: self.activate(r))
            button.bind('<Enter>', lambda event, r=row: self.highlight(r))
            button.bind('<Leave>', lambda event: self.leave())
        self.windows.append(window)
        window.bind('<Escape>', lambda event: self.close())
        window.bind('<Down>', lambda event: self.step(rows, 1))
        window.bind('<Up>', lambda event: self.step(rows, -1))
        window.bind('<Home>', lambda event: self.highlight(rows[0]))
        window.bind('<Return>', lambda event: self.activate(self.active) if self.active else None)
        window.bind('<Right>', lambda event: self.activate(self.active) if self.active and self.active[5] == 'cascade' else None)
        window.bind('<Left>', lambda event: self.close_child())
        window.bind('<FocusOut>', self.focus_out)
        window.update_idletasks()
        width, height = window.winfo_reqwidth(), window.winfo_reqheight()
        left, top, right, bottom = native.work_area(self.app.root)
        if not child:
            x, y = native.place_near(self.app.x, self.app.y, self.app.atlas.width, self.app.atlas.height,
                                     width, height, (left, top, right, bottom))
        elif x+width > right:
            x = self.windows[0].winfo_rootx()-width
        x, y = max(left, min(x, right-width)), max(top, min(y, bottom-height))
        window.geometry(f'{width}x{height}{x:+d}{y:+d}')
        window.attributes('-topmost', self.app.always_on_top.get())
        window.deiconify()
        window.update_idletasks()
        native.position(window, x, y)
        window.focus_force()
        if child:
            self.highlight(rows[0])

    def leave(self):
        if self.exit_hover:
            self.exit_hover = False
            self.app.refresh_visual()

    def highlight(self, row):
        if self.active and self.active[3].winfo_exists():
            self.active[3].configure(bg=BG)
        self.active = row
        row[3].configure(bg=BORDER)
        self.exit_hover = row[2] == 'Encerrar SAZABI'
        self.app.refresh_visual()

    def step(self, rows, direction):
        index = rows.index(self.active) if self.active in rows else (-1 if direction > 0 else 0)
        self.highlight(rows[(index+direction) % len(rows)])

    def activate(self, row):
        model, index, label, button, window, kind = row
        if kind == 'cascade':
            self.close_child()
            submenu = self.app.root.nametowidget(model.entrycget(index, 'menu'))
            self.build(submenu, window.winfo_rootx()+window.winfo_width(), button.winfo_rooty(), True)
            return
        self.close()
        model.invoke(index)

    def close_child(self):
        if len(self.windows) > 1:
            child = self.windows.pop()
            self.rows = {name: row for name, row in self.rows.items() if row[4] is not child}
            self.active = None
            child.destroy()
            self.windows[0].focus_force()

    def focus_out(self, event):
        if self.windows:
            if self.focus_job:
                self.app.root.after_cancel(self.focus_job)
            self.focus_job = self.app.root.after(100, self.check_focus)

    def check_focus(self):
        self.focus_job = None
        if self.windows and not any(native.is_foreground(window) for window in self.windows):
            self.close()

    def close(self):
        if self.focus_job:
            self.app.root.after_cancel(self.focus_job)
            self.focus_job = None
        windows, self.windows = self.windows, []
        self.rows, self.active = {}, None
        was_open = self.menu_open
        self.menu_open = self.exit_hover = False
        for window in reversed(windows):
            window.destroy()
        if was_open and not self.app.closing:
            self.app.refresh_visual()
