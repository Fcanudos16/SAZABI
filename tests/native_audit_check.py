"""Focused native audit: real Tk/worker, synthetic LAYLA, no external requests."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tempfile
import time
import tkinter as tk
from unittest.mock import patch
from core.config import Config
from desktop import DesktopApp


def run():
    with tempfile.TemporaryDirectory() as directory:
        root = tk.Tk()
        root.withdraw()
        app = DesktopApp(root, Config(database_path=':memory:', env_file=str(Path(directory) / '.env')))
        errors = []
        root.report_callback_exception = lambda kind, error, tb: errors.append(error)
        def wait(check):
            deadline = time.monotonic() + 12
            while not check() and time.monotonic() < deadline:
                root.update()
                time.sleep(.02)
            assert not errors, errors
            assert check(), 'Native operation timed out'
        try:
            wait(lambda: app.ready)
            app.get_terminal().show()
            with patch('utils.http_client.HttpClient.request') as external:
                with patch.object(app.worker, 'submit', wraps=app.worker.submit) as submit:
                    app.terminal.entry.insert(0, '/search mercadinhos em Campinas')
                    app.open_search()
                    app.open_search()
                    assert submit.call_count == 1
                wait(lambda: app.terminal.last_skill_result is not None and not app.busy)
                assert app.terminal.last_skill_result['status'] == 'unconfigured'
                assert 'custo zero' in app.terminal.output.get('1.0', 'end')
                external.assert_not_called()
            with patch('integrations.layla.session.LaylaBridge') as factory:
                bridge = factory.return_value
                bridge.state = 'connected'
                bridge.send.return_value = 'Resposta sintética da auditoria.'
                app.submit('/ai Rascunho de auditoria')
                wait(lambda: app.ai_terminal is not None and str(app.ai_terminal.entry['state']) == 'normal')
                terminal = app.ai_terminal
                assert terminal.entry.get() == 'Rascunho de auditoria'
                bridge.send.assert_not_called()
                terminal.send()
                terminal.send()
                wait(lambda: any(text == 'Resposta sintética da auditoria.' for role, text in terminal.history))
                bridge.send.assert_called_once_with('Rascunho de auditoria')
                terminal.request('reset')
                wait(lambda: str(terminal.entry['state']) == 'normal')
                assert all(text != 'Resposta sintética da auditoria.' for role, text in terminal.history)
                assert app.terminal.last_skill_result['skill'] == 'search'
            print('PASS: native /search duplicate guard, unconfigured state, no external call; /ai draft, send, reset and independent result.')
        finally:
            app.close()
            app.worker.thread.join(5)
            if app.ai_terminal and app.ai_terminal.session:
                app.ai_terminal.session.thread.join(5)
            try:
                root.destroy()
            except tk.TclError:
                pass
            assert not app.worker.thread.is_alive()


if __name__ == '__main__':
    run()
