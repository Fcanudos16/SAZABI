import threading
import time
from unittest.mock import Mock

from system_monitor.service import SystemCollector, MonitorSampler
from system_monitor.formatter import create_progress_bar, format_bytes, format_uptime


def wait_for(predicate, timeout=2):
    deadline = time.monotonic()+timeout
    while not predicate():
        assert time.monotonic() < deadline
        time.sleep(.005)


def test_formatters_fix_negative_bars_and_binary_units():
    assert '█' not in create_progress_bar(-20)
    assert create_progress_bar(150).count('█') == 20
    assert format_bytes(1024**3) == '1.00 GiB'
    assert format_uptime(-2) == '00h 00m 00s'
    assert format_uptime(90061) == '1d 01h 01m 01s'


def test_collector_keeps_available_metrics_after_one_sensor_fails():
    collector = SystemCollector()
    collector.cpu = Mock()
    collector.cpu.get_cpu_usage.return_value = 12.5
    collector.cpu.get_cpu_frequency_mhz.return_value = None
    collector.memory = Mock()
    collector.memory.get_memory_info.side_effect = PermissionError()
    collector.disk = Mock()
    collector.disk.get_disk_info.return_value = {'percent': 30}
    collector.uptime = Mock()
    collector.uptime.get_uptime_seconds.return_value = 123
    collector.metadata = {'os': 'test fixture'}
    value = collector.collect()
    assert value['cpu']['percent'] == 12.5 and value['memory'] is None
    assert value['disk']['percent'] == 30 and value['uptime'] == 123
    assert value['errors'] == {'memory': 'PermissionError'}


def test_sampler_pauses_restarts_and_uses_only_one_thread_and_slot():
    collector = Mock()
    collector.collect.return_value = {'cpu': {'percent': 10}}
    sampler = MonitorSampler(lambda: collector, interval=.01)
    try:
        assert not collector.collect.called
        sampler.set_active(True)
        wait_for(lambda: collector.collect.call_count >= 3)
        assert sampler.values.qsize() == 1
        sampler.set_active(False)
        time.sleep(.03)
        count = collector.collect.call_count
        time.sleep(.03)
        assert collector.collect.call_count == count
        assert sampler.latest() is None
        thread = sampler.thread
        sampler.set_active(True)
        wait_for(lambda: collector.collect.call_count > count)
        assert sampler.thread is thread and collector.prime.call_count == 2
    finally:
        sampler.close()
        sampler.thread.join(2)
    assert not sampler.thread.is_alive()


def test_inflight_read_is_discarded_when_monitor_closes():
    entered, release = threading.Event(), threading.Event()
    collector = Mock()
    def collect():
        entered.set()
        release.wait(2)
        return {'cpu': {'percent': 99}}
    collector.collect.side_effect = collect
    sampler = MonitorSampler(lambda: collector, interval=.01)
    try:
        sampler.set_active(True)
        assert entered.wait(2)
        sampler.set_active(False)
        release.set()
        time.sleep(.04)
        assert sampler.latest() is None
    finally:
        release.set()
        sampler.close()
        sampler.thread.join(2)


def test_missing_dependency_is_an_explicit_error_not_fake_metrics():
    def unavailable():
        raise ModuleNotFoundError('psutil')
    sampler = MonitorSampler(unavailable, interval=.01)
    try:
        sampler.set_active(True)
        wait_for(lambda: not sampler.values.empty())
        value = sampler.latest()
        assert 'psutil' in value['error'] and 'cpu' not in value
    finally:
        sampler.close()
        sampler.thread.join(2)
