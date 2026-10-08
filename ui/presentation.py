"""Small whole-art transforms. No detached body parts or new character drawings."""
import math


def transform_point(x, y, width, height, angle, scale):
    cx, cy = width/2, height*.70
    radians = math.radians(angle)
    cosine, sine = math.cos(radians), math.sin(radians)
    x, y = (x-cx)*scale, (y-cy)*scale
    return cx+x*cosine-y*sine, cy+x*sine+y*cosine


def transform_pixels(rgb, mask, width, height, angle, scale):
    """Nearest source samples retain the original palette; mask follows the art."""
    if angle == 0 and scale == 1:
        return bytes(rgb), bytes(mask)
    result = bytearray(b'\xff'*(width*height*3))
    shape = bytearray(width*height)
    cx, cy = width/2, height*.70
    radians = math.radians(angle)
    cosine, sine = math.cos(radians)/scale, math.sin(radians)/scale
    for y in range(height):
        for x in range(width):
            sx = round(cx+(x-cx)*cosine+(y-cy)*sine)
            sy = round(cy-(x-cx)*sine+(y-cy)*cosine)
            if 0 <= sx < width and 0 <= sy < height:
                i, source = y*width+x, sy*width+sx
                if mask[source]:
                    result[i*3:i*3+3] = rgb[source*3:source*3+3]
                    shape[i] = 1
    return bytes(result), bytes(shape)


class SazabiPresentationController:
    def __init__(self):
        self.angle, self.scale, self.last = 0., 1., None
        self.drag_impulse = 0.

    def drag(self, delta_x):
        self.drag_impulse = max(-1., min(1., delta_x/16))

    def reset(self):
        self.angle, self.scale, self.last, self.drag_impulse = 0., 1., None, 0.

    def sample(self, now, state, depth=0., work_x=0., landing_scale=1., state_elapsed=0.):
        dt = min(.2, max(0., now-self.last)) if self.last is not None else .05
        self.last = now
        self.drag_impulse *= math.exp(-dt*2)
        # Two nonmatching frequencies prevent a single obvious idle loop.
        angle = .9*math.sin(now*.25) + .45*math.sin(now*.16)
        scale = .99 + .01*math.cos(now*.35)**2
        if state in ('WORKING', 'RESEARCHING', 'ANALYZING'):
            angle = work_x
        elif state in ('JUMPING', 'DRAGGING'):
            angle, scale = self.drag_impulse+math.sin(now*1.2)*.4, 1.
        elif state == 'LANDING':
            angle, scale = 0., landing_scale
        elif state in ('SLEEPING', 'FALLING_ASLEEP', 'WAKE_UP'):
            angle = 1*depth
            scale = 1-depth*(.01+.01*math.sin(now*.4)**2)
        elif state == 'CONFIGURATION':
            angle, scale = .7*math.sin(now*.3), 1.
        elif state == 'EXIT_HOVER':
            angle = 1.*math.sin(state_elapsed*2.5)*max(0, 1-state_elapsed/2.4)
            scale = .99+.01*min(1, state_elapsed/.8)
        elif state in ('FOUND', 'RESPONDING'):
            angle = -1*math.sin(min(1, state_elapsed/1.6)*math.pi)
            scale = 1.
        blend = 1-math.exp(-dt*4)
        self.angle += (max(-3, min(3, angle))-self.angle)*blend
        self.scale += (max(.98, min(1, scale))-self.scale)*blend
        return round(self.angle), max(.98, min(1., round(self.scale, 2)))
