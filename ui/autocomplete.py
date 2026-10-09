"""Local overlay; never changes the composer or parent window dimensions."""
import tkinter as tk
from core.commands.registry import default_registry
from ui.terminal import BG, FG, BORDER, FONT

class SlashAutocomplete:
    def __init__(self, terminal):
        self.terminal, self.entry = terminal, terminal.entry
        self.registry = default_registry()
        self.options = []
        self.visible = False
        self.box = tk.Listbox(terminal.body, bg=BG, fg=FG, selectbackground=BORDER,
                              selectforeground='#c9fbd5', font=FONT, bd=1,
                              highlightbackground=BORDER, highlightthickness=1,
                              exportselection=False, activestyle='none', takefocus=False)
        self.entry.bind('<KeyRelease>', self.refresh, add='+')
        self.entry.bind('<Down>', lambda event: self.move(1))
        self.entry.bind('<Up>', lambda event: self.move(-1))
        self.entry.bind('<Tab>', self.accept)
        self.entry.bind('<Escape>', self.escape)
        self.box.bind('<ButtonRelease-1>', self.accept)

    def refresh(self, event=None):
        if event and event.keysym in ('Up', 'Down', 'Return', 'Tab', 'Escape'):
            return
        prefix = self.entry.get()
        self.options = self.registry.suggestions(prefix) if prefix.startswith('/') and not any(c.isspace() for c in prefix) else []
        if not self.options:
            self.hide()
            return
        self.box.delete(0, 'end')
        for command in self.options:
            self.box.insert('end', '/' + command.name + '  ·  ' + command.description)
        self.box.configure(height=len(self.options))
        self.box.selection_set(0)
        self.box.place(relx=0, rely=1, x=12, y=-85, relwidth=1, width=-24, anchor='sw')
        self.box.lift()
        self.visible = True

    def move(self, direction):
        if self.visible:
            index = self.box.curselection()
            target = ((index[0] if index else 0)+direction) % len(self.options)
            self.box.selection_clear(0, 'end')
            self.box.selection_set(target)
            return 'break'

    def accept(self, event=None):
        if not self.visible:
            return None
        index = self.box.curselection()
        command = self.options[index[0] if index else 0]
        self.entry.delete(0, 'end')
        self.entry.insert(0, '/' + command.name + (' ' if command.skill else ''))
        self.entry.icursor('end')
        self.entry.focus_set()
        self.hide()
        return 'break'

    def escape(self, event=None):
        if self.visible:
            self.hide()
            return 'break'

    def hide(self):
        self.visible = False
        self.box.place_forget()
