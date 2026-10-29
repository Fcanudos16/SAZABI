import json
import sys
from threading import Event
import pytest
from core.bootstrap import build_agent
from core.config import Config
from core.commands.registry import default_registry


@pytest.fixture
def personal(tmp_path):
    agent = build_agent(Config(database_path=str(tmp_path/'personal.db'), local_roots=(str(tmp_path),)))
    yield agent
    agent.db.close()


def execute(agent, command):
    agent.handle(command)
    return agent.last_skill_result


def test_registry_and_no_commercial_fallback(personal):
    names = default_registry().commands
    assert {'task','files','research','git','help'} <= names.keys()
    assert not {'leads','profile','strategies','outreach'} & names.keys()
    for command in ['/search clínicas em Campinas', '/research clínicas em Campinas', 'procure clínicas em Campinas', '/leads']:
        assert not execute(personal, command).success
    assert personal.runs.count() == personal.companies.count() == 0
    assert not personal.finder.sources


def test_tasks_persist_edit_due_export(personal, tmp_path):
    assert execute(personal, '/task add "Comprar pão" priority=alta due=2020-01-01 category=casa project=Compras').success
    assert execute(personal, '/task edit 1 title="Comprar café"').success
    assert 'Comprar café' in execute(personal, '/task list overdue').message
    assert execute(personal, '/task export tarefas.json').success
    assert json.loads((tmp_path/'tarefas.json').read_text('utf-8'))[0]['priority'] == 'alta'
    assert not execute(personal, '/task export tarefas.json').success
    other = build_agent(Config(database_path=personal.db.path, local_roots=(str(tmp_path),)))
    try:
        assert 'Comprar café' in execute(other, '/task list').message
        assert execute(other, '/task done 1').success
        assert json.loads(execute(other, '/task list pending').message) == []
    finally:
        other.db.close()


@pytest.mark.parametrize('command', ['/task done 999', '/task add abc priority=urgente', '/task add abc due=amanha', '/task edit 999 title=abc', '/files find ..', '/files find . min=x', '/run inventado', '/confirm inventado'])
def test_bad_inputs_isolated(personal, command):
    assert not execute(personal, command).success
    assert execute(personal, '/task add ok').success


def test_files_filters_duplicates_and_references(personal, tmp_path):
    (tmp_path/'a.txt').write_text('documentação técnica\nSQLite funciona', encoding='utf-8')
    (tmp_path/'b.txt').write_bytes((tmp_path/'a.txt').read_bytes())
    (tmp_path/'.env').write_text('SECRET=do-not-show')
    result = execute(personal, '/files find . ext=.txt min=2')
    assert json.loads(result.message)['total'] == 2
    assert len(json.loads(execute(personal, '/files duplicates .').message)['duplicates_sha256']) == 1
    result = execute(personal, '/research SQLite .')
    assert 'a.txt:2:' in result.message
    assert 'do-not-show' not in execute(personal, '/research SECRET .').message
    assert not execute(personal, '/files move .env exposed.txt').success


def test_move_preview_confirm_undo_and_replay(personal, tmp_path):
    source = tmp_path/'a.txt'
    source.write_text('original')
    result = execute(personal, '/files move a.txt b.txt')
    assert result.status == 'needs_confirmation' and source.exists()
    token = result.data['token']
    assert execute(personal, '/confirm '+token).success
    assert not source.exists() and (tmp_path/'b.txt').read_text() == 'original'
    assert not execute(personal, '/confirm '+token).success
    undo = next(iter(personal.personal.plans))
    assert execute(personal, '/confirm '+undo).success
    assert source.read_text() == 'original'


def test_changed_preview_refuses_all_moves(personal, tmp_path):
    (tmp_path/'a.txt').write_text('a')
    (tmp_path/'b.txt').write_text('b')
    result = execute(personal, '/files organize .')
    assert 'personal.db' not in result.message
    token = result.data['token']
    (tmp_path/'a.txt').write_text('changed')
    assert not execute(personal, '/confirm '+token).success
    assert (tmp_path/'b.txt').exists()


def test_cancelled_and_recovery_history(personal, tmp_path):
    event = Event(); event.set()
    personal.handle('/task add forbidden', cancelled=event)
    assert personal.last_skill_result.status == 'cancelled'
    assert personal.db.query_one('SELECT COUNT(*) FROM personal_tasks')[0] == 0
    identity = personal.personal.store.start('interrupted')
    other = build_agent(Config(database_path=personal.db.path, local_roots=(str(tmp_path),)))
    try:
        assert other.db.query_one('SELECT status FROM personal_operations WHERE id=?', (identity,))[0] == 'failed'
    finally:
        other.db.close()


def test_script_requires_confirmation_real_exit_code(personal, tmp_path):
    script = tmp_path/'script.py'
    script.write_text("from pathlib import Path\nPath('proof.txt').write_text('executed')\nraise SystemExit(3)\n")
    personal.config.local_routines['sample'] = {'argv': [sys.executable, str(script)], 'cwd': str(tmp_path)}
    result = execute(personal, '/run sample')
    assert result.status == 'needs_confirmation' and not (tmp_path/'proof.txt').exists()
    result = execute(personal, '/confirm '+result.data['token'])
    assert not result.success and '3' in result.message
    assert (tmp_path/'proof.txt').read_text() == 'executed'


def test_script_change_invalidates_approval(personal, tmp_path):
    script = tmp_path/'script.py'; script.write_text('print(1)')
    personal.config.local_routines['sample'] = {'argv': [sys.executable, str(script)], 'cwd': str(tmp_path)}
    result = execute(personal, '/run sample')
    script.write_text('print(2)')
    assert not execute(personal, '/confirm '+result.data['token']).success


def test_review_syntax_and_eval(personal, tmp_path):
    (tmp_path/'bad.py').write_text('if :')
    (tmp_path/'risky.py').write_text('eval(input())')
    result = execute(personal, '/review .')
    assert result.success and 'bad.py:1' in result.message and 'risky.py:1' in result.message


def test_sensitive_inputs_not_persisted(personal):
    secret = 'gsk_'+'x'*30
    assert not execute(personal, '/task add '+secret).success
    assert secret not in str(personal.db.query('SELECT * FROM personal_operations'))
    assert personal.db.query_one('SELECT COUNT(*) FROM personal_tasks')[0] == 0


def test_backup_integrity(personal):
    import sqlite3
    execute(personal, '/task add persist')
    result = execute(personal, '/backup')
    assert result.success
    with sqlite3.connect(result.message.removeprefix('Backup verificado: ')) as backup:
        assert backup.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert backup.execute('SELECT title FROM personal_tasks').fetchone()[0] == 'persist'


def test_git_real_repository(personal, tmp_path):
    import subprocess
    subprocess.run(['git', 'init', str(tmp_path/'repo')], check=True, capture_output=True)
    (tmp_path/'repo'/'untracked.txt').write_text('hello')
    result = execute(personal, '/git status repo')
    assert result.success and 'untracked.txt' in result.message
    assert not execute(personal, '/git reset repo').success


def test_process_cancellation_real_child(personal, tmp_path):
    import threading
    from skills.base import SkillContext, ExecutionStopped
    (tmp_path/'wait.py').write_text('import time\ntime.sleep(30)')
    context = SkillContext(personal)
    timer = threading.Timer(.3, context.cancelled.set)
    timer.start()
    try:
        with pytest.raises(ExecutionStopped):
            personal.personal.process([sys.executable, str(tmp_path/'wait.py')], tmp_path, context)
    finally:
        timer.cancel()


@pytest.mark.parametrize('path', ['a.txt:secret', 'NUL', 'CON.txt', '.env', 'credentials.json'])
def test_reserved_paths(personal, path):
    with pytest.raises(ValueError):
        personal.personal.policy.path(path, exists=False)


def test_missing_folder_reports_failure(personal):
    assert not execute(personal, '/files find missing').success
    assert not execute(personal, '/settings arbitrary').success
