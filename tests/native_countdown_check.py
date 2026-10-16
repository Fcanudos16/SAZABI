"""Real Tk HUD, manual controls and worker integration; no network or real DB."""
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.config import Config
from desktop import DesktopApp
from tests.factories import build_agent
from tests.native_desktop_check import screenshot
from ui.countdown.timer_engine import State


def main():
    root = tk.Tk()
    if '--scale2' in sys.argv:
        root.tk.call('tk', 'scaling', 2.0)
    errors = []
    root.report_callback_exception = lambda kind, value, trace: errors.append(value)
    entered, release = threading.Event(), threading.Event()
    mode = ['success']

    def factory(config, notifier):
        agent = build_agent(config, notifier=notifier)
        original = agent.finder.find
        def find(criteria):
            entered.set()
            if not release.wait(45):
                raise RuntimeError('test release timeout')
            if mode[0] == 'failure':
                raise RuntimeError('synthetic search failure')
            if mode[0] == 'timeout':
                agent.skill_context.timeout = -1
                agent.skill_context.checkpoint()
            return original(criteria)
        agent.finder.find = find
        return agent

    app = DesktopApp(root, Config(database_path=':memory:', mock=True), factory=factory)

    def tick(seconds=.15):
        until = time.monotonic()+seconds
        while time.monotonic() < until:
            root.update()
            time.sleep(.01)
        assert not errors, errors

    def wait(check):
        until = time.monotonic()+10
        while not check() and time.monotonic() < until:
            tick(.03)
        assert check(), 'native check timed out'

    try:
        wait(lambda: app.ready)
        app.open_countdown()
        hud = app.countdown
        hud.toggle_terminal()
        assert hud.run_command('cinco minutos').ok
        assert hud.engine.configured_cs == 30000
        assert hud.run_command('5:00:00').ok
        assert hud.engine.configured_cs == 30000
        assert hud.run_command('set 1:30').ok
        assert hud.run_command('start').ok
        tick(.2)
        assert hud.engine.remaining_cs() < 9000
        assert hud.run_command('pause').ok
        paused = hud.engine.remaining_cs()
        tick(.2)
        assert hud.engine.remaining_cs() == paused
        assert hud.run_command('resume').ok
        assert not hud.run_command('set 0:30').ok
        hud.run_command('top off')
        assert not hud.top
        hud.run_command('top on')
        tick()
        screenshot(hud.window, Path('data/desktop-previews/countdown-running.png'))
        hud.run_command('reset')
        hud.run_command('set 0:00:05')
        hud.run_command('start')
        tick(.15)
        assert hud.engine.state is State.COMPLETE
        screenshot(hud.window, Path('data/desktop-previews/countdown-complete.png'))
        hud.escape()
        if hud.engine.state is State.COMPLETE:
            hud.escape()
        assert hud.engine.state is State.CONFIGURED
        hud.run_command('set 5:00'); hud.run_command('start')

        # Width scaling and dragging retain the HUD's aspect ratio.
        for width in (280, 700, 1100):
            hud.width = width; hud.apply_size(); hud.clamp(); hud.draw(); tick(.05)
            assert abs(hud.height-hud.width*340/700) <= 1
        hud.width = 400; hud.apply_size(); hud.clamp(); hud.draw()

        for outcome in ('success', 'cancelled', 'failure', 'timeout'):
            mode[0] = outcome
            entered.clear(); release.clear()
            app.submit('/search oficinas em Campinas')
            wait(entered.is_set)
            wait(lambda: app.research_timer is not None and app.research_timer.stopwatch.running)
            timer = app.research_timer
            assert not hasattr(timer, 'window')
            assert timer.canvas.winfo_toplevel() is app.get_terminal().window
            assert timer.stopwatch.running
            started = timer.stopwatch.started
            app.submit('/search outra pesquisa em Campinas')
            assert timer.stopwatch.started == started
            beginning = timer.stopwatch.elapsed_cs()
            tick(.2)
            assert timer.stopwatch.elapsed_cs() > beginning
            assert hud.engine.state is State.RUNNING
            app.get_terminal().hide(); tick(.1)
            assert not timer.canvas.winfo_ismapped()
            assert timer.stopwatch.running
            app.get_terminal().show()
            tick()
            if outcome == 'cancelled':
                app.cancel_search(); tick(.15)
                assert timer.stopwatch.running  # cancellation request is not completion
            assert timer.canvas.winfo_ismapped()
            screenshot(app.get_terminal().window, Path('data/desktop-previews/search-elapsed.png'))
            release.set()
            wait(lambda: not app.busy)
            assert not timer.stopwatch.running
            assert not timer.visible and not timer.frame.winfo_manager()
            expected = {'success':'COMPLETED', 'cancelled':'CANCELLED', 'failure':'FAILED', 'timeout':'FAILED'}[outcome]
            assert timer.stopwatch.status == expected, timer.stopwatch.status
            frozen = timer.stopwatch.elapsed_cs(); tick(.1)
            assert timer.stopwatch.elapsed_cs() == frozen

        app.submit('/search')
        wait(lambda: not app.busy)
        assert not app.research_timer.visible
        assert not app.research_timer.frame.winfo_manager()
        assert not app.research_timer.stopwatch.running
        mode[0] = 'success'
        entered.clear(); release.clear()
        app.submit('Campinas')
        wait(entered.is_set)
        wait(lambda: app.research_timer.stopwatch.running)
        tick(.15)
        assert app.research_timer.stopwatch.elapsed_cs() > 0
        release.set()
        wait(lambda: not app.busy)
        assert app.research_timer.stopwatch.status == 'COMPLETED'

        app.context_menu(SimpleNamespace(x_root=app.x, y_root=app.y))
        assert 'Countdown' in app.interaction.rows and 'Tempo da pesquisa' not in app.interaction.rows
        assert not hasattr(app, 'open_research_timer')
        app.interaction.close()
        hud.run_command('stop')
        assert hud.engine.state is State.STANDBY
        hud.run_command('exit')
        assert not hud.visible and root.winfo_exists()
        app.open_countdown()
        assert app.countdown is hud and hud.visible
        # Shutdown while work is active must dispose callbacks and terminate the worker.
        entered.clear(); release.clear()
        app.submit('/search oficinas em Campinas')
        wait(entered.is_set)
        wait(lambda: app.research_timer.stopwatch.running)
        print('PASS: native HUD, manual commands, alert, scaling, independent clocks, search success/cancel/failure/timeout/region, duplicate guard, hide/reopen, menu.')
    finally:
        release.set()
        app.close()
        app.worker.thread.join(10)
        assert not app.worker.thread.is_alive()
        assert app.countdown.closed and app.research_timer.closed
        assert app.countdown.job is None and app.research_timer.job is None
        try:
            root.update()
        except tk.TclError:
            pass
        assert not errors, errors


if __name__ == '__main__':
    main()
