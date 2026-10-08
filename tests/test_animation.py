import json
import random
import pytest
from ui.behavior import SazabiAnimationController, SazabiSleepController, SazabiStateManager, validate_settings
from ui.sprites import ASSETS
from ui.renderer import eye_rows


def settings():
    return validate_settings(json.loads((ASSETS/'animation.json').read_text()))


def test_sleep_and_wake_obey_activity_and_tasks():
    sleep = SazabiSleepController(0)
    assert sleep.update(119) == 'IDLE'
    assert sleep.update(121) == 'FALLING_ASLEEP'
    assert 0 < sleep.depth(121.5) < 1
    assert sleep.update(123) == 'SLEEPING'
    sleep.touch(124)
    assert sleep.phase == 'WAKE_UP'
    assert sleep.update(125) == 'IDLE'
    for now in range(126, 1000):
        assert sleep.update(now, blocked=True) == 'IDLE'
    assert sleep.update(1100) == 'IDLE'
    assert sleep.update(1120) == 'FALLING_ASLEEP'


def test_task_priority_does_not_lock_out_results():
    states = SazabiStateManager()
    assert states.resolve('IDLE', False, True, 'SLEEPING') == 'ERROR'
    for task in ('WORKING', 'RESEARCHING', 'ANALYZING', 'FOUND', 'RESPONDING'):
        assert states.resolve(task, True, False, 'IDLE') == task
        assert states.resolve(task, True, False, 'WAKE_UP') == 'WAKE_UP'
        assert states.resolve(task, True, False, 'IDLE', 'DRAGGING') == 'DRAGGING'
    assert states.resolve('IDLE', False, False, 'SLEEPING') == 'SLEEPING'


def test_interrupting_sleep_entry_does_not_snap_eyes_shut():
    sleep = SazabiSleepController(0)
    sleep.update(121)
    partial = sleep.depth(121.3)
    sleep.touch(121.3)
    assert sleep.depth(121.3) == partial
    assert sleep.depth(121.6) < partial


def test_twelve_hour_behavior_is_bounded_and_never_sleeps_during_work():
    controller = SazabiAnimationController(0, settings(), random.Random(12))
    for now in range(12*3600):
        busy = now % 300 < 150
        x, y, blink, phase = controller.sample(now, 'WORKING' if busy else 'IDLE', busy)
        assert abs(x) <= 4 and -3 <= y <= 2 and 0 <= blink <= 1
        if busy:
            assert phase not in ('SLEEPING', 'FALLING_ASLEEP')
    assert not hasattr(controller, 'history'), 'Behavior must not accumulate frames'


def test_blinks_vary_and_are_short():
    controller = SazabiAnimationController(0, settings(), random.Random(9))
    starts, active = [], False
    for i in range(6000):
        now = i/100
        _, _, blink, _ = controller.sample(now, 'WORKING', True)
        if blink > .01 and not active:
            starts.append(now)
        active = blink > .01
    intervals = [round(b-a, 1) for a, b in zip(starts, starts[1:])]
    assert len(starts) > 8 and len(set(intervals)) > 3
    assert all(.3 < value < 7.3 for value in intervals)
    assert any(value < .6 for value in intervals), 'Occasional double blink expected'


def test_jump_landing_and_work_scan_are_bounded():
    from ui.behavior import SazabiDragController, SazabiWorkController
    drag = SazabiDragController(settings())
    drag.start(0)
    assert drag.sample(.1)[0] == 'JUMPING'
    assert drag.sample(.4)[0] == 'DRAGGING'
    drag.release(1)
    samples = [drag.sample(1+i/100) for i in range(61)]
    assert all(-6 <= y <= 2 and .98 <= scale <= 1 for _, y, scale in samples)
    assert any(scale < .99 for _, _, scale in samples)
    assert drag.sample(2)[0] is None
    work = SazabiWorkController(0, settings(), random.Random(2))
    positions = [work.sample(i/100) for i in range(1500)]
    assert min(positions) == -3 and max(positions) == 3
    assert positions.count(0) > 100


def test_sleep_has_no_painted_closed_eyes():
    controller = SazabiAnimationController(0, settings(), random.Random(9))
    controller.sample(121, 'IDLE')
    assert controller.sample(123, 'IDLE')[2:] == (0., 'SLEEPING')


def test_sleep_can_be_disabled_and_invalid_durations_rejected():
    sleep = SazabiSleepController(0, timeout=0)
    assert sleep.update(100000) == 'IDLE'
    for value in (0, -10, float('nan'), float('inf'), True):
        bad = settings()
        bad['transition_ms'] = value
        with pytest.raises(ValueError):
            validate_settings(bad)


def test_eye_overlay_ignores_background_and_keeps_original_rgb():
    width, height = 30, 20
    rgb = bytearray(bytes((20, 22, 24))*width*height)
    mask = bytes([1]*width*height)
    for y in range(6, 14):
        for x in range(10, 18):
            rgb[(y*width+x)*3:(y*width+x)*3+3] = b'\xff'*3
    before = bytes(rgb)
    rows = eye_rows(rgb, mask, width, height)
    assert len(rows) == 8 and all(row[3] == '#141618' for row in rows)
    assert bytes(rgb) == before
    assert eye_rows(rgb, bytes(width*height), width, height) == []
