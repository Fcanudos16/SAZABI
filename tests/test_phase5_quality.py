"""Synthetic regressions derived from phase-five observations; no network."""
from unittest.mock import Mock, patch
import sqlite3
import pytest

from core.config import Config
from core.bootstrap import build_agent
from research.web_source import WebSource, TavilySearch, PageParser, city_key
from research.base import SearchResult
from utils.http_client import FetchError
from database.models import CompanyProfile, Observation
from analysis.qualification import evaluate
from analysis.commercial_profile import load
from analysis.signal_detector import SignalDetector
from utils.timeutils import now_iso


def page(documents=None, text=None, meta=None):
    result = PageParser()
    result.url = 'https://fixture.example/'
    result.title = 'Empresa de teste'
    result.documents = documents or []
    result.text = text or []
    result.meta = meta or {}
    return result


@pytest.mark.parametrize('city', ['São Paulo', 'São Paulo/SP', 'São Paulo, Brasil', 'São Paulo, capital'])
def test_city_label_normalizes_only_explicit_suffixes(city):
    assert city_key(city) == 'sao paulo'
    assert city_key('São Paulo de Olivença') != city_key(city)


def test_editorial_publisher_is_not_a_prospect():
    source = WebSource(None)
    assert source.extract(page([{'@type':'NewsArticle'}], ['Jornal de teste'], {'og:site_name':'Jornal de teste'})) is None
    assert 'editorial' in source.extraction_reason


def test_brand_containing_city_is_not_location_evidence():
    source = WebSource(None)
    data = page([{'@type':'Organization','name':'São Paulo de teste','url':'https://fixture.example/'}],
                ['São Paulo de teste', 'Lisboa, Portugal'], {'og:site_name':'São Paulo de teste'})
    assert source.extract(data, 'São Paulo, capital') is None


def test_local_branch_wins_over_generic_organization():
    source = WebSource(None)
    data = page([{'@type':'Organization','name':'Marca teste','url':'https://fixture.example/'},
                 {'@type':'AutoRepair','name':'Oficina teste','url':'https://fixture.example/',
                  'address':{'addressLocality':'São Paulo/SP','addressRegion':'SP'}}])
    company = source.extract(data,'São Paulo, capital')
    assert company.name == 'Oficina teste' and company.city == 'São Paulo/SP'
    assert company.segment == 'oficina'
    assert company.observations[0].url == data.url


def test_missing_location_does_not_become_requested_city():
    source = WebSource(None)
    data = page(text=['Empresa de teste'],meta={'og:site_name':'Empresa de teste'})
    assert source.extract(data).city is None
    assert source.extract(data,'Campinas') is None


def test_page_failure_is_partial_and_empty_query_is_completed():
    for hits, expected in [([], 'completed'), ([SearchResult('Teste','https://fixture.example/','')],'partial')]:
        source = WebSource(TavilySearch('test-key'))
        agent = build_agent(Config(database_path=':memory:',search_api_key='test-key'),sources=[source])
        try:
            with patch.object(source.provider,'search',return_value=hits), patch.object(source,'page',side_effect=FetchError('Fonte indisponível',503)):
                agent.handle('/search oficinas em Campinas')
            assert agent.runs.last().status == expected
            assert agent.last_skill_result.status == expected
            assert len(agent.db.query('SELECT * FROM discovery_results')) == len(hits)
        finally:
            agent.db.close()


@pytest.mark.parametrize('response',[{'results':[None]}, {'results':[{'title':'x','url':12}]},
                                    {'results':[{'title':'x','url':'https://fixture.example','content':{}}]},
                                    {'results':{}}, {'results':[{'title':' ','url':'https://fixture.example'}]}])
def test_malformed_provider_response_not_empty_success(response):
    client = Mock(); client.json.return_value=response
    with pytest.raises(FetchError):
        TavilySearch('test-key',client=client).search('test')


def test_mixed_provider_response_exposes_discarded_record():
    client=Mock();client.json.return_value={'results':[None,{'title':'Teste','url':'https://fixture.example'}]}
    provider=TavilySearch('test-key',client=client)
    assert len(provider.search('test'))==1 and provider.errors


def test_existing_online_scheduling_suppresses_contradictory_recommendation():
    obs=Observation('Sistema de agendamento online, via Telefone ou WhatsApp.','Fonte de teste','https://fixture.example',now_iso())
    company=CompanyProfile(name='Teste')
    assert not any(s.type=='scheduling' for s in SignalDetector().detect(company,[obs]))
    result=evaluate(company,[obs],load(Config()))
    assert not result['recommendations']
    assert any('agendamento online existente' in line for line in result['negative_factors'])


def test_generic_hiring_link_and_historical_opening_do_not_score():
    observations=[Observation('Trabalhe conosco','Teste'),Observation('Inauguração da centésima loja.','Teste')]
    assert not SignalDetector().detect(CompanyProfile(name='Teste',website='https://fixture.example'),observations)


def test_database_failure_does_not_report_completed(agent):
    with patch.object(agent.runs,'create',side_effect=sqlite3.OperationalError('readonly database')):
        reply=agent.handle('/search oficinas em Campinas')
    assert not agent.last_skill_result.success
    assert agent.last_skill_result.status=='failed'
    assert 'Pesquisa concluída' not in reply
    assert agent.runs.count()==0


def test_rate_limit_is_failed_not_zero_results():
    source=WebSource(TavilySearch('test-key'))
    agent=build_agent(Config(database_path=':memory:',search_api_key='test-key'),sources=[source])
    try:
        with patch.object(source.provider,'search',side_effect=FetchError('Limite de requisições',429)):
            agent.handle('/search oficinas em Campinas')
        assert agent.runs.last().status=='failed' and not agent.last_skill_result.success
    finally:
        agent.db.close()


def test_query_preserves_city_and_disambiguates_workshop():
    from database.models import SearchCriteria
    provider = Mock()
    provider.search.return_value = []
    WebSource(provider).search(SearchCriteria(segment='oficina', city='São Paulo, capital'))
    query = provider.search.call_args.args[0]
    assert 'oficinas mecânicas' in query and '"São Paulo"' in query
    assert 'Brasil' not in query


def test_unavailable_optional_page_preserves_main_evidence():
    source = WebSource(None)
    main = page(text=['Empresa de teste oferece serviços automotivos.'])
    main.links = ['/contato']
    with patch.object(source, 'page', side_effect=[main, FetchError('Fonte indisponível', 503)]):
        observations = source.fetch_observations(CompanyProfile(name='Teste', website=main.url))
    assert observations and observations[0].url == main.url
    assert len(source.errors) == 1 and '/contato' in source.errors[0]
