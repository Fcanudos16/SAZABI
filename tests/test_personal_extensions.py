import json
from pathlib import Path
import subprocess
import pytest
from core.bootstrap import build_agent
from core.config import Config
from research.knowledge import TextParser, WikimediaSearch, PublicDocuments, Knowledge
from utils.http_client import FetchError


@pytest.fixture
def agent(tmp_path):
    value = build_agent(Config(database_path=str(tmp_path/'agent.db'), local_roots=(str(tmp_path),)))
    yield value
    value.db.close()


def command(agent, text):
    agent.handle(text)
    assert agent.last_skill_result is not None
    return agent.last_skill_result


def confirm(agent, result):
    assert result.status == 'needs_confirmation', result.message
    return command(agent, '/confirm '+result.data['token'])


def git(root, *args):
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr.decode('utf-8', 'replace')
    return result.stdout.decode('utf-8', 'replace').strip()


@pytest.fixture
def repo(tmp_path):
    root = tmp_path/'repo'; root.mkdir()
    git(root, 'init', '-b', 'main')
    git(root, 'config', 'user.name', 'SAZABI Test')
    git(root, 'config', 'user.email', 'sazabi@example.invalid')
    (root/'file.py').write_text('value = 1\n')
    git(root, 'add', 'file.py'); git(root, 'commit', '-m', 'initial')
    return root


def test_git_stage_commit_branch_real(agent, repo):
    (repo/'file.py').write_text('value = 2\n')
    result = command(agent, '/git add repo file.py')
    assert '+value = 2' in result.message
    assert git(repo, 'diff', '--cached') == ''
    assert confirm(agent, result).success
    result = command(agent, '/git commit repo "Atualiza valor"')
    assert 'value = 2' in result.message
    assert confirm(agent, result).success
    assert git(repo, 'log', '-1', '--format=%s') == 'Atualiza valor'
    assert confirm(agent, command(agent, '/git branch repo codex/test')).success
    assert 'codex/test' in git(repo, 'branch', '--list')


@pytest.mark.parametrize('change', ['worktree', 'index', 'config', 'head', 'attributes'])
def test_git_stale_plan_rejected(agent, repo, change):
    (repo/'file.py').write_text('value = 2\n')
    result = command(agent, '/git add repo file.py')
    if change == 'worktree':
        (repo/'file.py').write_text('value = 3\n')
    elif change == 'index':
        git(repo, 'add', 'file.py')
    elif change == 'config':
        git(repo, 'config', 'user.name', 'Changed')
    elif change == 'attributes':
        (repo/'.git'/'info'/'attributes').write_text('file.py text eol=crlf\n')
    else:
        git(repo, 'commit', '--allow-empty', '-m', 'advance')
    assert not confirm(agent, result).success


def test_git_no_shell_paths_and_secrets(agent, repo):
    (repo/'new.txt').write_text('safe contents\n')
    result = command(agent, '/git add repo new.txt')
    assert 'safe contents' in result.message
    assert confirm(agent, result).success
    assert not command(agent, '/git add repo .').success
    assert not command(agent, '/git reset repo --hard').success
    (repo/'.env').write_text('SECRET=hidden')
    assert not command(agent, '/git add repo .env').success


def test_git_rejects_executable_filters(agent, repo):
    git(repo, 'config', 'filter.unsafe.clean', 'arbitrary-program')
    (repo/'.gitattributes').write_text('*.py filter=unsafe\n')
    assert not command(agent, '/git add repo file.py').success


@pytest.fixture
def remote(tmp_path, repo):
    root = tmp_path/'remote.git'; root.mkdir()
    git(root, 'init', '--bare', '-b', 'main')
    git(repo, 'remote', 'add', 'origin', str(root))
    return root


def test_git_push_and_pull_real_local_remote(agent, repo, remote, tmp_path):
    result = command(agent, '/git push repo origin main')
    assert 'inexistente' in result.message
    assert confirm(agent, result).success
    assert git(remote, 'rev-parse', 'main') == git(repo, 'rev-parse', 'HEAD')
    peer = tmp_path/'peer'
    git(tmp_path, 'clone', str(remote), str(peer))
    git(peer, 'config', 'user.name', 'Peer'); git(peer, 'config', 'user.email', 'peer@example.invalid')
    (peer/'file.py').write_text('value = 3\n')
    git(peer, 'add', 'file.py'); git(peer, 'commit', '-m', 'remote update'); git(peer, 'push', 'origin', 'main')
    result = command(agent, '/git pull repo origin main')
    assert (repo/'file.py').read_text() == 'value = 1\n'
    finished = confirm(agent, result)
    assert finished.success, finished.message
    assert (repo/'file.py').read_text() == 'value = 3\n'


def test_remote_changed_after_preview(agent, repo, remote):
    git(repo, 'push', 'origin', 'main')
    result = command(agent, '/git push repo origin main')
    git(remote, 'update-ref', '-d', 'refs/heads/main')
    assert not confirm(agent, result).success


def test_pull_dirty_refused(agent, repo, remote):
    git(repo, 'push', 'origin', 'main')
    (repo/'file.py').write_text('unsaved = True\n')
    assert not command(agent, '/git pull repo origin main').success
    assert 'unsaved' in (repo/'file.py').read_text()


def test_review_rules_and_proposal_real(agent, tmp_path):
    code = 'import subprocess as sp\ndef f(cache=[]):\n    try:\n        sp.run("x", shell=True)\n    except:\n        pass\n'
    path = tmp_path/'risky.py'; path.write_text(code)
    result = command(agent, '/review risky.py')
    rules = {row['rule'] for row in result.data['findings']}
    assert {'mutable-default', 'shell', 'bare-except'} <= rules
    proposal = command(agent, '/review fix risky.py bare-except')
    assert path.read_text() == code
    applied = confirm(agent, proposal)
    assert applied.success, applied.message
    assert 'except Exception:' in path.read_text()
    assert list(tmp_path.glob('.sazabi-original-*'))
    undo = next(iter(agent.personal.plans))
    assert command(agent, '/confirm '+undo).success
    assert path.read_text() == code


def test_candidate_diff_stale_and_syntax(agent, tmp_path):
    (tmp_path/'code.py').write_text('a = 1\n')
    (tmp_path/'candidate.py').write_text('a = 2\n')
    proposal = command(agent, '/review propose code.py candidate.py')
    assert '-a = 1' in proposal.message and '+a = 2' in proposal.message
    (tmp_path/'code.py').write_text('a = 3\n')
    assert not confirm(agent, proposal).success
    assert (tmp_path/'code.py').read_text() == 'a = 3\n'
    (tmp_path/'candidate.py').write_text('if :')
    assert not command(agent, '/review propose code.py candidate.py').success


def test_fix_then_execute_real_test_project(agent, tmp_path):
    root = tmp_path/'project'; root.mkdir(); (root/'tests').mkdir()
    source = root/'value.py'; source.write_text('def value():\n    return 1\n')
    (root/'candidate.py').write_text('def value():\n    return 2\n')
    (root/'tests'/'test_value.py').write_text('import unittest\nfrom value import value\nclass Check(unittest.TestCase):\n    def test_value(self):\n        self.assertEqual(value(), 2)\n')
    failed = confirm(agent, command(agent, '/test project'))
    assert not failed.success
    assert confirm(agent, command(agent, '/review propose project/value.py project/candidate.py')).success
    passed = confirm(agent, command(agent, '/test project'))
    assert passed.success, passed.message


class ContractClient:
    def __init__(self, data=None, pages=None):
        self.data, self.pages, self.calls = data, pages or {}, []
        self.checkpoint = lambda: None
    def json(self, url):
        self.checkpoint(); self.calls.append(url)
        return self.data
    def request(self, url):
        self.checkpoint(); self.calls.append(url)
        value = self.pages[url]
        if isinstance(value, Exception):
            raise value
        return value


def test_wikimedia_contract_validates_sources():
    client = ContractClient({'query': {'search': [{'title': 'Python', 'pageid': 42, 'snippet': '<span>Language</span>'}]}})
    rows = WikimediaSearch(client).search('Python pathlib')
    assert rows[0]['url'] == 'https://pt.wikipedia.org/?curid=42'
    assert rows[0]['snippet'] == 'Language'
    assert 'srsearch=Python+pathlib' in client.calls[0]
    client.data = {'query': {'search': [{'title': 'invalid', 'pageid': 'fake'}]}}
    with pytest.raises(FetchError):
        WikimediaSearch(client).search('query')


def test_document_robots_redirect_and_extraction():
    client = ContractClient(pages={
        'https://example.org/robots.txt': 'User-agent: *\nAllow: /',
        'https://example.org/start': FetchError('redirect', 302, '/page'),
        'https://example.org/page': '<html><title>Manual</title><script>hidden</script><p>Visible documentation text.</p></html>'})
    doc = PublicDocuments(client).fetch('https://example.org/start')
    assert doc.source.endswith('/page') and doc.title == 'Manual'
    assert 'hidden' not in str(doc.lines)
    client.pages['https://example.org/robots.txt'] = 'User-agent: *\nDisallow: /'
    with pytest.raises(FetchError):
        PublicDocuments(client).fetch('https://example.org/page')


def test_no_downgrade_or_credentials_redirect():
    client = ContractClient(pages={'https://example.org/robots.txt': '',
                                  'https://example.org/start': FetchError('redirect', 302, 'http://localhost/private')})
    with pytest.raises(ValueError):
        PublicDocuments(client).fetch('https://example.org/start')
    assert 'http://localhost/private' not in client.calls


def test_local_summary_compare_never_send_documents(agent, tmp_path):
    (tmp_path/'a.md').write_text('SQLite stores data in a local file and supports SQL transactions.\nIt can be used for local applications.\n')
    (tmp_path/'b.md').write_text('PostgreSQL runs as a server and supports SQL transactions.\nConnections reach a configured server.\n')
    client = ContractClient()
    agent.personal.knowledge = Knowledge(agent.personal, client)
    result = command(agent, '/research summarize a.md')
    assert result.success and 'L1:' in result.message
    result = command(agent, '/research compare a.md b.md')
    assert result.success and 'compartilhados' in result.message
    assert not client.calls


def test_web_disabled_and_malformed_do_not_fake_success(agent):
    agent.config.knowledge_web = 'disabled'
    assert not command(agent, '/research web Python').success
    assert not command(agent, '/research url https://example.org').success
    agent.config.knowledge_web = 'wikimedia'
    agent.personal.knowledge = Knowledge(agent.personal, ContractClient({'error': 'unavailable'}))
    result = command(agent, '/research web Python')
    assert not result.success and 'inventado' in result.message


@pytest.mark.parametrize('risk', ['diverged', 'ignored', 'protected'])
def test_pull_never_overwrites_risky_context(agent, repo, remote, tmp_path, risk):
    git(repo, 'push', 'origin', 'main')
    peer = tmp_path/'peer'
    git(tmp_path, 'clone', str(remote), str(peer))
    git(peer, 'config', 'user.name', 'Peer'); git(peer, 'config', 'user.email', 'peer@example.invalid')
    if risk == 'diverged':
        (repo/'local.txt').write_text('local history')
        git(repo, 'add', 'local.txt'); git(repo, 'commit', '-m', 'local commit')
        (peer/'remote.txt').write_text('remote history')
        git(peer, 'add', 'remote.txt')
    elif risk == 'ignored':
        (repo/'.git'/'info'/'exclude').write_text('private.txt\n')
        (repo/'private.txt').write_text('local contents must survive')
        (peer/'private.txt').write_text('remote replacement')
        git(peer, 'add', 'private.txt')
    else:
        (peer/'.env').write_text('test configuration')
        git(peer, 'add', '.env')
    git(peer, 'commit', '-m', 'remote change'); git(peer, 'push', 'origin', 'main')
    before = git(repo, 'rev-parse', 'HEAD')
    result = confirm(agent, command(agent, '/git pull repo origin main'))
    assert not result.success and result.status == 'partial', result.message
    assert git(repo, 'rev-parse', 'HEAD') == before
    if risk == 'ignored':
        assert (repo/'private.txt').read_text() == 'local contents must survive'
    if risk == 'protected':
        assert not (repo/'.env').exists()


def test_undo_invalid_original_is_labeled_honestly(agent, tmp_path):
    (tmp_path/'bad.py').write_text('if :\n')
    (tmp_path/'fixed.py').write_text('value = 1\n')
    assert confirm(agent, command(agent, '/review propose bad.py fixed.py')).success
    undo = next(iter(agent.personal.plans))
    result = command(agent, '/confirm '+undo)
    assert result.success and 'problemas anteriores' in result.message
    assert (tmp_path/'bad.py').read_text() == 'if :\n'
