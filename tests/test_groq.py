from unittest.mock import patch
import pytest
from analysis.ai_provider import GroqProvider, GroqError, list_models
from core.bootstrap import build_agent
from core.config import Config
from core.connection import configure_groq
from database.models import Observation


def test_no_evidence_never_calls_model():
    with patch('analysis.ai_provider.request') as request:
        assert 'insuficiente' in GroqProvider('local', 'test-groq-key').summarize([])
        request.assert_not_called()


@pytest.mark.parametrize('choice', [
    {}, {'finish_reason': 'length', 'message': {'content': 'partial'}},
    {'finish_reason': 'stop', 'message': {'content': ''}},
    {'finish_reason': 'stop', 'message': {'content': 'text', 'tool_calls': [{}]}},
    {'finish_reason': 'stop', 'message': {'content': 'text', 'refusal': 'no'}},
    {'finish_reason': 'stop', 'message': {'content': 'x' * 6001}},
])
def test_incomplete_or_nontext_response_rejected(choice):
    with patch('analysis.ai_provider.request', return_value={'choices': [choice]}):
        with pytest.raises(GroqError):
            GroqProvider('local', 'test-groq-key').summarize([Observation('Evidence', 'source', 'https://example.org')])


def test_list_filters_inactive_and_malformed_items():
    with patch('analysis.ai_provider.request', return_value={'data': [None, {'id': 'model'}, {'id': 'inactive', 'active': False}]}):
        assert list_models('test-groq-key') == ['model']


def test_configure_preserves_search_key_and_activates_without_restart(tmp_path, monkeypatch):
    monkeypatch.setenv('AI_PROVIDER', 'none')
    monkeypatch.setenv('GROQ_MODEL', '')
    path = tmp_path / '.env'
    path.write_text('SEARCH_API_KEY=private-test-key\n', encoding='utf-8')
    agent = build_agent(Config(env_file=str(path), database_path=':memory:'))
    try:
        with patch('analysis.ai_provider.GroqProvider.check_model'):
            configure_groq(agent, 'local-1')
        assert agent.config.ai_provider == 'groq'
        assert agent.config.groq_model == 'local-1'
        assert 'SEARCH_API_KEY=private-test-key' in path.read_text()
        assert agent.db.query('SELECT * FROM conversation_history') == []
        configure_groq(agent, '')
        assert agent.config.ai_provider == 'none'
    finally:
        agent.db.close()


def test_ai_does_not_mutate_evidence_score_or_history(agent):
    agent.handle('investigue Oficina Silva')
    agent.config.mock = False
    agent.config.ai_provider = 'groq'
    agent.config.groq_model = 'local'
    tables = ('companies', 'sources', 'signals', 'hypotheses', 'conversation_history')
    before = {table: [tuple(row) for row in agent.db.query('SELECT * FROM ' + table)] for table in tables}
    with patch('analysis.ai_provider.GroqProvider.summarize', return_value='Interpretação de teste'):
        assert 'não validada' in agent.handle('/groq')
    after = {table: [tuple(row) for row in agent.db.query('SELECT * FROM ' + table)] for table in tables}
    assert before == after


@pytest.mark.parametrize('status', [401, 403, 429, 500])
def test_http_errors_hide_provider_body_and_close(status):
    from unittest.mock import Mock
    from analysis.ai_provider import request
    conn = Mock()
    conn.getresponse.return_value.status = status
    conn.getresponse.return_value.read.return_value = b'private-test-key secret provider error'
    with patch('analysis.ai_provider.http.client.HTTPSConnection', return_value=conn):
        with pytest.raises(GroqError) as error:
            request('/chat/completions', {}, api_key='private-test-key')
    assert 'private-test-key' not in str(error.value)
    conn.close.assert_called_once()
    assert conn.request.call_count == 1


def test_missing_key_does_not_connect():
    from analysis.ai_provider import request
    with patch('analysis.ai_provider.http.client.HTTPSConnection') as connection:
        with pytest.raises(GroqError, match='GROQ_API_KEY'):
            request('/models')
        connection.assert_not_called()


def test_config_loads_key_without_exposing_it(tmp_path, monkeypatch):
    from core.config import load_config
    for key in ('GROQ_API_KEY', 'GROQ_MODEL', 'AI_PROVIDER'):
        monkeypatch.delenv(key, raising=False)
    env = tmp_path / '.env'
    env.write_text('AI_PROVIDER=groq\nGROQ_API_KEY=private-test-key\n', encoding='utf-8')
    config = load_config(str(env))
    assert config.groq_api_key == 'private-test-key'
    assert config.groq_model == 'llama-3.3-70b-versatile'
    assert 'private-test-key' not in repr(config)
