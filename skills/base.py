"""Stable command/skill contract; only serializable public data reaches the UI."""
from dataclasses import dataclass, field, asdict
from threading import Event
import time

class ExecutionStopped(Exception):
    def __init__(self, status):
        self.status = status

@dataclass
class SkillResult:
    success: bool
    skill: str
    status: str
    message: str = ''
    data: dict = field(default_factory=dict)
    error: str = ''

    def to_dict(self):
        return asdict(self)

@dataclass
class SkillContext:
    agent: object
    criteria: object = None
    cancelled: Event = field(default_factory=Event)
    timeout: float = 180
    started: float = field(default_factory=time.monotonic)

    def checkpoint(self):
        if self.cancelled.is_set():
            raise ExecutionStopped('cancelled')
        if time.monotonic() - self.started >= self.timeout:
            raise ExecutionStopped('failed')

    def state(self, status):
        self.agent.emit('SKILL_STATE', skill='search', status=status)
