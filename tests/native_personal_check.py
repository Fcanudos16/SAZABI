"""Real Tk/worker personal workflow, isolated DB, original sprites, no network."""
import sys
import time
import uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tkinter as tk
from core.config import Config
from desktop import DesktopApp
from ui import theme
from tests.native_desktop_check import screenshot

root = tk.Tk()
workspace = (Path('data')/('native-personal-'+uuid.uuid4().hex)).resolve()
workspace.mkdir(parents=True)
(workspace/'sample.py').write_text('try:\n    value = 1\nexcept:\n    pass\n')
app = DesktopApp(root, Config(database_path=':memory:', local_roots=(str(workspace),)))
errors = []
root.report_callback_exception = lambda kind, error, tb: errors.append(str(error))


def wait(predicate, seconds=12):
    until = time.monotonic()+seconds
    while time.monotonic() < until:
        root.update()
        if predicate():
            assert not errors, errors
            return
        time.sleep(.02)
    raise AssertionError('UI timeout')


try:
    wait(lambda: app.ready)
    terminal = app.get_terminal(); terminal.show()
    root.update()
    assert terminal.output.cget('background') == theme.BG
    assert terminal.output.cget('foreground') == theme.FG
    assert app.atlas.images['IDLE'] and root.winfo_viewable()
    terminal.entry.insert(0, '/ta'); terminal.autocomplete.refresh()
    assert [c.name for c in terminal.autocomplete.options] == ['task']
    terminal.autocomplete.accept()
    assert terminal.entry.get() == '/task '
    terminal.entry.delete(0, 'end')
    app.submit('/task add "Verificar interface"')
    wait(lambda: not app.busy)
    assert terminal.last_skill_result['success']
    app.submit('/task list')
    wait(lambda: not app.busy)
    assert 'Verificar interface' in terminal.output.get('1.0', 'end')
    assert terminal.window.winfo_width() <= root.winfo_screenwidth()
    assert terminal.window.winfo_height() <= root.winfo_screenheight()
    screenshot(terminal.window, Path('data/rework-terminal.png'))
    app.submit('/review fix sample.py bare-except')
    wait(lambda: not app.busy)
    assert terminal.last_skill_result['status'] == 'needs_confirmation'
    assert 'except Exception:' not in (workspace/'sample.py').read_text()
    screenshot(terminal.window, Path('data/rework-review-preview.png'))
    token = terminal.last_skill_result['data']['token']
    app.submit('/confirm '+token)
    wait(lambda: not app.busy)
    assert terminal.last_skill_result['success']
    assert 'except Exception:' in (workspace/'sample.py').read_text()
    app.submit('/files find ..')
    wait(lambda: not app.busy)
    assert not terminal.last_skill_result['success']
    terminal.hide(); root.update()
    assert root.winfo_viewable()
    print('PASS: real Tk, original mascot, black/green terminal, autocomplete, tasks, review preview/confirmation, errors, compact geometry, hide/show.')
finally:
    app.close()
    app.worker.thread.join(timeout=8)
    try: root.destroy()
    except tk.TclError: pass
