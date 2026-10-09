import json
import threading
from unittest.mock import Mock, patch
import pytest
from core.commands.parser import parse
from core.commands.registry import default_registry, CommandDefinition
from core.commands.router import CommandRouter
from skills.registry import SkillRegistry
from skills.base import SkillContext, SkillResult
from skills.search.skill import SearchSkill
from core.config import Config
from core.bootstrap import build_agent
from core.worker import AgentWorker


def test_parser_preserves_arguments_and_normalizes_command():
    command = parse('  /SEARCH empresas de software em São Paulo  ')
    assert command.name == 'search'
    assert command.arguments == 'empresas de software em São Paulo'
    assert parse('procure clínicas') is None
    assert parse('/ai').arguments == ''


@pytest.mark.parametrize('text', ['/', '/???', 'x'*2001, '/search a\x00b', None])
def test_parser_rejects_invalid_input(text):
    with pytest.raises(ValueError):
        parse(text)


def test_registry_supports_new_skill_and_command_without_parser_changes():
    skill = Mock(name='custom')
    skill.name, skill.enabled = 'lead', True
    skill.execute.return_value = SkillResult(True, 'lead', 'completed', 'ok')
    skills = SkillRegistry()
    skills.register(skill)
    registry = default_registry()
    registry.register(CommandDefinition('lead', 'Analyze lead', skill='lead'))
    context = object()
    result = CommandRouter(skills, registry).execute('/lead Original Query', context)
    assert result.message == 'ok'
    skill.execute.assert_called_once_with('Original Query', context)
    skill.enabled = False
    assert not skills.available('lead')
    assert not skills.execute('lead', 'x', context).success
    assert not skills.execute('missing', 'x', context).success


def test_search_uses_existing_services_and_structured_output(agent):
    events = []
    agent.event_sink = lambda kind, data: events.append((kind, data))
    reply = agent.handle('/search clínicas em São Paulo')
    result = agent.last_skill_result.to_dict()
    assert result['success'] and result['status'] == 'completed'
    assert result['skill'] == 'search' and result['message'] == reply
    assert len(result['data']['companies']) == 2
    assert all(row['id'] and row['name'] for row in result['data']['companies'])
    states = [data['status'] for kind, data in events if kind == 'SKILL_STATE']
    assert states[0] == 'running' and 'processing' in states and states[-1] == 'completed'
    assert agent.skill_context is None


def test_no_key_is_unconfigured_not_fake_success():
    agent = build_agent(Config(database_path=':memory:'))
    try:
        assert 'ainda não configurada' in agent.handle('/search empresas em Campinas')
        assert not agent.last_skill_result.success
        assert agent.last_skill_result.status == 'unconfigured'
        assert agent.runs.count() == agent.companies.count() == 0
    finally:
        agent.db.close()


def test_skill_config_error_is_safe(agent, tmp_path):
    path = tmp_path / 'config.json'
    path.write_text('{invalid')
    result = SearchSkill(path).execute('query', SkillContext(agent))
    assert result.status == 'unconfigured' and str(path) not in result.message


def test_ai_only_requests_terminal_and_ollama_remains_separate(agent):
    with patch('analysis.ai_provider.OllamaProvider') as ollama:
        agent.handle('/ai Analise os leads')
        assert agent.last_skill_result.data == {'action': 'open_ai', 'draft': 'Analise os leads'}
        ollama.assert_not_called()


def test_cancelled_before_execution_creates_no_run(agent):
    cancel = threading.Event()
    cancel.set()
    agent.handle('/search clínicas em Campinas', cancelled=cancel)
    assert agent.last_skill_result.status == 'cancelled'
    assert agent.runs.count() == 0


def test_timeout_finishes_real_run_and_allows_retry(agent):
    skill = agent.skills.get('search')
    skill.timeout = .01
    original = agent.finder.find
    def delayed(criteria):
        import time
        time.sleep(.025)
        return original(criteria)
    with patch.object(agent.finder, 'find', side_effect=delayed):
        agent.handle('/search clínicas em São Paulo')
    assert agent.last_skill_result.status == 'failed'
    assert agent.runs.last().status == 'failed' and agent.runs.last().finished_at
    skill.timeout = 180
    agent.handle('/search clínicas em São Paulo')
    assert agent.last_skill_result.success


def test_worker_rejects_duplicate_and_cancels_running_skill():
    from tests.factories import build_agent as factory
    entered, release = threading.Event(), threading.Event()
    def build(config, **kwargs):
        agent = factory(config, **kwargs)
        original = agent.finder.find
        def blocked(criteria):
            entered.set()
            release.wait(4)
            return original(criteria)
        agent.finder.find = blocked
        return agent
    worker = AgentWorker(Config(mock=True, database_path=':memory:'), factory=build, progress=True)
    try:
        assert worker.events.get(timeout=5)[0] == 'ready'
        assert worker.submit('/search clínicas em São Paulo')
        assert entered.wait(3)
        assert not worker.submit('/search clínicas em São Paulo')
        worker.cancel()
        release.set()
        while True:
            kind, value = worker.events.get(timeout=5)
            if kind == 'command_result':
                assert value['status'] == 'cancelled'
                break
    finally:
        release.set()
        worker.close()
        worker.thread.join(5)
    assert not worker.thread.is_alive()


def test_failing_future_skill_returns_safe_standard_error():
    skill = Mock()
    skill.name, skill.enabled = 'other', True
    skill.execute.side_effect = RuntimeError('private path and token')
    registry = SkillRegistry()
    registry.register(skill)
    result = registry.execute('other', 'x', object())
    assert result.status == 'failed' and not result.success
    assert 'private' not in str(result.to_dict())


def test_search_restores_transport_after_cancel(agent):
    from utils.http_client import HttpClient
    from research.web_source import WebSource, TavilySearch
    cancel = threading.Event()
    client = HttpClient(interval=0)
    previous = client.checkpoint
    source = WebSource(TavilySearch('test-key', client=client), client=client)
    agent.finder.sources = agent.investigator.sources = [source]
    cancel.set()
    agent.handle('/search empresas em Campinas', cancelled=cancel)
    assert agent.last_skill_result.status == 'cancelled'
    assert client.checkpoint is previous and agent.skill_context is None


def test_http_checkpoint_stops_before_network():
    from utils.http_client import HttpClient
    from skills.base import ExecutionStopped
    client = HttpClient()
    client.checkpoint = Mock(side_effect=ExecutionStopped('cancelled'))
    with patch('utils.http_client.public_address') as resolve:
        with pytest.raises(ExecutionStopped):
            client.request('https://example.org')
        resolve.assert_not_called()


def test_status_does_not_expose_internal_database_path(agent):
    assert agent.config.database_path not in agent.handle('/status')


def test_region_answer_continues_the_same_skill(agent):
    assert agent.handle('/search oficinas') == 'Qual região devo pesquisar?'
    assert agent.last_skill_result.status == 'needs_input'
    assert agent.skills.get('search').state == 'idle'
    reply = agent.handle('Campinas')
    assert 'Pesquisa concluída' in reply
    assert agent.last_skill_result.skill == 'search' and agent.last_skill_result.success
    assert agent.last_skill_result.data['run_id'] == agent.runs.last().id
