from unittest.mock import patch
import pytest
from analysis.ai_provider import OllamaProvider, OllamaError, list_models
from core.bootstrap import build_agent
from core.config import Config
from core.connection import configure_ollama
from database.models import Observation


def test_no_evidence_never_calls_model():
    with patch('analysis.ai_provider.request') as request:
        assert 'insuficiente' in OllamaProvider('local').summarize([])
        request.assert_not_called()


@pytest.mark.parametrize('response', [
    {'done': False, 'message': {'content': 'partial'}},
    {'done': True, 'done_reason': 'length', 'message': {'content': 'partial'}},
    {'done': True, 'message': {'content': ''}},
    {'done': True, 'message': {'content': 'text', 'tool_calls': [{}]}},
])
def test_incomplete_or_nontext_response_rejected(response):
    with patch('analysis.ai_provider.request', side_effect=[{'details': {'family': 'local'}}, response]):
        with pytest.raises(OllamaError):
            OllamaProvider('local').summarize([Observation('Evidence', 'source', 'https://example.org')])


def test_cloud_model_rejected_before_evidence_sent():
    with patch('analysis.ai_provider.request', return_value={'remote_host': 'https://ollama.com'}) as request:
        with pytest.raises(OllamaError, match='nuvem'):
            OllamaProvider('remote').summarize([Observation('Private evidence', 'source', 'https://example.org')])
        assert request.call_count == 1
        assert request.call_args.args == ('/api/show', {'model': 'remote'})


def test_list_filters_cloud_and_malformed_items():
    with patch('analysis.ai_provider.request', return_value={'models': [None, {'name': 'local:1'},
        {'name': 'cloud-model'}, {'name': 'remote', 'remote_host': 'https://ollama.com'}]}):
        assert list_models() == ['local:1']


def test_configure_preserves_search_key_and_activates_without_restart(tmp_path, monkeypatch):
    monkeypatch.setenv('AI_PROVIDER', 'none')
    monkeypatch.setenv('OLLAMA_MODEL', '')
    path = tmp_path / '.env'
    path.write_text('SEARCH_API_KEY=private-test-key\n', encoding='utf-8')
    agent = build_agent(Config(env_file=str(path), database_path=':memory:'))
    try:
        with patch('analysis.ai_provider.OllamaProvider.check_model'):
            configure_ollama(agent, 'local:1')
        assert agent.config.ai_provider == 'ollama'
        assert agent.config.ollama_model == 'local:1'
        assert 'SEARCH_API_KEY=private-test-key' in path.read_text()
        assert agent.db.query('SELECT * FROM conversation_history') == []
        configure_ollama(agent, '')
        assert agent.config.ai_provider == 'none'
    finally:
        agent.db.close()


def test_ai_does_not_mutate_evidence_score_or_history(agent):
    agent.handle('investigue Oficina Silva')
    agent.config.mock = False
    agent.config.ai_provider = 'ollama'
    agent.config.ollama_model = 'local'
    tables = ('companies', 'sources', 'signals', 'hypotheses', 'conversation_history')
    before = {table: [tuple(row) for row in agent.db.query('SELECT * FROM ' + table)] for table in tables}
    with patch('analysis.ai_provider.OllamaProvider.summarize', return_value='Interpretação de teste'):
        assert 'não validada' in agent.handle('/ai')
    after = {table: [tuple(row) for row in agent.db.query('SELECT * FROM ' + table)] for table in tables}
    assert before == after
