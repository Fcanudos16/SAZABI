"""Adapter for the user's System monitor collectors; no network or database."""
from queue import Queue, Empty
import threading
import time


class SystemCollector:
    def __init__(self):
        # Optional at app startup: absent psutil must not stop the mascot.
        from system_monitor import cpu, memory, disk, uptime, system_info
        self.cpu, self.memory, self.disk, self.uptime, self.info = cpu, memory, disk, uptime, system_info
        self.metadata = None

    def prime(self):
        self.cpu.start_cpu_measurement()

    def collect(self):
        result = {'timestamp': time.time(), 'errors': {}}
        readers = {
            'cpu': lambda: {'percent': self.cpu.get_cpu_usage(), 'frequency': self.cpu.get_cpu_frequency_mhz()},
            'memory': self.memory.get_memory_info,
            'disk': self.disk.get_disk_info,
            'uptime': self.uptime.get_uptime_seconds,
            'system': self.system,
        }
        for name, reader in readers.items():
            try:
                result[name] = reader()
            except Exception as error:
                result[name] = None
                result['errors'][name] = type(error).__name__
        return result

    def system(self):
        if self.metadata is None:
            self.metadata = dict(os=self.info.get_os_name(), hostname=self.info.get_hostname(),
                                 processor=self.info.get_processor_name(), architecture=self.info.get_architecture(),
                                 physical=self.cpu.get_physical_cores(), logical=self.cpu.get_logical_cores())
        return self.metadata


class MonitorSampler:
    """One reusable, paused worker and one latest-value slot, never a backlog."""
    def __init__(self, factory=SystemCollector, interval=1.):
        self.factory, self.interval = factory, interval
        self.values = Queue(maxsize=1)
        self.condition = threading.Condition()
        self.active, self.stopped, self.generation = False, False, 0
        self.thread = threading.Thread(target=self.run, name='SAZABI-system-monitor', daemon=True)
        self.thread.start()

    def set_active(self, active):
        with self.condition:
            if active != self.active:
                self.generation += 1
            self.active = active
            self.latest()
            self.condition.notify_all()

    def latest(self):
        try:
            return self.values.get_nowait()
        except Empty:
            return None

    def close(self):
        with self.condition:
            self.stopped = True
            self.condition.notify_all()

    def run(self):
        collector, primed_generation = None, -1
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.active or self.stopped)
                if self.stopped:
                    return
                generation = self.generation
            try:
                if collector is None:
                    collector = self.factory()
                if primed_generation != generation:
                    collector.prime()
                    primed_generation = generation
                    # The first CPU reading establishes a baseline, not a real 0%.
                    with self.condition:
                        self.condition.wait_for(lambda: self.stopped or generation != self.generation, self.interval)
                        if self.stopped:
                            return
                        if generation != self.generation:
                            continue
                value = collector.collect()
            except ImportError:
                value = {'error': 'Monitor indisponível: instale psutil com python -m pip install -r requirements.txt e reinicie.'}
            except Exception as error:
                value = {'error': 'Não foi possível ler o sistema: ' + type(error).__name__}
            with self.condition:
                if self.stopped:
                    return
                if self.active and generation == self.generation:
                    self.latest()
                    self.values.put_nowait(value)
                self.condition.wait_for(lambda: self.stopped or generation != self.generation, self.interval)
