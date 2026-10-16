"""Phase-three fixtures only: no real leads or external providers."""
import json
from unittest.mock import patch
import pytest
from analysis.commercial_profile import load, update, validate
from analysis.qualification import evaluate, public_url
from analysis.commercial import CommercialService, ai_prompt
from core.config import Config
from database.database import Database
from database.models import CompanyProfile, Observation
from database.repositories import CompanyRepository, SourceRepository
from database.leads import LeadRepository
from utils.timeutils import utcnow, now_iso


@pytest.fixture
def profile():
    return load(Config())


def observation(text='Controle manual em planilhas. Atendimento via WhatsApp. Temos 3 unidades.',date=None):
    return Observation(text,'Fonte de teste','https://empresa.example/processos',date or now_iso())


def seed(agent):
    company=CompanyProfile(name='Empresa de teste comercial',city='Campinas',segment='oficina')
    agent.companies.add(company)
    agent.sources.replace_for_company(company.id,[observation()])
    return company


def test_transparent_sum_and_evidence_links(profile):
    result=evaluate(CompanyProfile(name='Teste'),[observation()],profile)
    assert result['score']==75 and result['category']=='high'
    assert sum(f['points'] for f in result['factors'])+sum(a['points'] for a in result['adjustments'])==result['score']
    assert all(f['reason'] for f in result['factors'])
    assert result['facts'][0]['checked_at'] and result['facts'][0]['url']
    assert all(r['evidence_ids']==[1] and 'não confirmados' in r['hypothesis'] for r in result['recommendations'])
    assert result['gaps'] and result['next_action']


@pytest.mark.parametrize('high,moderate,expected',[(75,40,'high'),(76,75,'moderate'),(90,76,'low')])
def test_category_boundaries(profile,high,moderate,expected):
    profile['thresholds']={'high':high,'moderate':moderate}
    assert evaluate(CompanyProfile(name='Teste'),[observation()],profile)['category']==expected


@pytest.mark.parametrize('date',[None,'inválida','2000-01-01','2999-01-01'])
def test_missing_old_future_dates_never_inflate(profile,date):
    obs=observation();obs.retrieved_at=date
    result=evaluate(CompanyProfile(name='Teste'),[obs],profile)
    assert result['category']=='insufficient' and result['score']<40
    assert not result['recommendations']


def test_missing_site_and_generic_text_are_not_opportunity(profile):
    company=CompanyProfile(name='Teste',website=None)
    result=evaluate(company,[observation('Bem-vindo ao site da empresa.')],profile)
    assert result['category']=='low' and not result['recommendations']
    assert next(f for f in result['factors'] if f['criterion']=='digital_features')['points']==0


def test_unsuccessful_lookup_not_a_confirmed_feature_gap(profile):
    result=evaluate(CompanyProfile(name='Teste'),[observation('Site não identificado. Loja virtual não identificada.')],profile)
    assert result['category']=='low' and not result['recommendations']


def test_repeated_evidence_not_more_points(profile):
    company=CompanyProfile(name='Teste');obs=observation()
    assert evaluate(company,[obs],profile)['score']==evaluate(company,[obs]*10,profile)['score']


def test_no_opportunity_caps_preferences_and_explains_adjustment(profile):
    profile.update(priority_segments=['oficina'],priority_locations=['Campinas'],company_sizes=['pequena'])
    company=CompanyProfile(name='Teste',segment='oficina',city='Campinas',estimated_size='pequena',phone='19999998888')
    result=evaluate(company,[observation('Nosso telefone é (19) 99999-8888.')],profile)
    assert result['score']==39 and result['category']=='low'
    assert result['adjustments'][0]['points']==-1
    assert sum(f['points'] for f in result['factors'])+sum(a['points'] for a in result['adjustments'])==39


def test_services_exclusions_and_accepted_projects(profile):
    company=CompanyProfile(name='Teste')
    profile['services']=['e-commerce']
    assert not evaluate(company,[observation()],profile)['recommendations']
    profile['services']=['automação']
    profile['excluded_projects']=['WhatsApp']
    result=evaluate(company,[observation()],profile)
    assert result['recommendations'] and all('WhatsApp' not in r['solution'] for r in result['recommendations'])
    profile['accepted_projects']=['projeto que não aceitamos aqui']
    assert not evaluate(company,[observation()],profile)['recommendations']
    profile['services']=[]
    assert evaluate(company,[observation()],profile)['category']=='insufficient'


def test_existing_feature_reduces_hypotheses(profile):
    result=evaluate(CompanyProfile(name='Teste'),[observation('Agendamento por telefone. Oferece agendamento online.')],profile)
    assert not any('agendamento' in r['solution'] for r in result['recommendations'])
    assert result['negative_factors']


def test_profile_preferences_and_public_contact(profile):
    profile.update(priority_segments=['oficina'],priority_locations=['Campinas'],company_sizes=['pequena'])
    company=CompanyProfile(name='Teste',segment='oficina',city='Campinas',estimated_size='pequena',phone='19999998888')
    result=evaluate(company,[observation('Controle manual em planilhas. Atendimento via WhatsApp. Temos 3 unidades. Telefone (19) 99999-8888.')],profile)
    assert result['score']==100
    company.phone='11988887777'
    assert evaluate(company,[observation()],profile)['score']==95


@pytest.mark.parametrize('url',['http://127.0.0.1/a','http://192.168.1.10','file:///tmp/x','https://user:pass@example.com','http://localhost','http://host.local',''])
def test_nonpublic_urls_rejected(url):
    assert not public_url(url)


def test_profile_atomic_edit_and_invalid_weights(tmp_path,profile):
    path=tmp_path/'profile.json';path.write_text(json.dumps(profile),encoding='utf-8')
    config=Config(commercial_profile_path=str(path))
    update(config,'technologies',['Python'])
    assert load(config)['technologies']==['Python']
    before=path.read_bytes()
    with pytest.raises(ValueError): update(config,'services',[''])
    assert path.read_bytes()==before
    profile['weights']['evidence']=99
    with pytest.raises(ValueError):validate(profile)


def test_restart_cache_recalculation_and_history(tmp_path):
    path=str(tmp_path/'test.db');cfg=Config(database_path=path)
    db=Database(path)
    company=CompanyProfile(name='Teste persistência')
    CompanyRepository(db).add(company)
    SourceRepository(db).replace_for_company(company.id,[observation()])
    service=CommercialService(db,cfg)
    first=service.qualify(company.id)
    assert service.qualify(company.id)['id']==first['id']
    second=service.qualify(company.id,True)
    assert second['id']!=first['id']
    SourceRepository(db).replace_for_company(company.id,[observation('Apenas informação institucional.')])
    assert service.qualify(company.id)['category']=='low'
    assert service.history(company.id)[-1]['facts']==first['facts']
    assert LeadRepository(db).resolve(company.id)['commercial_status']=='new'
    db.close();db=Database(path)
    assert len(CommercialService(db,cfg).history(company.id))==3
    db.close()


def test_profile_change_invalidates_cache(agent,tmp_path,profile):
    path=tmp_path/'profile.json';path.write_text(json.dumps(profile),encoding='utf-8')
    agent.config.commercial_profile_path=str(path)
    company=seed(agent);service=CommercialService(agent.db,agent.config)
    before=service.qualify(company.id)
    update(agent.config,'services',[])
    after=service.qualify(company.id)
    assert after['id']!=before['id'] and after['category']=='insufficient'


@pytest.mark.parametrize('format',['email','message','call'])
def test_drafts_are_personalized_preview_only_then_explicit_save(agent,format):
    company=seed(agent)
    text=agent.handle('/draft '+company.id+' '+format)
    assert company.name in text and 'Controle manual' in text and 'Nenhuma mensagem enviada' in text
    assert agent.db.query_one('SELECT COUNT(*) n FROM commercial_drafts')['n']==0
    assert 'Rascunho salvo' in agent.handle('/draft-save')
    assert agent.db.query_one('SELECT COUNT(*) n FROM commercial_drafts')['n']==1
    assert company.name in agent.handle('/drafts '+company.id)


def test_stale_draft_cannot_be_saved(agent):
    company=seed(agent)
    agent.handle('/draft '+company.id+' email')
    agent.sources.replace_for_company(company.id,[observation('Nova informação sem oportunidade.')])
    assert 'mudaram' in agent.handle('/draft-save')
    assert not agent.db.query('SELECT * FROM commercial_drafts')


def test_no_opportunity_or_archived_no_outreach(agent):
    company=seed(agent)
    agent.sources.replace_for_company(company.id,[])
    assert 'insuficientes' in agent.handle('/draft '+company.id+' email')
    LeadRepository(agent.db).archive(company.id)
    assert 'arquivado' in agent.handle('/draft '+company.id+' email')


def test_optional_ai_never_auto_sends_and_excludes_private_notes(agent):
    company=seed(agent)
    LeadRepository(agent.db).edit(company.id,'notes','PRIVATE-NOTE-SECRET')
    with patch('integrations.layla.bridge.LaylaBridge.send',side_effect=AssertionError('must not send')):
        assert 'Qualificação:' in agent.handle('/qualify '+company.id)
        text=agent.handle('/qualify-ai '+company.id+' summary')
        assert 'Revise' in text and 'pagos' in text
        assert 'PRIVATE-NOTE-SECRET' not in text
        assert agent.last_skill_result.data['action']=='open_ai'
        assert len(agent.last_skill_result.data['draft'])<=2000
        assert not agent.db.query('SELECT * FROM commercial_drafts')


def test_ai_payload_redacts_contacts(profile):
    result=evaluate(CompanyProfile(name='Teste'),[observation('Atendimento via WhatsApp (19) 99999-8888 ou a@empresa.example')],profile)
    prompt=ai_prompt(result,'summary')
    assert '99999' not in prompt and 'a@empresa' not in prompt


def test_auto_research_and_export_evaluations(agent,tmp_path):
    agent.handle('/search oficinas em Campinas')
    rows=agent.db.query('SELECT * FROM lead_evaluations')
    assert rows
    identity=rows[0]['company_id']
    assert 'Qualificação:' in agent.handle('/qualify '+identity)
    assert 'Histórico imutável' in agent.handle('/evaluations '+identity)
    file=LeadRepository(agent.db).export('json',[identity],tmp_path)
    data=json.loads(file.read_text(encoding='utf-8'))[0]
    assert data['evaluations'][0]['profile'] and data['score'] is not None


def test_v1_to_v2_preserves_data_and_backs_up(tmp_path):
    from unittest.mock import patch
    # Build an actual old schema; do not downgrade a new database by deleting
    # version markers while leaving later tables and columns behind.
    with patch('database.migrations._v2'), patch('database.migrations._v3'), patch('database.migrations._v4'):
        path=str(tmp_path/'v1.db');db=Database(path)
        company=CompanyProfile(name='Teste migração');CompanyRepository(db).add(company)
        db.close()
    db=Database(path)
    assert CompanyRepository(db).get(company.id).name==company.name
    assert not db.query('SELECT * FROM lead_evaluations')
    assert len(list((tmp_path/'backups').glob('*.db')))==1
    assert db.query_one('PRAGMA integrity_check')[0]=='ok'
    db.close()
