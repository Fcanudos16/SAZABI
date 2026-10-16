"""Research elapsed time, independent of the manually controlled countdown."""
import time

from .timer_engine import NS_PER_CS


class Stopwatch:
    def __init__(self, clock_ns=time.monotonic_ns):
        self.clock = clock_ns
        self.started = None
        self.elapsed = 0
        self.status = 'STANDBY'

    @property
    def running(self):
        return self.started is not None

    def start(self):
        if self.running:
            return
        self.elapsed = 0
        self.started = self.clock()
        self.status = 'SEARCHING'

    def elapsed_cs(self):
        value = self.clock() - self.started if self.running else self.elapsed
        return max(0, value // NS_PER_CS)

    def finish(self, status):
        if self.running:
            self.elapsed = max(0, self.clock() - self.started)
            self.started = None
            self.status = status.upper()
