import pytest

from core.config import Config
from tests.factories import build_agent
from desktop import AgentWorker
from research.web_source import TavilySearch
from utils.http_client import FetchError


def test_worker_persists_and_closes_database(tmp_path):
    worker = AgentWorker(Config(mock=True, database_path=str(tmp_path / 'desktop.db')), factory=build_agent)
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


def test_main_defaults_to_desktop_without_key(tmp_path, monkeypatch):
    from unittest.mock import Mock
    import main
    config = Config(database_path=':memory:', search_api_key='')
    monkeypatch.setattr(main, 'load_config', lambda *a, **kw: config)
    monkeypatch.setattr(main, 'setup_logging', lambda *a, **kw: None)
    launch = Mock(return_value=0)
    monkeypatch.setattr('desktop.run_desktop', launch)
    assert main.main([]) == 0
    launch.assert_called_once_with(config)


def test_real_worker_without_key_keeps_local_commands_available():
    worker = AgentWorker(Config(database_path=':memory:', search_api_key=''))
    try:
        kind, message = worker.events.get(timeout=5)
        assert kind == 'ready' and 'Configuração' in message
        worker.commands.put('/status')
        assert 'Fontes ativas: nenhuma' in worker.events.get(timeout=5)[1]
        worker.commands.put('/history')
        assert worker.events.get(timeout=5)[0] == 'reply'
    finally:
        worker.close()
        worker.thread.join(timeout=5)
    assert not worker.thread.is_alive()


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
    app = DesktopApp(root, Config(mock=True, database_path=':memory:'), factory=build_agent)
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
