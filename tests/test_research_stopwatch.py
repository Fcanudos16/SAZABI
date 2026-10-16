from ui.countdown.stopwatch import Stopwatch


def test_elapsed_time_is_monotonic_and_frozen_until_next_search():
    now = [0]
    timer = Stopwatch(lambda: now[0])
    timer.start()
    now[0] = 1_230_000_000
    assert timer.elapsed_cs() == 123
    timer.start()  # repeated SEARCH_STARTED must not reset the submission time
    assert timer.elapsed_cs() == 123
    timer.finish('cancelled')
    now[0] += 5_000_000_000
    assert timer.elapsed_cs() == 123 and timer.status == 'CANCELLED'
    timer.finish('completed')  # unrelated later replies must not replace the result
    assert timer.status == 'CANCELLED'
    timer.start()
    assert timer.elapsed_cs() == 0 and timer.running


def test_elapsed_time_does_not_depend_on_refresh_frequency():
    now = [0]
    timer = Stopwatch(lambda: now[0])
    timer.start()
    now[0] = 400_123_000_000
    assert timer.elapsed_cs() == 40012
