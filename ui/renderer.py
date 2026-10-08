"""Original poses plus temporary presentation layers; source files stay intact."""
from collections import Counter
import time
import tkinter as tk
from ui import native
from ui.behavior import ease
from ui.presentation import transform_point


def eye_rows(rgb, mask, width, height):
    """Find enclosed bright islands, never exterior JPEG background.

    Each lid uses the surrounding dark face's existing RGB. Rows follow the
    original eye silhouette; no replacement eye or facial contour is drawn.
    """
    candidates = {i for i, on in enumerate(mask) if on and min(rgb[i*3:i*3+3]) >= 96}
    groups = []
    while candidates:
        seed = candidates.pop()
        group, queue = {seed}, [seed]
        while queue:
            i = queue.pop()
            x, y = i % width, i // width
            for nx, ny in ((x-1,y), (x+1,y), (x,y-1), (x,y+1)):
                j = ny*width+nx
                if 0 <= nx < width and 0 <= ny < height and j in candidates:
                    candidates.remove(j)
                    group.add(j)
                    queue.append(j)
        if len(group) >= 40:
            groups.append(group)
    rows = []
    for group in sorted(groups, key=len, reverse=True)[:2]:
        top, bottom = min(i//width for i in group), max(i//width for i in group)
        surrounding = []
        for i in group:
            x, y = i % width, i // width
            for nx in (x-3, x+3):
                if 0 <= nx < width:
                    color = tuple(rgb[(y*width+nx)*3:(y*width+nx)*3+3])
                    if max(color) < 65:
                        surrounding.append(color)
        if not surrounding:
            continue  # An unsupported asset never receives guessed face colors.
        color = '#%02x%02x%02x' % Counter(surrounding).most_common(1)[0][0]
        for y in range(top, bottom+1):
            xs = sorted(i % width for i in group if i//width == y)
            if xs:
                rows.append((min(xs), y, max(xs)+1, color, (y-top+.5)/(bottom-top+1)))
    return rows


class SazabiRenderer:
    def __init__(self, app):
        self.app, self.state, self.level = app, 'IDLE', -1
        self.scale, self.angle = 1., 0
        self.lid_points = {}
        self.lids = {}
        for state, pixels in app.atlas.pixels.items():
            items = []
            for x, y, right, color, fraction in eye_rows(pixels, app.atlas.masks[state], app.atlas.width, app.atlas.height):
                points = (x, y, right, y, right, y+1, x, y+1)
                item = app.canvas.create_polygon(*points, fill=color, outline='', state='hidden')
                self.lid_points[item] = points
                items.append((item, fraction))
            self.lids[state] = items

    def pose(self, state):
        for items in self.lids.values():
            for item, _ in items:
                self.app.canvas.itemconfigure(item, state='hidden')
        self.state, self.level = state, -1
        self.scale, self.angle = 1., 0
        for item, _ in self.lids[state]:
            self.app.canvas.coords(item, *self.lid_points[item])
        self.app.canvas.itemconfigure(self.app.sprite, image=self.app.atlas.images[state])
        native.shape(self.app.root, self.app.atlas.regions[state])

    def blink(self, amount):
        if self.state in ('CONFIGURATION', 'EXIT_HOVER', 'LANDING'):
            amount = 0
        level = round(amount*8)
        if level == self.level:
            return
        self.level = level
        for item, fraction in self.lids[self.state]:
            self.app.canvas.itemconfigure(item, state='normal' if fraction <= level/8 else 'hidden')

    def transform(self, angle, scale):
        angle, scale = max(-3, min(3, round(angle))), max(.98, min(1., round(scale, 2)))
        if (angle, scale) == (self.angle, self.scale):
            return
        self.angle, self.scale = angle, scale
        image, region = self.current_frame()
        self.app.canvas.itemconfigure(self.app.sprite, image=image)
        native.shape(self.app.root, region)
        for item, _ in self.lids[self.state]:
            points = self.lid_points[item]
            transformed = []
            for x, y in zip(points[::2], points[1::2]):
                transformed.extend(transform_point(x, y, self.app.atlas.width, self.app.atlas.height, angle, scale))
            self.app.canvas.coords(item, *transformed)

    def current_frame(self):
        return self.app.atlas.frame(self.state, self.angle, self.scale)


class SazabiTransitionController:
    """At most one passive outgoing layer plus the incoming main window."""
    def __init__(self, app, renderer):
        self.app, self.renderer, self.ghost, self.job = app, renderer, None, None

    def finish(self):
        if self.job:
            self.app.root.after_cancel(self.job)
            self.job = None
        if self.ghost:
            self.ghost.destroy()
            self.ghost = None
        self.app.root.attributes('-alpha', 1)

    def start(self, state, duration=None):
        if state == self.renderer.state:
            return
        self.finish()
        if self.app.reduced_motion.get():
            self.renderer.pose(state)
            return
        image, region = self.renderer.current_frame()
        window = self.ghost = tk.Toplevel(self.app.root)
        window.withdraw()
        window.overrideredirect(True)
        tk.Label(window, image=image, bd=0, highlightthickness=0).pack()
        window.update_idletasks()
        native.no_activate(window)
        native.click_through(window)
        native.shape(window, region)
        window.attributes('-alpha', 1)
        window.deiconify()
        native.show_passive(window, self.app.x, self.app.y, self.app.atlas.width, self.app.atlas.height, self.app.always_on_top.get())
        self.app.root.attributes('-alpha', 0)
        self.renderer.pose(state)
        self.started = time.monotonic()
        key = 'important_transition_ms' if state in ('FOUND', 'RESPONDING') else 'transition_ms'
        self.duration = duration or self.app.animation_settings[key]/1000
        self.tick()

    def tick(self):
        self.job = None
        if not self.ghost:
            return
        progress = (time.monotonic()-self.started)/self.duration
        if progress >= 1:
            self.finish()
            return
        alpha = ease(progress)
        self.app.root.attributes('-alpha', alpha)
        self.ghost.attributes('-alpha', 1-alpha)
        dx, dy = self.app.motion_offset
        native.position(self.ghost, self.app.x+dx, self.app.y+dy)
        self.job = self.app.root.after(33, self.tick)
