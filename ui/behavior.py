"""Clock-driven behavior, independent of Tk, network and the original artwork."""
import math
import random


def validate_settings(settings):
    limits = {'sleep_after_seconds': (0, 86400), 'transition_ms': (100, 1500),
              'important_transition_ms': (100, 1500), 'sleep_transition_ms': (100, 5000),
              'wake_transition_ms': (100, 3000), 'notification_transition_ms': (100, 1500),
              'jump_transition_ms': (150, 300), 'landing_transition_ms': (400, 800),
              'work_move_ms': (300, 500), 'work_pause_min_ms': (100, 2000), 'work_pause_max_ms': (100, 3000)}
    for key, (minimum, maximum) in limits.items():
        value = settings[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
            raise ValueError('Configuração de animação inválida: ' + key)
    for key in ('hover_wakes', 'blink_enabled'):
        if not isinstance(settings[key], bool):
            raise ValueError('Configuração de animação inválida: ' + key)
    if settings['work_pause_min_ms'] > settings['work_pause_max_ms']:
        raise ValueError('Intervalo de pausa de trabalho inválido')
    return settings


def ease(value):
    value = max(0., min(1., value))
    return value * value * (3 - 2 * value)


class SazabiSleepController:
    def __init__(self, now, timeout=120, enter=1.2, wake=.7):
        self.timeout, self.enter, self.wake = timeout, enter, wake
        self.last_activity, self.started = now, now
        self.phase = 'IDLE'
        self.wake_depth = 1.

    def touch(self, now):
        self.last_activity = now
        if self.phase in ('FALLING_ASLEEP', 'SLEEPING'):
            self.wake_depth = self.depth(now)
            self.phase, self.started = 'WAKE_UP', now

    def update(self, now, blocked=False):
        if blocked:
            self.touch(now)
        if self.phase == 'WAKE_UP' and now-self.started >= self.wake:
            self.phase = 'IDLE'
        if self.phase == 'IDLE' and not blocked and self.timeout > 0 and now-self.last_activity >= self.timeout:
            self.phase, self.started = 'FALLING_ASLEEP', now
        if self.phase == 'FALLING_ASLEEP' and now-self.started >= self.enter:
            self.phase = 'SLEEPING'
        return self.phase

    def depth(self, now):
        if self.phase == 'SLEEPING':
            return 1.
        if self.phase == 'FALLING_ASLEEP':
            return ease((now-self.started)/self.enter)
        if self.phase == 'WAKE_UP':
            return self.wake_depth*(1-ease((now-self.started)/self.wake))
        return 0.


class SazabiStateManager:
    """Task states override autonomy; task event order remains authoritative.

    Priorities arbitrate competing sources, not successive pipeline events.
    A completed WORKING must never lock out its subsequent FOUND/RESPONDING.
    """
    def resolve(self, task, busy, failed, phase, temporary=None):
        if failed:
            return 'ERROR'
        if phase in ('WAKE_UP', 'SLEEPING', 'FALLING_ASLEEP'):
            return phase
        if temporary:
            return temporary
        if busy or task != 'IDLE':
            return task
        return phase


class SazabiIdleController:
    def __init__(self, now, rng):
        self.rng, self.next_blink, self.blink_start = rng, now+rng.uniform(3, 7), None
        self.double_blink = False
        self.start, self.duration = now, rng.uniform(4.5, 7.5)
        self.amplitude, self.direction = rng.uniform(1.2, 2.4), rng.choice((-1, 1))

    def sample(self, now, activity):
        if now-self.start >= self.duration:
            self.start, self.duration = now, self.rng.uniform(4.5, 7.5)
            self.amplitude, self.direction = self.rng.uniform(1.2, 2.4), self.rng.choice((-1, 1))
        phase = min(1., (now-self.start)/self.duration)
        breath = math.sin(math.pi*phase)**2
        if self.blink_start is None and now >= self.next_blink:
            self.blink_start = now
        blink = 0.
        if self.blink_start is not None:
            t = (now-self.blink_start)/.22
            if t >= 1:
                self.blink_start = None
                gap = .16 if not self.double_blink and self.rng.random() < .12 else self.rng.uniform(3, 7)
                self.double_blink = gap == .16
                self.next_blink = now+gap
            else:
                blink = math.sin(math.pi*t)**2
        # Return to zero before drawing a new random cycle: no discontinuity.
        return self.direction*breath, -self.amplitude*breath, blink


class SazabiAnimationController:
    def __init__(self, now, settings, rng=None):
        self.rng = rng or random.Random()
        self.sleep = SazabiSleepController(now, settings['sleep_after_seconds'],
                                          settings['sleep_transition_ms']/1000, settings['wake_transition_ms']/1000)
        self.idle = SazabiIdleController(now, self.rng)
        self.states = SazabiStateManager()
        self.activity_level, self.visual_state = 2, 'IDLE'
        self.work = SazabiWorkController(now, settings, self.rng)

    def touch(self, now):
        self.sleep.touch(now)

    def sample(self, now, task, busy=False, failed=False, interacting=False, temporary=None):
        phase = self.sleep.update(now, busy or failed or task != 'IDLE' or interacting)
        self.visual_state = self.states.resolve(task, busy, failed, phase, temporary)
        self.activity_level = (0 if phase == 'SLEEPING' else 5 if task == 'RESEARCHING'
                               else 4 if busy else 3 if interacting else 2)
        x, y, blink = self.idle.sample(now, self.activity_level)
        depth = self.sleep.depth(now)
        y = y*(1-depth) + depth*(-.7*math.sin(now*.45)**2 + 2)
        x *= 1-depth
        if task in ('ANALYZING', 'WORKING', 'RESEARCHING') and phase == 'IDLE' and not temporary:
            x += self.work.sample(now)
        # Sleeping uses the unmodified official pose, never painted closed eyes.
        return round(x), round(y), blink if phase == 'IDLE' else 0., phase


class SazabiWorkController:
    def __init__(self, now, settings, rng):
        self.started, self.settings, self.rng = now, settings, rng
        self.stage, self.side = 'PAUSE', -1
        self.duration = self.pause()

    def pause(self):
        return self.rng.uniform(self.settings['work_pause_min_ms'], self.settings['work_pause_max_ms'])/1000

    def sample(self, now):
        elapsed = now-self.started
        if elapsed >= self.duration:
            self.started = now
            self.stage = {'PAUSE': 'OUT', 'OUT': 'HOLD', 'HOLD': 'RETURN', 'RETURN': 'PAUSE'}[self.stage]
            if self.stage == 'PAUSE':
                self.side *= -1
            self.duration = self.pause() if self.stage in ('PAUSE', 'HOLD') else self.settings['work_move_ms']/1000
            elapsed = 0
        amount = ease(elapsed/self.duration)
        return self.side*3*({'PAUSE': 0, 'OUT': amount, 'HOLD': 1, 'RETURN': 1-amount}[self.stage])


class SazabiDragController:
    def __init__(self, settings):
        self.settings, self.started, self.phase = settings, 0., None

    def start(self, now):
        self.started, self.phase = now, 'JUMPING'

    def release(self, now):
        self.started, self.phase = now, 'LANDING'

    def sample(self, now):
        t = now-self.started
        if self.phase == 'JUMPING' and t >= self.settings['jump_transition_ms']/1000:
            self.phase = 'DRAGGING'
        if self.phase == 'LANDING':
            duration = self.settings['landing_transition_ms']/1000
            if t >= duration:
                self.phase = None
                return None, 0, 1.
            p = t/duration
            y = -5*(1-ease(p/.45)) if p < .45 else 2*math.sin(math.pi*(p-.45)/.55)
            scale = 1-.02*math.sin(math.pi*max(0, (p-.35)/.65))
            return self.phase, round(y), scale
        if self.phase in ('JUMPING', 'DRAGGING'):
            y = -5*ease(t/(self.settings['jump_transition_ms']/1000)) - math.sin(t*4)
            return self.phase, round(y), 1.
        return None, 0, 1.
