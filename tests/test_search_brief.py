"""Synthetic companies only; no provider calls or production database writes."""
import json
from unittest.mock import patch
import pytest
from analysis.search_brief import build_brief, qualification_gaps, detail_text
from analysis.qualification import evaluate
from analysis.commercial_profile import load
from core.config import Config
from database.models import CompanyProfile, Observation, SearchCriteria
from utils.timeutils import now_iso


def brief(text, services=None, name='Empresa Teste', extra=()):
    company=CompanyProfile(id='teste',name=name,website='https://empresa.example',city='Campinas',segment='oficina')
    profile=load(Config())
    if services is not None: profile['services']=services
    observations=[Observation(text,'Site público','https://empresa.example/processos',now_iso()),*extra]
    return build_brief(company,evaluate(company,observations,profile))


def test_documented_need():
    result=brief('Precisamos automatizar o controle manual de pedidos.')
    assert result['situation']=='Necessidade identificada'
    assert result['score']==90 and result['priority']=='Alta'
    assert result['evidence'][0]['strength']=='Direta'
    assert result['solution']=='automação de processos internos'
    assert result['outreach'] and 'Empresa Teste' in result['outreach']


def test_indirect_manual_process():
    result=brief('Utilizamos planilhas para controle manual de pedidos.')
    assert result['situation']=='Oportunidade provável'
    assert result['score']==64
    assert result['signals'][0]['evidence_ids']==[1]
    assert 'pode se beneficiar' in result['summary']


def test_job_is_not_external_purchase_intention():
    result=brief('Vaga para desenvolver integrações entre sistemas.', ['integrações'])
    assert result['situation']=='Oportunidade provável'
    assert 'Vaga não é pedido' in result['evidence'][0]['limitation']
    assert result['priority']!='Alta'


@pytest.mark.parametrize('text',['Bem-vindos ao nosso site.', 'Não precisamos automatizar o controle manual.',
                                'Site não identificado. Loja virtual não identificada.'])
def test_missing_or_negative_information(text):
    result=brief(text)
    assert result['priority']=='Baixa' and not result['outreach']
    assert result['situation']=='Hipótese de prospecção'


def test_duplicate_claims_do_not_raise_priority():
    text='Utilizamos planilhas para controle manual de pedidos.'
    single=brief(text)
    repeated=brief(text,extra=[Observation(text,'Reprodução','https://outra.example/noticia',now_iso())])
    assert single['score']==repeated['score'] and len(repeated['evidence'])==1


def test_score_reproducible_and_fit_required():
    result=brief('Precisamos automatizar o controle manual de pedidos.')
    assert sum(f['maximum'] for f in result['factors'])==100
    assert sum(f['points'] for f in result['factors'])+result['adjustment']==result['score']
    incompatible=brief('Precisamos automatizar o controle manual de pedidos.', ['e-commerce'])
    assert not incompatible['solution'] and incompatible['score']==0


def test_filters_do_not_qualify_unknown_or_wrong_region():
    company=CompanyProfile(name='Teste',website='https://teste.example',city='Curitiba')
    assert qualification_gaps(company,SearchCriteria(city='Campinas'))
    assert qualification_gaps(company,SearchCriteria(segment='clínica',size='pequena'))


def test_requested_need_must_match_investigation():
    from analysis.search_brief import matches_need
    result=brief('Vaga para desenvolver integrações entre sistemas.', ['integrações'])
    assert not matches_need('processos manuais',result)
    assert matches_need('software/sistemas',result)


@pytest.mark.parametrize('host',['pt.wikipedia.org','prefeitura.gov.br'])
def test_noncommercial_pages_not_company(host):
    from research.web_source import WebSource, PageParser
    from unittest.mock import Mock
    page=PageParser();page.url='https://'+host
    page.meta={'og:site_name':'Instituição'};page.text=['Instituição']
    assert WebSource(Mock()).extract(page) is None


def test_multiple_companies_persistence_and_history(agent):
    agent.handle('/search clínicas em São Paulo')
    result=agent.last_skill_result.data
    assert len(result['opportunities'])==2
    for card in result['opportunities']:
        row=agent.db.query_one('SELECT result_json FROM lead_evaluations WHERE company_id=?',(card['company_id'],))
        assert json.loads(row['result_json'])['search_brief']['name']==card['name']
        assert card['name'] in agent.handle('/lead '+card['company_id'])
    assert agent.handle('/history')


def test_analysis_failure_keeps_collected_results(agent):
    with patch('analysis.search_brief.build_brief',side_effect=RuntimeError('test failure')):
        agent.handle('/search clínicas em São Paulo')
    result=agent.last_skill_result
    assert result.status=='partial'
    assert result.data['companies'] and not result.data['opportunities']
    assert result.data['pending_companies']


def test_failed_repeat_does_not_present_stale_evaluation(agent):
    agent.handle('/search clínicas em São Paulo')
    from research.company_investigator import InvestigationResult
    with patch.object(agent.investigator,'investigate',return_value=InvestigationResult([],False,True)):
        agent.handle('/search clínicas em São Paulo')
    assert not agent.last_skill_result.data['opportunities']


def test_no_qualified_results(agent):
    agent.handle('/search clínicas em Cidade Inexistente')
    assert 'Nenhuma empresa qualificada' in agent.last_skill_result.message
    assert not agent.last_skill_result.data['opportunities']


def test_detail_separates_fact_and_interpretation():
    result=brief('Utilizamos planilhas para controle manual de pedidos.')
    text=detail_text(result)
    assert 'Como iniciar o contato' in text and 'publicação: não informada' in text
    assert result['evidence'][0]['url'] in text


def test_partial_state_is_persisted_and_does_not_leak_to_next_company(agent):
    original=agent.investigator.investigate
    calls=[]
    def investigate(*args, **kwargs):
        result=original(*args, **kwargs)
        if not calls: agent.investigator.errors.append('Página de vagas indisponível (teste).')
        calls.append(1)
        return result
    with patch.object(agent.investigator,'investigate',side_effect=investigate):
        agent.handle('/search clínicas em São Paulo')
    cards=agent.last_skill_result.data['opportunities']
    assert agent.last_skill_result.status=='partial'
    assert sum(c['investigation_state']=='partial' for c in cards)==1
    card=next(c for c in cards if c['investigation_state']=='partial')
    row=agent.db.query_one('SELECT result_json FROM lead_evaluations WHERE company_id=? ORDER BY id DESC LIMIT 1',(card['company_id'],))
    assert json.loads(row['result_json'])['search_brief']['investigation_state']=='partial'


def test_investigation_prioritizes_relevant_internal_pages_without_extra_search():
    from research.web_source import WebSource, PageParser
    from unittest.mock import Mock
    page=PageParser();page.url='https://empresa.example'
    page.links=['/sobre','/contato','/vagas/integracoes','/servicos','https://externo.example/vagas']
    source=WebSource(Mock())
    def fetched(url):
        if url==page.url: return page
        result=PageParser();result.url=url;result.text=['Utilizamos planilhas para controle manual.']
        return result
    with patch.object(source,'page',side_effect=fetched) as fetch:
        observations=source.fetch_observations(CompanyProfile(name='Empresa',website=page.url))
    assert fetch.call_count==3
    assert fetch.call_args_list[1].args[0].endswith('/vagas/integracoes')
    assert observations and not source.provider.search.called
