"""Regression checks for real failure boundaries; all data is isolated."""
from unittest.mock import Mock, patch
import pytest
from core.config import load_config
from database.models import Observation
from utils.http_client import HttpClient, FetchError


def seed(agent):
    agent.handle('investigue Oficina Silva')
    return agent.companies.search_by_name('Oficina Silva')[0]


def test_refresh_without_sources_preserves_evidence_and_timestamp(agent):
    profile = seed(agent)
    before = agent.sources.list_for_company(profile.id)
    agent.investigator.sources = []
    reply = agent.handle('atualize a investigação da Oficina Silva')
    assert 'indisponíve' in reply
    assert agent.sources.list_for_company(profile.id) == before
    assert agent.companies.get(profile.id).last_researched == profile.last_researched


def test_failed_first_collection_does_not_create_successful_cache(agent):
    profile = seed(agent)
    agent.sources.replace_for_company(profile.id, [])
    profile.investigated, profile.last_researched = False, None
    agent.companies.update(profile)
    source = Mock(name='offline_source')
    source.name = 'offline'
    source.fetch_observations.side_effect = FetchError('offline')
    agent.investigator.sources = [source]
    outcome = agent._investigate(profile, refresh=True)
    assert not outcome.from_cache
    stored = agent.companies.get(profile.id)
    assert not stored.investigated and stored.last_researched is None
    assert agent.investigator.errors


def test_partial_collection_preserves_previous_complete_snapshot(agent):
    profile = seed(agent)
    before = agent.sources.list_for_company(profile.id)
    good, bad = Mock(), Mock()
    good.name, bad.name = 'good', 'bad'
    good.fetch_observations.return_value = [Observation('New evidence', 'good', 'https://example.org')]
    bad.fetch_observations.side_effect = FetchError('offline')
    agent.investigator.sources = [good, bad]
    agent._investigate(profile, refresh=True)
    assert agent.sources.list_for_company(profile.id) == before
    assert agent.companies.get(profile.id).last_researched == profile.last_researched


def test_investigation_write_failure_rolls_back_all_evidence(agent):
    profile = seed(agent)
    before = {table: [tuple(row) for row in agent.db.query('SELECT * FROM '+table)]
              for table in ('companies', 'sources', 'signals', 'hypotheses')}
    agent.db.execute("CREATE TRIGGER fail_hypothesis BEFORE INSERT ON hypotheses BEGIN SELECT RAISE(ABORT, 'test write failure'); END")
    with pytest.raises(Exception, match='test write failure'):
        agent._investigate(profile, refresh=True)
    for table, rows in before.items():
        assert [tuple(row) for row in agent.db.query('SELECT * FROM '+table)] == rows
    agent.db.execute('DROP TRIGGER fail_hypothesis')
    agent._investigate(agent.companies.get(profile.id), refresh=True)
    assert agent.hypotheses.list_for_company(profile.id)


def test_internal_search_failure_finishes_run_and_allows_next_command(agent):
    with patch.object(agent.finder, 'find', side_effect=RuntimeError('test failure')):
        assert 'erro interno' in agent.handle('procure clínicas em Campinas')
    run = agent.runs.last()
    assert run.status == 'failed' and run.finished_at and run.error_message
    assert 'Pesquisa concluída' in agent.handle('procure clínicas em São Paulo')
    assert agent.runs.last().status == 'completed'


def response_connection():
    conn = Mock()
    conn.getresponse.return_value.status = 200
    conn.getresponse.return_value.getheader.return_value = None
    conn.getresponse.return_value.read.return_value = b'{}'
    return conn


def test_connection_recovers_without_restarting_application():
    conn, client = response_connection(), HttpClient(interval=0)
    with patch('utils.http_client.public_address', return_value='1.1.1.1'), patch('utils.http_client.PinnedHTTPS', return_value=conn):
        conn.request.side_effect = OSError('offline')
        with pytest.raises(FetchError):
            client.request('https://example.org', {'query': 'test'})
        conn.request.side_effect = None
        assert client.json('https://example.org', {'query': 'test'}) == {}


def test_rate_limit_can_recover_after_cooldown():
    conn, client = response_connection(), HttpClient(interval=0)
    with patch('utils.http_client.public_address', return_value='1.1.1.1'), patch('utils.http_client.PinnedHTTPS', return_value=conn), patch('utils.http_client.time.monotonic', return_value=100) as clock:
        conn.getresponse.return_value.status = 429
        with pytest.raises(FetchError):
            client.request('https://example.org', {})
        conn.getresponse.return_value.status = 200
        with pytest.raises(FetchError):
            client.request('https://example.org', {})
        assert conn.request.call_count == 1
        clock.return_value = 161
        assert client.json('https://example.org', {}) == {}


@pytest.mark.parametrize('ttl', ['nan', 'inf', '-1'])
def test_invalid_optional_settings_do_not_break_desktop(tmp_path, monkeypatch, ttl):
    monkeypatch.setenv('CACHE_TTL_HOURS', ttl)
    monkeypatch.setenv('TELEGRAM_ALLOWED_USER_IDS', '123,invalid')
    config = load_config(str(tmp_path / '.env'))
    assert config.cache_ttl_hours == 24 and config.telegram_allowed_ids == ()


def test_windows_bom_env_is_read(tmp_path, monkeypatch):
    monkeypatch.delenv('DEFAULT_REGION', raising=False)
    path = tmp_path / '.env'
    path.write_text('DEFAULT_REGION=Campinas', encoding='utf-8-sig')
    assert load_config(str(path)).default_region == 'Campinas'


@pytest.mark.parametrize('phrase', ['atualize a investigação da Oficina Silva',
    'atualizar pesquisa de Oficina Silva', 'pesquise novamente Oficina Silva'])
def test_refresh_command_matches_real_company(phrase):
    from core.command_router import route
    command = route(phrase)
    assert command.name == 'investigate' and command.refresh
    assert command.target == 'Oficina Silva'
