"""Phase-two storage tests; all databases and company data are isolated fixtures."""
import csv
import json
import sqlite3
from unittest.mock import patch
import pytest
from core.config import Config
from tests.factories import build_agent
from database.database import Database, SCHEMA
from database.models import CompanyProfile, Observation
from database.repositories import CompanyRepository, SourceRepository
from database.leads import LeadRepository


def test_restart_keeps_lead_stages_notes_sources_and_run(tmp_path):
    cfg=Config(database_path=str(tmp_path/'test.db'),mock=True)
    agent=build_agent(cfg)
    agent.handle('/search oficinas em Campinas')
    company=agent.companies.search_by_name('Oficina Delta')[0]
    identity=company.id
    assert agent.last_skill_result.success
    assert 'atualizado' in agent.handle('/stage '+identity+' negotiating')
    agent.handle('/note '+identity+' Próxima conversa na sexta')
    agent.handle('/edit '+identity+' phone (19) 9999-0000')
    agent.handle('/action '+identity+' response Resposta recebida pelo usuário')
    agent.db.close()
    agent=build_agent(cfg)
    try:
        leads=LeadRepository(agent.db)
        detail=leads.detail(identity)
        assert detail['commercial_status']=='negotiating'
        assert detail['notes']=='Próxima conversa na sexta'
        assert detail['phone']=='(19) 9999-0000'
        assert detail['research_runs'] and detail['sources']
        assert any(e['kind']=='response' for e in detail['events'])
        count=agent.companies.count()
        agent.handle('/search oficinas em Campinas')
        after=leads.detail(identity)
        assert agent.companies.count()==count
        assert after['commercial_status']=='negotiating' and after['notes']==detail['notes']
        assert after['phone']==detail['phone'] and len(after['research_runs'])==2
    finally: agent.db.close()


def test_migration_of_existing_database_preserves_data_and_backups(tmp_path):
    path=tmp_path/'old.db'
    conn=sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO companies(id,name,normalized_name,status,first_seen,updated_at) VALUES('abc123','Empresa antiga','empresa antiga','CONTACTED','2026-01-01','2026-01-01')")
    conn.execute("INSERT INTO sources(company_id,source_name,text,retrieved_at) VALUES('abc123','Fonte antiga','Evidência antiga','2026-01-01')")
    conn.execute("INSERT INTO saved_companies VALUES('abc123','Nota anterior preservada','2026-01-01')")
    conn.commit(); conn.close()
    db=Database(str(path))
    assert LeadRepository(db).detail('abc123')['commercial_status']=='contacted'
    assert LeadRepository(db).detail('abc123')['notes']=='Nota anterior preservada'
    assert db.query_one('SELECT COUNT(*) n FROM source_history')['n']==1
    assert len(list((tmp_path/'backups').glob('*.db')))==1
    db.close()
    db=Database(str(path))
    assert db.query_one('SELECT COUNT(*) n FROM schema_migrations')['n']==2
    assert db.query_one('SELECT COUNT(*) n FROM lead_events')['n']==1
    assert CompanyRepository(db).count()==1
    db.close()


def test_similar_names_are_flagged_not_merged(agent):
    a=CompanyProfile(name='Oficina Silva',city='Campinas',website='https://a.example',domain='a.example')
    b=CompanyProfile(name='Oficina Silva Auto Center',city='Campinas',website='https://b.example',domain='b.example')
    agent.companies.add(a);agent.companies.add(b)
    from utils.deduplication import is_same_company
    assert not is_same_company(a,b)
    leads=LeadRepository(agent.db)
    assert leads.duplicates(a.id) and agent.companies.count()==2
    assert 'possível duplicação' in agent.handle('/leads')


def test_archiving_is_confirmed_and_reversible(agent):
    agent.handle('/search oficinas em Campinas')
    identity=agent.companies.search_by_name('Oficina Delta')[0].id
    leads=LeadRepository(agent.db)
    assert 'Confirma' in agent.handle('/archive '+identity)
    agent.handle('não')
    assert not leads.resolve(identity)['archived']
    agent.handle('/archive '+identity); agent.handle('sim')
    assert leads.resolve(identity)['archived']
    assert identity not in agent.handle('/leads')
    assert identity in agent.handle('/leads arquivados')
    agent.handle('/restore '+identity)
    assert identity in agent.handle('/leads')


def test_archive_confirmation_is_cancelled_by_new_command(agent):
    profile=CompanyProfile(name='Manual')
    agent.companies.add(profile)
    agent.handle('/archive '+profile.id)
    agent.handle('/leads');agent.handle('sim')
    assert not LeadRepository(agent.db).resolve(profile.id)['archived']


def test_filter_and_save_by_id(agent):
    a=CompanyProfile(name='Clínica Árvore',city='São Paulo',segment='Saúde')
    b=CompanyProfile(name='Oficina',city='Campinas')
    agent.companies.add(a);agent.companies.add(b)
    agent.handle('/stage '+a.id+' qualified')
    agent.handle('/save '+a.id)
    reply=agent.handle('/leads arvore status=qualified cidade="São Paulo" segmento=saude salvos')
    assert a.id in reply and b.id not in reply
    assert LeadRepository(agent.db).resolve(a.id)['commercial_status']=='qualified'


def test_stage_history_and_no_auto_contact(agent):
    agent.handle('/search oficinas em Campinas')
    p=agent.companies.search_by_name('Oficina Delta')[0]
    leads=LeadRepository(agent.db)
    assert leads.resolve(p.id)['commercial_status']=='new'
    for stage in ('qualified','contact_pending','contacted','negotiating','converted','discarded'):
        agent.handle('/stage '+p.id+' '+stage)
    assert len([e for e in leads.events(p.id) if e['kind']=='stage'])==6
    assert agent.ignored.is_ignored(p.id)
    agent.handle('/stage '+p.id+' new')
    assert not agent.ignored.is_ignored(p.id)


def test_exports_are_selected_utf8_and_csv_formula_safe(agent,tmp_path):
    a=CompanyProfile(name='Clínica Árvore');b=CompanyProfile(name='Não selecionada')
    agent.companies.add(a);agent.companies.add(b)
    leads=LeadRepository(agent.db)
    leads.edit(a.id,'notes','=SUM(1,2)')
    json_path=leads.export('json',[a.id,a.id],tmp_path)
    rows=json.loads(json_path.read_text(encoding='utf-8'))
    assert [r['id'] for r in rows]==[a.id]
    assert rows[0]['notes']=='=SUM(1,2)'
    assert 'search_api_key' not in rows[0]
    csv_path=leads.export('csv',[a.id],tmp_path)
    with csv_path.open(encoding='utf-8-sig',newline='') as stream: rows=list(csv.DictReader(stream))
    assert rows[0]['name']=='Clínica Árvore' and rows[0]['notes'].startswith("'=")
    with pytest.raises(ValueError):leads.export('json',[],tmp_path)
    with pytest.raises(ValueError):leads.export('json',[a.id,'invalid'],tmp_path)


def test_export_write_error_leaves_no_partial_file(agent,tmp_path):
    p=CompanyProfile(name='Exemplo');agent.companies.add(p)
    with patch('database.leads.os.replace',side_effect=OSError('disk failure')):
        with pytest.raises(OSError):LeadRepository(agent.db).export('json',[p.id],tmp_path)
    assert list(tmp_path.iterdir())==[]


def test_lead_and_history_write_rollback_together(agent):
    p=CompanyProfile(name='Exemplo');agent.companies.add(p)
    agent.db.conn.execute("CREATE TRIGGER fail_event BEFORE INSERT ON lead_events BEGIN SELECT RAISE(ABORT,'simulated full disk'); END")
    reply=agent.handle('/stage '+p.id+' contacted')
    assert 'não' in reply.lower() and not agent.last_skill_result.success
    assert LeadRepository(agent.db).resolve(p.id)['commercial_status']=='new'


def test_company_creation_failure_does_not_leave_partial_lead(agent):
    agent.db.conn.execute("CREATE TRIGGER fail_event BEFORE INSERT ON lead_events BEGIN SELECT RAISE(ABORT,'simulated full disk'); END")
    agent.handle('/search oficinas em Campinas')
    assert not agent.last_skill_result.success
    assert agent.companies.count()==0
    assert agent.runs.last().status=='failed'
    assert not agent.runs.company_ids(agent.runs.last().id)


def test_locked_database_returns_safe_error(tmp_path):
    cfg=Config(database_path=str(tmp_path/'lock.db'))
    agent=build_agent(cfg)
    p=CompanyProfile(name='Exemplo');agent.companies.add(p)
    other=sqlite3.connect(cfg.database_path)
    try:
        agent.db.conn.execute('PRAGMA busy_timeout=0')
        other.execute('BEGIN IMMEDIATE')
        assert 'bloqueado' in agent.handle('/note '+p.id+' texto')
        assert not agent.last_skill_result.success
    finally:
        other.rollback();other.close();agent.db.close()


def test_source_versions_are_preserved(agent):
    p=CompanyProfile(name='Exemplo');agent.companies.add(p)
    agent.sources.replace_for_company(p.id,[Observation('Antes','Site','https://example.org','2026-01-01')])
    agent.sources.replace_for_company(p.id,[Observation('Depois','Site','https://example.org','2026-02-01')])
    assert [o.text for o in agent.sources.list_for_company(p.id)]==['Depois']
    assert len(LeadRepository(agent.db).detail(p.id)['sources'])==2


def test_cancel_rolls_back_incomplete_company_and_association(agent):
    from skills.base import ExecutionStopped
    with patch.object(agent,'_investigate',side_effect=ExecutionStopped('cancelled')):
        agent.handle('/search oficinas em Campinas')
    run=agent.runs.last()
    assert run.status=='cancelled' and run.new_count==0
    assert agent.companies.count()==0 and not agent.runs.company_ids(run.id)
    assert agent.db.query_one('SELECT COUNT(*) n FROM lead_events')['n']==0


def test_export_command_and_invalid_fields(tmp_path):
    agent=build_agent(Config(database_path=str(tmp_path/'commands.db')))
    try:
        p=CompanyProfile(name='Empresa Árvore');agent.companies.add(p)
        assert 'concluída' in agent.handle('/export json '+p.id)
        files=list((tmp_path/'exports').glob('*.json'))
        assert len(files)==1 and json.loads(files[0].read_text(encoding='utf-8'))[0]['id']==p.id
        assert 'inválidos' in agent.handle('/edit '+p.id+' commercial_status converted')
        assert LeadRepository(agent.db).resolve(p.id)['commercial_status']=='new'
    finally: agent.db.close()


def test_backup_is_closed_and_restores_commercial_history(agent,tmp_path):
    p=CompanyProfile(name='Empresa de backup');agent.companies.add(p)
    leads=LeadRepository(agent.db)
    leads.stage(p.id,'qualified');leads.edit(p.id,'notes','Conservar observação')
    original=sqlite3.connect
    closed=[]
    class TrackingConnection(sqlite3.Connection):
        def close(self):
            closed.append(True)
            super().close()
    def connect(path):return original(path,factory=TrackingConnection)
    with patch('database.database.sqlite3.connect',side_effect=connect):
        backup=agent.db.backup(tmp_path/'backups')
    assert closed==[True]
    recovered=Database(backup)
    try:
        assert recovered.query_one('PRAGMA integrity_check')[0]=='ok'
        detail=LeadRepository(recovered).detail(p.id)
        assert detail['notes']=='Conservar observação' and detail['commercial_status']=='qualified'
        assert len(detail['events'])==3
    finally:recovered.close()


def test_domain_variants_dedupe_but_conflicting_domains_do_not():
    from utils.deduplication import is_same_company
    a=CompanyProfile(name='Empresa',city='Campinas',domain='WWW.EXAMPLE.ORG')
    b=CompanyProfile(name='Empresa Ltda',city='Campinas',website='https://example.org/contato?q=1')
    assert is_same_company(a,b)
    b.website='https://other.example'
    assert not is_same_company(a,b)


def test_partial_investigation_keeps_discovery_evidence(agent):
    from utils.http_client import FetchError
    source=agent.investigator.sources[0]
    from database.models import RawCompany
    discovered=RawCompany(name='Oficina Delta',city='Campinas',observations=[Observation('Identidade verificada na descoberta','Fonte de teste','https://example.org','2026-01-01')])
    with patch.object(agent.finder,'find',return_value=[discovered]), patch.object(source,'fetch_observations',side_effect=FetchError('Fonte indisponível')):
        agent.handle('/search oficinas em Campinas')
    assert agent.runs.last().status=='partial'
    p=agent.companies.search_by_name('Oficina Delta')[0]
    assert LeadRepository(agent.db).detail(p.id)['sources']
    assert not p.investigated


def test_archived_lead_is_not_recommended_or_reintroduced(agent):
    agent.handle('/search clínicas em São Paulo')
    p=agent.companies.search_by_name('Clínica Alpha')[0]
    LeadRepository(agent.db).archive(p.id)
    assert p.name not in agent.handle('/interesting')
    agent.handle('/search clínicas em São Paulo')
    assert p.id not in agent.runs.company_ids(agent.runs.last().id)
    assert agent.companies.get(p.id) is not None
