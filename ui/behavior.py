"""Clock-driven behavior, independent of Tk, network and the original artwork."""
import math
import random


def validate_settings(settings):
    limits = {'sleep_after_seconds': (0, 86400), 'transition_ms': (100, 1500),
              'important_transition_ms': (100, 1500), 'sleep_transition_ms': (100, 5000),
              'wake_transition_ms': (100, 3000), 'notification_transition_ms': (100, 1500)}
    for key, (minimum, maximum) in limits.items():
        value = settings[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
            raise ValueError('Configuração de animação inválida: ' + key)
    for key in ('hover_wakes', 'blink_enabled'):
        if not isinstance(settings[key], bool):
            raise ValueError('Configuração de animação inválida: ' + key)
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
    def resolve(self, task, busy, failed, phase):
        if failed:
            return 'ERROR'
        if busy or task != 'IDLE':
            return task
        return phase


class SazabiIdleController:
    def __init__(self, now, rng):
        self.rng, self.next_blink, self.blink_start = rng, now+rng.uniform(2.8, 5.8), None
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
                self.next_blink = now+self.rng.uniform(2.8, 6.2)/(1+.03*activity)
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

    def touch(self, now):
        self.sleep.touch(now)

    def sample(self, now, task, busy=False, failed=False, interacting=False):
        phase = self.sleep.update(now, busy or failed or task != 'IDLE' or interacting)
        self.visual_state = self.states.resolve(task, busy, failed, phase)
        self.activity_level = (0 if phase == 'SLEEPING' else 5 if task == 'RESEARCHING'
                               else 4 if busy else 3 if interacting else 2)
        x, y, blink = self.idle.sample(now, self.activity_level)
        depth = self.sleep.depth(now)
        y = y*(1-depth) + depth*(-.7*math.sin(now*.45)**2 + 2)
        x *= 1-depth
        return round(x), round(y), max(blink*(1-depth), depth), phase
