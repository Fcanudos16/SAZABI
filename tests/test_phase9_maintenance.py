"""Operational failures and restoration use isolated disposable SQLite files."""
from datetime import date,timedelta
import json
import logging
from pathlib import Path
import sqlite3
from threading import Event
from unittest.mock import patch
import pytest
from core.config import Config
from core.maintenance import Maintenance
from core.worker import AgentWorker
from database.database import Database
from database.models import CompanyProfile,Observation
from database.leads import LeadRepository
from database.restore import restore_backup,validate_backup
from database.recovery import research_lock,ResearchBusy
from tests.factories import build_agent
from utils.logger import setup_logging,redact
from utils.timeutils import now_iso


@pytest.fixture
def persistent(tmp_path):
    agent=build_agent(Config(database_path=str(tmp_path/'test.db'),mock=True))
    try:yield agent
    finally:agent.db.close()


def test_verified_backup_retention_and_failure_preserve_old(persistent):
    service=Maintenance(persistent)
    service.configure('retention',2)
    paths=[service.backup() for _ in range(3)]
    assert len(service.backups())==2 and not Path(paths[0]).exists()
    assert validate_backup(paths[-1])['version']==4
    before=service.backups()
    with patch.object(persistent.db,'backup',side_effect=OSError('synthetic disk full')):
        with pytest.raises(OSError):service.backup()
    assert before==service.backups()
    assert service.get('journal')[-1]['status']=='failed'
    assert not list(Path(paths[-1]).parent.glob('*.pending'))


def test_backup_publish_failure_cleans_partial(persistent):
    with patch('os.replace',side_effect=OSError('synthetic replace failure')):
        with pytest.raises(OSError):persistent.db.backup()
    assert not list((Path(persistent.db.path).parent/'backups').iterdir())


def test_restore_confirmation_integrity_rescue_and_session_lock(tmp_path):
    path=tmp_path/'restore.db'
    agent=build_agent(Config(database_path=str(path),mock=True))
    p=CompanyProfile(name='Original sintética');agent.companies.add(p)
    repo=LeadRepository(agent.db)
    repo.stage(p.id,'negotiating');repo.edit(p.id,'notes','Nota original')
    repo.create_task(p.id,'Tarefa original','2026-12-01')
    backup=agent.db.backup()
    repo.edit(p.id,'notes','Nota posterior')
    with pytest.raises(ValueError):restore_backup(path,backup)
    with research_lock(agent.db,suffix='.session.lock'),pytest.raises(ResearchBusy):restore_backup(path,backup,True)
    agent.db.close()
    rescue=restore_backup(path,backup,True)
    assert rescue and validate_backup(rescue)['companies']==1
    with sqlite3.connect(rescue) as conn:assert conn.execute('SELECT notes FROM companies').fetchone()[0]=='Nota posterior'
    agent=build_agent(Config(database_path=str(path),mock=True))
    try:
        detail=LeadRepository(agent.db).detail(p.id)
        assert detail['notes']=='Nota original' and detail['commercial_status']=='negotiating'
        assert detail['tasks'] and detail['events']
        assert Maintenance(agent).integrity()['ok']
    finally:agent.db.close()


def test_corrupt_unrelated_and_future_backup_refused_without_mutating(tmp_path,persistent):
    corrupt=tmp_path/'corrupt.db';corrupt.write_bytes(b'not sqlite')
    unrelated=tmp_path/'other.db'
    with sqlite3.connect(unrelated) as conn:conn.execute('CREATE TABLE unrelated(id)')
    future=Path(persistent.db.backup())
    with sqlite3.connect(future) as conn:conn.execute("INSERT INTO schema_migrations VALUES(999,'test')")
    for path in (corrupt,unrelated,future):
        with pytest.raises((ValueError,sqlite3.Error)):restore_backup(persistent.db.path,path,True)
    assert not (Path(persistent.db.path).parent/'rescue').exists()
    assert persistent.db.query_one('SELECT MAX(version) FROM schema_migrations')[0]==4


def test_options_persist_validate_and_health_is_sanitized(persistent):
    service=Maintenance(persistent)
    service.configure('auto_refresh',True)
    assert Maintenance(persistent).options()['auto_refresh']
    before=service.options()
    for key,value in [('retention',0),('auto_backup','true'),('refresh_minutes',1),('retention',True)]:
        with pytest.raises(ValueError):service.configure(key,value)
    assert service.options()==before
    persistent.config.groq_api_key='gsk_SUPERSECRET'
    persistent.config.search_api_key='tvly-SUPERSECRET'
    output=json.dumps(service.health())
    assert 'SUPERSECRET' not in output and 'mean_completed_seconds' in output
    assert 'não verificada' in service.health()['integrations']['Groq']
    assert agent_command(persistent,'/health')
    assert agent_command(persistent,'/diagnostics')


def agent_command(agent,text):
    agent.handle(text)
    return agent.last_skill_result.success


def test_due_notifications_are_deduplicated_and_configurable(persistent):
    p=CompanyProfile(name='Teste');persistent.companies.add(p)
    LeadRepository(persistent.db).create_task(p.id,'Sintética',date.today().isoformat())
    messages=[];service=Maintenance(persistent,messages.append)
    service.configure('auto_backup',False);service.configure('due_alerts',True)
    service.tick();service.tick()
    assert len(messages)==1
    again=Maintenance(persistent,messages.append);again.tick()
    assert len(messages)==1
    service.configure('notifications',False)
    assert not service.alert('different','Não enviar')
    assert len(messages)==1


def test_backup_failure_alert_is_deduplicated(persistent):
    messages=[];service=Maintenance(persistent,messages.append)
    with patch.object(persistent.db,'backup',side_effect=OSError('test')):
        for _ in range(2):
            with pytest.raises(OSError):service.backup()
    assert len(messages)==1


def test_periodic_opt_in_limit_failures_and_manual_reset(persistent):
    p=CompanyProfile(name='Sintética',website='https://example.test',last_researched='2000-01-01',investigated=True)
    persistent.companies.add(p)
    service=Maintenance(persistent);service.configure('auto_backup',False)
    with patch.object(persistent,'handle') as handle:
        service.tick();handle.assert_not_called()
        service.configure('auto_refresh',True)
        for _ in range(4):
            record=service.get('refresh:'+p.id,{})
            record.pop('next_attempt',None);service.put('refresh:'+p.id,record)
            service.put('refresh_tick',None);service.tick()
        assert handle.call_count==3
    assert service.get('refresh:'+p.id)['failures']==3
    assert persistent.companies.get(p.id).last_researched=='2000-01-01'
    assert agent_command(persistent,'/maintenance reset-refresh '+p.id)
    assert service.get('refresh:'+p.id)['failures']==0


def test_refresh_success_preserves_business_context_and_tracks_unconfirmed(persistent):
    persistent.handle('/search clínicas em Campinas')
    p=persistent.companies.search_by_name('Clínica Vida Campinas')[0]
    repo=LeadRepository(persistent.db)
    repo.stage(p.id,'contacted');repo.edit(p.id,'notes','Nota comercial')
    repo.create_task(p.id,'Acompanhar','2026-12-01')
    persistent.db.execute("UPDATE companies SET last_researched='2000-01-01' WHERE id=?",(p.id,))
    service=Maintenance(persistent)
    service.configure('auto_backup',False);service.configure('auto_refresh',True)
    old_context=persistent.memory.last_company_id()
    service.tick()
    record=service.get('refresh:'+p.id)
    assert record['status']=='completed' and record['last_success']
    assert 'unconfirmed_observations' in record
    assert repo.resolve(p.id)['notes']=='Nota comercial'
    assert repo.resolve(p.id)['commercial_status']=='contacted'
    assert repo.tasks(p.id) and persistent.memory.last_company_id()==old_context
    with patch.object(persistent,'handle') as handle:
        service.tick();handle.assert_not_called()


def test_unknown_refresh_not_retried_and_pending_user_input_not_overridden(persistent):
    p=CompanyProfile(name='Teste',website='https://example.test');persistent.companies.add(p)
    service=Maintenance(persistent);service.put('refresh:'+p.id,{'status':'running'})
    service.recover()
    assert service.get('refresh:'+p.id)['status']=='unknown'
    service.configure('auto_backup',False);service.configure('auto_refresh',True)
    persistent._pending={'type':'region'}
    with patch.object(persistent,'handle') as handle:
        service.tick();handle.assert_not_called()
    assert persistent._pending=={'type':'region'}
    cancelled=Event();cancelled.set()
    with patch.object(service,'refresh_one') as refresh:
        service.tick(cancelled);refresh.assert_not_called()


def test_logs_redact_tracebacks_and_rotate(tmp_path):
    path=tmp_path/'test.log';logger=setup_logging('INFO',str(path))
    try:
        for handler in logger.handlers:handler.maxBytes=250;handler.backupCount=2
        for i in range(15):logger.info('entry %s %s',i,'x'*80)
        try:raise ValueError('gsk_SUPERSECRET Bearer token-value tvly-PRIVATE password=hidden')
        except ValueError:logger.exception('Falha sintética')
        for handler in logger.handlers:handler.flush()
        logs=list(tmp_path.glob('test.log*'))
        assert len(logs)<=3 and len(logs)>1
        text=''.join(p.read_text(encoding='utf-8') for p in logs)
        assert 'SUPERSECRET' not in text and 'token-value' not in text and 'hidden' not in text
        assert '[REDACTED]' in text
    finally:
        for handler in list(logger.handlers):handler.close();logger.removeHandler(handler)


def test_worker_backup_failure_still_ready_and_releases_session(tmp_path):
    config=Config(database_path=str(tmp_path/'worker.db'))
    with patch('database.database.Database.backup',side_effect=OSError('synthetic failure')):
        worker=AgentWorker(config)
        events=[]
        try:
            while not any(kind=='ready' for kind,value in events):events.append(worker.events.get(timeout=10))
            assert not any(kind=='error' for kind,value in events)
            assert len([1 for kind,value in events if kind=='maintenance_alert'])==1
            worker.submit('/health')
            assert worker.events.get(timeout=10)[0]=='reply'
        finally:worker.close();worker.thread.join(10)
    assert not worker.thread.is_alive()
    from types import SimpleNamespace
    with research_lock(SimpleNamespace(path=config.database_path),suffix='.session.lock'):pass
