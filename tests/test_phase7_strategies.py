"""Synthetic profile/strategy fixtures; no provider calls or user database."""
from copy import deepcopy
import json
from unittest.mock import patch
import pytest
from analysis.commercial_profile import load,update,validate,DEFAULT_PATH
from analysis.strategies import plan
from analysis.qualification import evaluate
from core.command_router import parse_criteria
from core.config import Config
from tests.factories import build_agent
from database.models import CompanyProfile,Observation
from utils.timeutils import now_iso


@pytest.fixture
def config(tmp_path):
    path=tmp_path/'profile.json'
    path.write_text(DEFAULT_PATH.read_text(encoding='utf-8'),encoding='utf-8')
    return Config(database_path=str(tmp_path/'test.db'),commercial_profile_path=str(path),mock=True)


def fact(text):
    return Observation(text,'Fonte sintética','https://empresa.example/test',now_iso())


def test_profile_backward_compatible_edit_and_restart(config):
    previous=load(config)
    for field,values in [('services',['integrações']),('technologies',['Python']),('automation_processes',['pedidos']),
                         ('project_complexity',['pequena']),('interesting_traits',['múltiplas unidades'])]:
        update(config,field,values)
    agent=build_agent(config)
    try:
        assert load(config)['technologies']==['Python']
        assert load(config)['services']==['integrações']
        agent.handle('/strategies disable integration')
        assert agent.last_skill_result.success
        agent.handle('/profile json thresholds {"moderate": 45, "high": 80}')
        assert agent.last_skill_result.success
    finally: agent.db.close()
    agent=build_agent(config)
    try:
        assert not load(config)['strategies']['integration']['enabled']
        assert load(config)['thresholds']['high']==80
        agent.handle('/profile reset strategies')
        assert agent.last_skill_result.success
        assert load(config)['services']==['integrações']
        assert load(config)['strategies']['integration']['enabled']
        assert previous['services']!=load(config)['services']
    finally: agent.db.close()


def test_intent_preserved_and_broad_query_explained(config):
    update(config,'priority_segments',['clínica'])
    update(config,'priority_locations',['São Paulo'])
    profile=load(config)
    criteria,context=plan(profile,parse_criteria('empresas'),'empresas')
    assert criteria.segment=='clínica' and criteria.city=='São Paulo' and context['applied']
    criteria,context=plan(profile,parse_criteria('oficinas em Campinas'),'oficinas em Campinas')
    assert criteria.segment=='oficina' and criteria.city=='Campinas'
    criteria,_=plan(profile,parse_criteria('distribuidores em Recife'),'distribuidores em Recife')
    assert criteria.segment=='distribuidores' and criteria.city=='Recife'


def test_segment_rule_and_explicit_strategy(config):
    update(config,'segment_rules',{'clínica':{'strategy':'manual','signals':['scheduling'],'min_signals':1}})
    profile=load(config)
    _,context=plan(profile,parse_criteria('clínicas em São Paulo'),'clínicas em São Paulo')
    assert context['strategy_id']=='manual'
    _,context=plan(profile,parse_criteria('oficinas em Campinas'),'oficinas em Campinas',explicit='integration')
    assert context['strategy_id']=='integration'
    profile['strategies']['integration']['enabled']=False
    with pytest.raises(ValueError): plan(profile,parse_criteria('oficinas'),'oficinas',explicit='integration')


def test_tools_are_observed_and_need_is_only_hypothesis(config):
    update(config,'services',['integrações'])
    profile=load(config)
    company=CompanyProfile(name='Empresa sintética',segment='oficina',website='https://empresa.example')
    result=evaluate(company,[fact('Usamos Shopify e WhatsApp para pedidos.')],profile)
    assert result['recommendations']
    assert all(r['evidence_ids'] and r['services']==['integrações'] for r in result['recommendations'])
    assert all('não confirmados' in r['hypothesis'] for r in result['recommendations'])
    assert not evaluate(company,[fact('Site simples e antigo.')],profile)['recommendations']
    assert not evaluate(company,[fact('Não usamos Shopify ou WhatsApp.')],profile)['recommendations']
    assert not evaluate(company,[fact('Usamos Shopify para pedidos.')],profile)['recommendations']


def test_exclusions_and_minimum_evidence(config):
    profile=load(config)
    company=CompanyProfile(name='Sintética',segment='oficina')
    observations=[fact('Controle manual em planilhas. Temos 3 unidades.')]
    assert evaluate(company,observations,profile)['recommendations']
    profile['excluded_segments']=['oficina']
    result=evaluate(company,observations,profile)
    assert not result['recommendations'] and result['score']<profile['thresholds']['moderate']
    assert any('excluído' in r for r in result['negative_factors'])
    profile['excluded_segments']=[]
    profile['segment_rules']={'oficina':{'signals':['manual_process'],'min_signals':2}}
    assert not evaluate(company,observations,profile)['recommendations']


def test_search_profile_snapshot_cache_and_disabled_strategies(config):
    agent=build_agent(config)
    try:
        agent.handle('/search estratégia=manual oficinas em Campinas')
        assert agent.last_skill_result.success
        first=agent.db.query_one('SELECT id,strategy_json FROM research_runs ORDER BY id DESC LIMIT 1')
        snapshot=first['strategy_json']
        assert json.loads(snapshot)['strategy_id']=='manual'
        identity=agent.runs.company_ids(first['id'])[0]
        agent.handle('/stage '+identity+' negotiating')
        agent.handle('/note '+identity+' Nota sintética')
        agent.handle('/task '+identity+' 2026-10-30 Revisar')
        old=agent.db.query_one('SELECT COUNT(*) n FROM companies')['n']
        profile=load(config)
        for strategy in profile['strategies'].values(): strategy['enabled']=False
        update(config,'strategies',profile['strategies'])
        agent.handle('/search oficinas em Campinas')
        assert agent.last_skill_result.success and 'Exploratória' in agent.last_skill_result.message
        assert agent.db.query_one('SELECT COUNT(*) n FROM companies')['n']==old
        assert not agent.hypotheses.list_for_company(identity)
        assert agent.db.query_one('SELECT strategy_json FROM research_runs WHERE id=?',(first['id'],))[0]==snapshot
        assert agent.db.query_one('SELECT commercial_status,notes FROM companies WHERE id=?',(identity,))['notes']=='Nota sintética'
        assert agent.db.query_one('SELECT COUNT(*) n FROM lead_tasks')['n']==1
        assert 'manual' in agent.handle('/strategies run '+str(first['id']))
        before=agent.runs.count()
        agent.handle('/search estratégia=manual oficinas em Campinas')
        assert not agent.last_skill_result.success and agent.runs.count()==before
    finally: agent.db.close()
    agent=build_agent(config)
    try: assert agent.db.query_one('SELECT strategy_json FROM research_runs WHERE id=?',(first['id'],))[0]==snapshot
    finally: agent.db.close()


def test_incomplete_profile_does_not_invent_services(config):
    update(config,'services',[])
    agent=build_agent(config)
    try:
        agent.handle('/search oficinas em Campinas')
        assert agent.last_skill_result.success
        assert 'Exploratória' in agent.last_skill_result.message
        assert not agent.db.query('SELECT * FROM hypotheses')
    finally: agent.db.close()


def test_new_declarative_strategy_without_engine_change(config):
    profile=load(config)
    strategy=deepcopy(profile['strategies']['manual'])
    strategy.update(objective='Rotina específica',triggers=['estoque'],query_terms=['pedidos'],segments=['oficina'])
    profile['strategies']['inventory']=strategy
    update(config,'strategies',profile['strategies'])
    criteria,context=plan(load(config),parse_criteria('oficinas em Campinas'),'oficinas em Campinas',explicit='inventory')
    assert context['strategy_id']=='inventory' and criteria.need=='pedidos'


def test_invalid_configuration_is_atomic(config):
    before=open(config.commercial_profile_path,encoding='utf-8').read()
    with pytest.raises(ValueError): update(config,'weights',{'service_fit':100})
    assert open(config.commercial_profile_path,encoding='utf-8').read()==before
    invalid=load(config);invalid['strategies']['manual']['min_signals']=0
    with pytest.raises(ValueError): validate(invalid)


def test_strategy_minimum_does_not_block_other_qualified_strategy(config):
    profile=load(config)
    profile['strategies']['custom']['min_signals']=5
    result=evaluate(CompanyProfile(name='Teste'),[fact('Controle manual em planilhas.')],profile)
    assert any(r['solution']=='automação de processos internos' for r in result['recommendations'])


def test_profile_processes_only_guide_missing_goal(config):
    profile=load(config)
    profile['automation_processes']=['agendamento']
    _,context=plan(profile,parse_criteria('clínicas em Campinas'),'clínicas em Campinas')
    assert context['strategy_id']=='manual'
    _,context=plan(profile,parse_criteria('clínicas integração em Campinas'),'clínicas integração em Campinas')
    assert context['strategy_id']=='integration'


def test_unconfigured_source_and_invalid_profile_do_not_fetch(config):
    agent=build_agent(config)
    try:
        with open(config.commercial_profile_path,'w',encoding='utf-8') as file:file.write('{invalid')
        with patch.object(agent.finder,'find') as find:
            agent.handle('/search oficinas em Campinas')
            assert not agent.last_skill_result.success
            find.assert_not_called()
        assert agent.runs.count()==0
    finally:agent.db.close()
