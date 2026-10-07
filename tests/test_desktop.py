import pytest

from core.config import Config
from desktop import AgentWorker
from research.web_source import TavilySearch
from utils.http_client import FetchError


def test_worker_persists_and_closes_database(tmp_path):
    worker = AgentWorker(Config(mock=True, database_path=str(tmp_path / 'desktop.db')))
    try:
        assert worker.events.get(timeout=5)[0] == 'ready'
        worker.commands.put('procure clínicas em Campinas')
        kind, text = worker.events.get(timeout=10)
        assert kind == 'reply' and 'Pesquisa concluída' in text
        worker.commands.put('/status')
        assert 'Pesquisas realizadas: 1' in worker.events.get(timeout=5)[1]
    finally:
        worker.close()
        worker.thread.join(timeout=5)
    assert not worker.thread.is_alive()
    assert worker.events.get(timeout=5)[0] == 'closed'


def test_worker_startup_failure_is_reported():
    def fail(*args, **kwargs):
        raise RuntimeError('failure')
    worker = AgentWorker(Config(mock=True), factory=fail)
    worker.thread.join(timeout=5)
    assert worker.events.get(timeout=5)[0] == 'error'
    assert worker.events.get(timeout=5)[0] == 'closed'


def test_tavily_invalid_response_fails_without_inventing_results():
    from unittest.mock import Mock
    client = Mock()
    client.json.return_value = {'detail': 'invalid'}
    with pytest.raises(FetchError):
        TavilySearch('key', client=client).search('clínicas')


def test_native_window_mock_flow():
    import time
    tk = pytest.importorskip('tkinter')
    from desktop import DesktopApp
    try:
        root = tk.Tk()
    except tk.TclError as error:
        pytest.skip('Tcl/Tk ou sessão gráfica indisponível: ' + str(error))
    root.withdraw()
    app = DesktopApp(root, Config(mock=True, database_path=':memory:'))
    def until(predicate):
        deadline = time.monotonic() + 10
        while not predicate() and time.monotonic() < deadline:
            root.update()
            time.sleep(.02)
        assert predicate()
    try:
        until(lambda: not app.busy)
        app.submit('procure clínicas em Campinas')
        assert app.busy
        until(lambda: not app.busy)
        assert 'Pesquisa concluída' in app.output.get('1.0', 'end')
    finally:
        app.close()
        app.worker.thread.join(timeout=5)
        root.destroy()
