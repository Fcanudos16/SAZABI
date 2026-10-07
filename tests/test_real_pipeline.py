import gzip
from unittest.mock import Mock, patch

import pytest

from core.bootstrap import build_agent
from core.config import Config, load_config
from core.connection import connect
from database.models import SearchCriteria
from research.base import SearchResult
from research.web_source import WebSource
from utils.http_client import HttpClient, FetchError


def test_http_gzip_is_decoded_and_expansion_bounded():
    conn = Mock()
    response = conn.getresponse.return_value
    response.status = 200
    response.getheader.side_effect = lambda name: {'Content-Encoding': 'gzip', 'Content-Type': 'text/html; charset=utf-8'}.get(name)
    response.read.return_value = gzip.compress('<h1>Saúde</h1>'.encode())
    with patch('utils.http_client.public_address', return_value='1.1.1.1'), patch('utils.http_client.PinnedHTTPS', return_value=conn):
        assert 'Saúde' in HttpClient(interval=0).request('https://example.org')
        response.read.return_value = gzip.compress(b'a' * 5000)
        with pytest.raises(FetchError, match='descompactada'):
            HttpClient(interval=0, max_bytes=100).request('https://example.org')


def test_missing_robots_redirect_and_declared_identity():
    client = Mock()
    client.request.side_effect = [FetchError('404', status=404), FetchError('redirect', status=301, location='https://www.example.org/'),
        'User-agent: *\nAllow: /', '<meta property="og:site_name" content="Empresa Teste"><h1>Empresa Teste</h1>']
    source = WebSource(None, client)
    page = source.page('https://example.org')
    company = source.extract(page)
    assert company.name == 'Empresa Teste'
    assert company.website == 'https://www.example.org/'
    assert company.city is None and company.segment is None
    assert company.observations[0].url == page.url


def test_pending_real_hits_survive_restart_without_fake_companies(tmp_path):
    provider, client = Mock(), Mock()
    provider.search.return_value = [SearchResult('Página da busca', 'https://example.org/', 'Texto da fonte')]
    client.request.side_effect = FetchError('Acesso recusado', status=403)
    config = Config(database_path=str(tmp_path / 'actual.db'))
    agent = build_agent(config, sources=[WebSource(provider, client)])
    reply = agent.handle('/search petshops em Campinas')
    assert 'pendentes de identificação' in reply and 'https://example.org/' in reply
    assert agent.companies.count() == 0
    assert 'petshops' in provider.search.call_args.args[0]
    agent.db.close()
    reopened = build_agent(config)
    try:
        assert 'Texto da fonte' in reopened.handle('/results')
        assert reopened.companies.count() == 0
    finally:
        reopened.db.close()


def test_bad_key_records_failure_not_success():
    provider = Mock()
    provider.search.side_effect = FetchError('Chave API inválida', status=401)
    agent = build_agent(Config(database_path=':memory:'), sources=[WebSource(provider)])
    try:
        assert 'Pesquisa não concluída' in agent.handle('/search clínicas em Campinas')
        assert agent.runs.last().status == 'failed'
        assert 'Chave API inválida' in agent.handle('/history')
        assert agent.companies.count() == 0
    finally:
        agent.db.close()


def test_connect_saves_key_without_history_and_reuses_database(tmp_path, monkeypatch):
    monkeypatch.delenv('SEARCH_API_KEY', raising=False)
    path = tmp_path / '.env'
    path.write_text('DEFAULT_REGION=Campinas\nSEARCH_API_KEY=old\n', encoding='utf-8')
    config = Config(env_file=str(path), database_path=':memory:')
    agent = build_agent(config)
    try:
        with patch('core.connection.TavilySearch') as provider:
            provider.return_value.check_connection.return_value = {'usage': 0, 'limit': 1000}
            connect(agent, 'tvly-test-private-key')
        assert load_config(str(path)).search_api_key == 'tvly-test-private-key'
        assert 'DEFAULT_REGION=Campinas' in path.read_text(encoding='utf-8')
        assert len(agent.finder.sources) == 1 and agent.finder.sources == agent.investigator.sources
        assert agent.db.query('SELECT * FROM conversation_history') == []
        assert 'campo protegido' in agent.handle('tvly-test-private-key')
        assert agent.db.query('SELECT * FROM conversation_history') == []
    finally:
        monkeypatch.delenv('SEARCH_API_KEY', raising=False)
        agent.db.close()


def test_failed_connection_preserves_previous_key(tmp_path):
    path = tmp_path / '.env'
    path.write_text('SEARCH_API_KEY=old\n', encoding='utf-8')
    agent = build_agent(Config(env_file=str(path), database_path=':memory:'))
    try:
        with patch('core.connection.TavilySearch') as provider:
            provider.return_value.check_connection.side_effect = FetchError('Chave inválida', status=401)
            with pytest.raises(FetchError):
                connect(agent, 'tvly-invalid-test-key')
        assert path.read_text(encoding='utf-8') == 'SEARCH_API_KEY=old\n'
        assert not agent.finder.sources
    finally:
        agent.db.close()


def test_production_never_loads_test_data():
    agent = build_agent(Config(database_path=':memory:'))
    try:
        assert not agent.finder.sources
        assert agent.companies.count() == 0
        assert 'Pesquisa não iniciada' in agent.handle('/search clínicas em Campinas')
        assert agent.runs.count() == 0
    finally:
        agent.db.close()


def test_production_pipeline_uses_attributed_web_evidence_and_persists(tmp_path):
    import json
    provider, client = Mock(), Mock()
    provider.search.return_value = [SearchResult('Empresa Teste', 'https://example.org/')]
    document = {'@type': 'LocalBusiness', 'name': 'Empresa Teste', 'url': 'https://example.org/',
                'address': {'addressLocality': 'Campinas'}}
    client.request.side_effect = ['User-agent: *\nAllow: /',
        '<script type="application/ld+json">' + json.dumps(document) + '</script><p>Temos três unidades em Campinas.</p>']
    config = Config(database_path=str(tmp_path / 'pipeline.db'))
    agent = build_agent(config, sources=[WebSource(provider, client)])
    try:
        report = agent.handle('/search empresas em Campinas')
        assert 'Empresa Teste' in report and 'https://example.org/' in report
        profile = agent.companies.search_by_name('Empresa Teste')[0]
        assert profile.city == 'Campinas' and profile.segment is None
        assert agent.signals.list_for_company(profile.id)[0].source_url == 'https://example.org/'
        assert agent.runs.last().status == 'completed'
    finally:
        agent.db.close()
    reopened = build_agent(config)
    try:
        assert 'Empresa Teste' in reopened.handle('/results')
        assert 'Temos três unidades' in reopened.handle('/company Empresa Teste')
    finally:
        reopened.db.close()


def test_cli_without_key_from_another_directory_is_real_and_persistent(tmp_path, monkeypatch):
    import subprocess
    import sys
    from pathlib import Path
    monkeypatch.delenv('SEARCH_API_KEY', raising=False)
    entry = str(Path(__file__).resolve().parents[1] / 'main.py')
    def run(command):
        completed = subprocess.run([sys.executable, entry, '--env', str(tmp_path / '.env'),
            '--db', str(tmp_path / 'cli.db'), '-c', command], cwd=tmp_path,
            capture_output=True, encoding='utf-8', timeout=30)
        assert completed.returncode == 0, completed.stderr
        return completed.stdout
    assert 'definida' in run('/set region Campinas')
    assert 'Campinas' in run('/status')
    assert 'Pesquisa não iniciada' in run('/search clínicas em Campinas')
    assert 'Pesquisas realizadas: 0' in run('/status')
