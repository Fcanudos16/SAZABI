"""Commercial workflow with synthetic companies and isolated SQLite databases."""
from datetime import date, timedelta
import json
import sqlite3
from unittest.mock import patch

import pytest
from core.config import Config
from database.database import Database
from database.leads import LeadRepository, STAGES
from database.models import CompanyProfile, Observation
from database.repositories import CompanyRepository, SourceRepository
from tests.factories import build_agent


def company(agent, name='Empresa sintética'):
    profile=CompanyProfile(name=name,city='São Paulo',segment='oficina')
    agent.companies.add(profile)
    return profile


def test_all_stages_manual_and_history_idempotent(agent):
    p=company(agent);repo=LeadRepository(agent.db)
    for stage in STAGES:
        agent.handle(f'/stage {p.id} {stage} Revisão manual de teste')
        assert agent.last_skill_result.success
        assert repo.resolve(p.id)['commercial_status']==stage
    events=repo.events(p.id)
    assert len([e for e in events if e['kind']=='stage'])==len(STAGES)-1
    assert len([e for e in events if e['kind']=='manual_contact'])==1
    agent.handle(f'/stage {p.id} discarded')
    assert repo.events(p.id)==events
    agent.handle(f'/lead {p.id}')
    assert repo.resolve(p.id)['commercial_status']=='discarded'
    assert repo.events(p.id)==events


def test_tasks_overdue_today_completion_reopen_edit_and_overview(agent):
    p=company(agent);repo=LeadRepository(agent.db)
    yesterday=(date.today()-timedelta(days=1)).isoformat()
    today=date.today().isoformat()
    agent.handle(f'/task {p.id} {yesterday} Confirmar atividade | Dados sintéticos')
    assert agent.last_skill_result.success
    first=repo.tasks(p.id)[0]
    second=repo.create_task(p.id,'Acompanhar',today)
    assert repo.overview()['overdue']==1
    assert len(repo.list(overdue=True))==1
    assert 'VENCIDA' in agent.handle('/tasks vencidas')
    agent.handle(f"/taskdone {first['id']}")
    assert agent.last_skill_result.success
    assert repo.overview()['overdue']==0
    assert repo.tasks(p.id,include_completed=True)[-1]['completed_at']
    assert repo.detail(p.id)['next_action']['id']==second
    agent.handle(f"/taskreopen {first['id']}")
    assert repo.overview()['overdue']==1
    agent.handle(f"/taskedit {first['id']} {today} Novo título | Nova descrição")
    assert repo.overview()['overdue']==0
    assert repo.tasks(p.id)[0]['description']=='Nova descrição'
    assert all(t['created_at'] for t in repo.tasks(p.id))
    assert repo.overview()['total']==1 and repo.overview()['stages']['new']==1
    repo.stage(p.id,'converted','Confirmado pelo usuário')
    assert repo.overview()['stages']['converted']==1
    repo.archive(p.id)
    assert repo.overview()['total']==0 and not repo.overview()['upcoming']
    repo.archive(p.id,False)
    assert repo.overview()['total']==1


@pytest.mark.parametrize('due',['2026-02-30','16/10/2026','20261016','2026-1-01','2026-10-16T12:00:00'])
def test_invalid_task_date_does_not_write(agent,due):
    p=company(agent);repo=LeadRepository(agent.db)
    initial=repo.events(p.id)
    agent.handle(f'/task {p.id} {due} Teste')
    assert not agent.last_skill_result.success
    assert not repo.tasks() and repo.events(p.id)==initial


def test_task_and_event_are_atomic(agent):
    p=company(agent);repo=LeadRepository(agent.db)
    with patch.object(repo,'event',side_effect=sqlite3.OperationalError('test failure')):
        with pytest.raises(sqlite3.OperationalError): repo.create_task(p.id,'Teste','2026-10-16')
    assert not repo.tasks()
    task=repo.create_task(p.id,'Teste','2026-10-16')
    with patch.object(repo,'event',side_effect=sqlite3.OperationalError('test failure')):
        with pytest.raises(sqlite3.OperationalError): repo.change_task(task,completed=True)
    assert not repo.tasks()[0]['completed']


def test_filter_sort_and_latest_score_use_real_records(agent):
    repo=LeadRepository(agent.db)
    a=company(agent,'A');b=company(agent,'B');c=company(agent,'C')
    repo.stage(b.id,'verifying')
    for identity,score,category in [(a.id,90,'high'),(b.id,50,'moderate'),(a.id,20,'low')]:
        agent.db.execute('INSERT INTO lead_evaluations(company_id,input_hash,engine_version,score,category,result_json,evaluated_at) VALUES(?,?,?,?,?,?,?)',
                         (identity,'test','test',score,category,'{}','2026-10-16'))
    agent.db.execute("UPDATE companies SET first_seen='2026-01-02T15:00:00+00:00',updated_at='2026-01-02' WHERE id=?",(a.id,))
    agent.db.execute("UPDATE companies SET first_seen='2026-03-02T15:00:00+00:00',updated_at='2026-03-02' WHERE id=?",(b.id,))
    assert [r['id'] for r in repo.list(min_score=30,max_score=60,order='score')]==[b.id]
    assert [r['id'] for r in repo.list(stage='verifying',segment='oficina')]==[b.id]
    assert [r['id'] for r in repo.list(discovered_from='2026-01-01',discovered_to='2026-01-31')]==[a.id]
    assert [r['id'] for r in repo.list(insufficient=True)]==[c.id]
    assert repo.list(order='discovered')[-1]['id']==a.id
    assert repo.list(order='updated')[-1]['id']==a.id
    repo.create_task(b.id,'Prazo','2026-10-20')
    assert repo.list(order='next')[0]['id']==b.id
    agent.handle('/leads min_score=30 max_score=60 status=verifying ordem=score')
    assert agent.last_skill_result.success


def test_restart_and_research_preserve_manual_fields_tasks_and_history(tmp_path):
    config=Config(database_path=str(tmp_path/'workflow.db'),mock=True)
    agent=build_agent(config)
    agent.handle('/search oficinas em Campinas')
    p=agent.companies.search_by_name('Oficina Delta')[0];repo=LeadRepository(agent.db)
    repo.stage(p.id,'negotiating','Conversa registrada pelo usuário')
    repo.edit(p.id,'notes','Nota sintética preservada')
    repo.edit(p.id,'phone','11999990000')
    task=repo.create_task(p.id,'Acompanhar','2026-10-20')
    original_sources=repo.detail(p.id)['sources']
    agent.db.close()
    agent=build_agent(config);repo=LeadRepository(agent.db)
    try:
        agent.handle('/search oficinas em Campinas')
        profile=agent.companies.get(p.id);profile.phone='000'
        agent.companies.update(profile)
        detail=repo.detail(p.id)
        assert detail['phone']=='11999990000'
        assert detail['manual_fields']['phone']['origin']=='user'
        assert detail['notes']=='Nota sintética preservada' and detail['commercial_status']=='negotiating'
        assert detail['tasks'][0]['id']==task
        assert len(detail['research_runs'])==2
        assert all(s in detail['sources'] for s in original_sources)
        assert len(agent.companies.search_by_name('Oficina Delta'))==1
        assert any(e['kind']=='stage' for e in detail['events'])
    finally: agent.db.close()


def test_v2_migration_keeps_children_indexes_triggers_and_rollback(tmp_path):
    path=str(tmp_path/'v2.db')
    with patch('database.migrations._v3'), patch('database.migrations._v4'):
        db=Database(path)
        p=CompanyProfile(name='Antiga sintética');CompanyRepository(db).add(p)
        LeadRepository(db).stage(p.id,'contacted')
        db.execute("UPDATE companies SET phone='123' WHERE id=?",(p.id,))
        LeadRepository(db).event(p.id,'edit',json.dumps({'field':'phone','before':None,'after':'123'}))
        SourceRepository(db).replace_for_company(p.id,[Observation('Fonte sintética','Teste','https://example.test')])
        db.close()
    from database.migrations import _v3
    def fail(db):
        _v3(db)
        raise RuntimeError('synthetic failure after rebuild')
    with patch('database.migrations._v3',side_effect=fail),pytest.raises(RuntimeError): Database(path)
    with sqlite3.connect(path) as conn:
        assert conn.execute('SELECT MAX(version) FROM schema_migrations').fetchone()[0]==2
        assert conn.execute('SELECT COUNT(*) FROM sources').fetchone()[0]==1
        assert conn.execute('SELECT COUNT(*) FROM lead_events').fetchone()[0]==4
    db=Database(path)
    try:
        repo=LeadRepository(db)
        assert repo.resolve(p.id)['commercial_status']=='contacted'
        assert json.loads(repo.resolve(p.id)['manual_fields'])['phone']['value']=='123'
        assert db.query_one('SELECT COUNT(*) n FROM sources')['n']==1
        assert db.query_one('PRAGMA foreign_keys')[0]==1
        assert not db.query('PRAGMA foreign_key_check')
        repo.stage(p.id,'verifying')
        new=CompanyProfile(name='Depois');CompanyRepository(db).add(new)
        assert repo.events(new.id)[0]['kind']=='identified'
        assert db.query_one("SELECT name FROM sqlite_master WHERE name='idx_companies_domain'")
        assert db.query_one('PRAGMA integrity_check')[0]=='ok'
    finally: db.close()
