import json
import sqlite3
from unittest.mock import Mock, patch

import pytest

from analysis.opportunity_analyzer import OpportunityAnalyzer
from analysis.scoring import opportunity_score
from tests.factories import build_agent
from core.config import Config
from core.memory import Memory
from database.database import Database
from database.models import CompanyProfile, Signal, SearchCriteria
from notifications.telegram import TelegramAPI, TelegramBot
from research.web_source import WebSource, TavilySearch
from research.base import SearchResult
from utils.http_client import HttpClient, FetchError, public_address


def test_backup_restores_real_sqlite(tmp_path):
    db = Database(str(tmp_path / 'source.db'))
    db.execute("INSERT INTO settings VALUES ('region', 'Campinas', 'today')")
    backup = db.backup()
    with sqlite3.connect(backup) as restored:
        assert restored.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert restored.execute('SELECT value FROM settings').fetchone()[0] == 'Campinas'
    db.close()


def test_context_separated_by_user():
    db = Database(':memory:')
    one, two = Memory(db, '1:'), Memory(db, '2:')
    one.set_last_company('a')
    assert two.last_company_id() is None
    two.set_last_company('b')
    assert one.last_company_id() == 'a'


def test_no_evidence_no_hypothesis_or_priority():
    signal = Signal('scheduling', 'd', 'e', 's', 'today', 'high')
    assert opportunity_score([signal]) == 0
    assert OpportunityAnalyzer(['sistemas web']).analyze(CompanyProfile('X'), [signal]) == []
    signal.source_url = 'https://example.org'
    assert opportunity_score([signal] * 20) == opportunity_score([signal]) == 25


def update(uid=1, chat_type='private', text='/status'):
    return {'message': {'from': {'id': uid}, 'chat': {'id': uid, 'type': chat_type}, 'text': text}}


def test_telegram_denies_before_factory_and_limits_rate():
    api, factory = Mock(), Mock()
    factory.return_value.handle.return_value = 'ok'
    bot = TelegramBot(api, [1], factory)
    assert not bot.process(update(2))
    assert not bot.process(update(1, 'group'))
    factory.assert_not_called()
    api.send.assert_not_called()
    assert bot.process(update())
    assert not bot.process(update())
    factory.assert_called_once_with(1)


def test_allowlist_required_and_telegram_chunking():
    with pytest.raises(ValueError):
        TelegramBot(Mock(), [], Mock())
    client = Mock()
    client.json.return_value = {'ok': True, 'result': {}}
    TelegramAPI('123:token', client).send(1, 'a' * 5000)
    assert client.json.call_count == 3


def test_mock_never_builds_network_providers():
    with patch('research.web_source.TavilySearch', side_effect=AssertionError('network')):
        agent = build_agent(Config(mock=True, database_path=':memory:', search_api_key='secret'))
        assert 'mock' in agent.handle('/status')
        assert 'desativada' in agent.handle('/ollama X')


def test_public_address_rejects_private_and_mixed_dns():
    with patch('socket.getaddrinfo', return_value=[(2, 1, 6, '', ('127.0.0.1', 443))]):
        with pytest.raises(FetchError):
            public_address('local.test')
    for url in ('http://example.org', 'https://user:password@example.org', 'https://example.org:8443'):
        with pytest.raises(FetchError):
            HttpClient().request(url)


def test_429_stops_without_retry_and_blocks_next_call():
    conn = Mock()
    conn.getresponse.return_value.status = 429
    client = HttpClient(interval=0)
    with patch('utils.http_client.public_address', return_value='1.1.1.1'), patch('utils.http_client.PinnedHTTPS', return_value=conn):
        for _ in range(2):
            with pytest.raises(FetchError):
                client.request('https://example.org/')
    assert conn.request.call_count == 1


def test_web_does_not_invent_companies_from_snippets():
    provider, client = Mock(), Mock()
    client.interval = 0
    provider.search.return_value = [SearchResult('10 melhores clínicas', 'https://example.org/', 'três unidades')]
    client.request.side_effect = ['User-agent: *\nAllow: /', '<h1>Listagem de clínicas</h1>']
    assert WebSource(provider, client).search(SearchCriteria(city='Campinas')) == []


def test_web_extracts_attributed_company_and_respects_robots():
    provider, client = Mock(), Mock()
    client.interval = 0
    provider.search.return_value = [SearchResult('Clínica', 'https://example.org/')]
    item = {'@type': 'Dentist', 'name': 'Clínica X', 'url': 'https://example.org/',
            'address': {'addressLocality': 'Campinas'}}
    client.request.side_effect = ['User-agent: *\nAllow: /', '<script type="application/ld+json">' + json.dumps(item) + '</script>']
    result = WebSource(provider, client).search(SearchCriteria(city='Campinas'))
    assert result[0].city == 'Campinas' and result[0].observations[0].retrieved_at
    client.request.side_effect = ['User-agent: *\nDisallow: /']
    source = WebSource(provider, client)
    assert source.search(SearchCriteria()) == []
    assert 'robots.txt' in source.last_hits[0]['reason']


def test_tavily_limits_results_and_keeps_key_in_header():
    client = Mock()
    client.json.return_value = {'results': [{'title': 'X', 'url': 'https://example.org'}]}
    assert TavilySearch('secret', client=client).search('clínicas')[0].title == 'X'
    args, kwargs = client.json.call_args
    assert 'secret' not in args[0]
    assert kwargs['headers']['Authorization'] == 'Bearer secret'
    assert kwargs['payload']['search_depth'] == 'basic'
    assert kwargs['payload']['auto_parameters'] is False
    assert kwargs['payload']['include_answer'] is False


def test_explicit_negation_does_not_become_positive_signal():
    from analysis.signal_detector import SignalDetector
    from database.models import Observation
    signals = SignalDetector().detect(CompanyProfile('X', website='https://example.org'),
        [Observation('Não temos duas unidades.', 'site', 'https://example.org'),
         Observation('Não usamos planilhas.', 'site', 'https://example.org')])
    assert signals == []


def test_ollama_uses_bounded_evidence_and_has_no_database_access():
    from analysis.ai_provider import OllamaProvider
    from database.models import Observation
    conn = Mock()
    conn.getresponse.return_value.status = 200
    conn.getresponse.return_value.read.side_effect = [b'{"details":{"family":"test"}}', b'{"done":true,"done_reason":"stop","message":{"content":"Resumo"}}']
    with patch('analysis.ai_provider.http.client.HTTPConnection', return_value=conn):
        assert OllamaProvider('local').summarize([Observation('x' * 900, 'site', 'https://example.org')] * 20) == 'Resumo'
    payload = json.loads(conn.request.call_args.args[2])
    evidence = json.loads(payload['messages'][1]['content'])
    assert len(evidence) == 8 and len(evidence[0]['text']) == 600
    assert conn.close.call_count == 2


def test_http_get_retries_are_bounded_and_post_is_not_retried():
    conn = Mock()
    conn.request.side_effect = OSError('offline')
    with patch('utils.http_client.public_address', return_value='1.1.1.1'), patch('utils.http_client.PinnedHTTPS', return_value=conn), patch('utils.http_client.time.sleep'):
        with pytest.raises(FetchError):
            HttpClient(interval=0).request('https://example.org/')
        assert conn.request.call_count == 3
        conn.reset_mock()
        with pytest.raises(FetchError):
            HttpClient(interval=0).request('https://example.org/', {'text': 'message'})
        assert conn.request.call_count == 1
