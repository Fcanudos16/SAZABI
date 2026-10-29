"""Small explicit Git command set. Every mutation uses a guarded one-shot plan."""
import hashlib
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

from core.processes import run
from skills.base import SkillResult, ExecutionStopped
from utils.logger import redact

PREFIX = ['git', '--no-pager', '-c', 'core.fsmonitor=false', '-c', 'core.hooksPath=/dev/null',
          '-c', 'commit.gpgSign=false', '-c', 'submodule.recurse=false', '-c', 'protocol.ext.allow=never',
          '-c', 'push.followTags=false', '-c', 'gc.auto=0']
USAGE = ('/git status|branches|log|diff|message pasta; /git add pasta arquivo [...]; '
         '/git commit pasta "mensagem"; /git branch pasta nome; /git push|pull pasta remoto branch')


class GitSkill:
    def __init__(self, service):
        self.service, self.policy = service, service.policy

    def call(self, root, args, context, allowed=(0,)):
        output = run(PREFIX+args, root, context)
        if output.code not in allowed:
            raise ValueError('Git não concluiu a operação:\n'+redact(output.stderr.decode('utf-8', 'replace')[:4000]))
        return output.stdout

    def root(self, value, context):
        root = self.policy.path(value)
        if not root.is_dir():
            raise ValueError('Informe a raiz do repositório.')
        actual = self.call(root, ['rev-parse', '--show-toplevel'], context).decode('utf-8', 'strict').strip()
        if Path(actual).resolve() != root:
            raise ValueError('Informe a raiz exata do repositório: '+actual)
        return root

    def writable(self, root, context):
        metadata = root/'.git'
        if not metadata.is_dir() or metadata.is_symlink() or getattr(metadata, 'is_junction', lambda: False)():
            raise ValueError('Escrita requer checkout normal; worktrees e .git redirecionado não são suportados.')
        for name in ('index', 'HEAD', 'config', 'objects', 'refs'):
            path = metadata/name
            if path.is_symlink() or getattr(path, 'is_junction', lambda: False)():
                raise ValueError('Metadados Git redirecionados; operação recusada.')
        if any((metadata/name).exists() for name in ('MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-apply', 'rebase-merge', 'index.lock')):
            raise ValueError('Há operação Git ou lock pendente; conclua-a antes de continuar.')
        self.filters(root, context)

    def filters(self, root, context, names=None, source=None):
        if names is None:
            names = self.names(root, ['ls-files', '--cached', '--others', '--exclude-standard', '-z'], context)
        if len(names) > 5000:
            raise ValueError('Repositório excedeu 5.000 arquivos.')
        for offset in range(0, len(names), 50):
            argv = ['check-attr', '-z'] + (['--source='+source] if source else []) + ['filter', '--', *names[offset:offset+50]]
            values = self.call(root, argv, context).split(b'\0')
            if any(value not in (b'unspecified', b'unset') for value in values[2::3]):
                raise ValueError('Arquivos com filtro Git ativo (incluindo LFS) exigem fluxo externo revisado.')

    def names(self, root, args, context):
        data = self.call(root, args, context)
        return [name.decode('utf-8', 'strict') for name in data.split(b'\0') if name]

    def state(self, root, context):
        self.writable(root, context)
        digest = hashlib.sha256()
        for args, allowed in ((['rev-parse', '--verify', 'HEAD'], (0, 128)), (['symbolic-ref', '-q', 'HEAD'], (0, 1)),
                              (['status', '--porcelain=v1', '-z', '--untracked-files=all'], (0,)),
                              (['config', '--null', '--list'], (0,))):
            digest.update(self.call(root, args, context, allowed))
        index = root/'.git'/'index'
        if index.exists():
            if index.stat().st_size > 20_000_000:
                raise ValueError('Índice Git excedeu o limite.')
            digest.update(index.read_bytes())
        names = self.names(root, ['ls-files', '--cached', '--others', '--exclude-standard', '-z'], context)
        if len(names) > 5000:
            raise ValueError('Repositório excedeu 5.000 arquivos; revisão manual necessária.')
        for offset in range(0, len(names), 50):
            # Includes effective attributes from info/attributes and global files,
            # which can change staging conversions without changing tracked files.
            digest.update(self.call(root, ['check-attr', '-z', '--all', '--', *names[offset:offset+50]], context))
        for name in sorted(set(names)):
            path = self.policy.path(str(root/name), exists=False)
            if not path.is_relative_to(root):
                raise ValueError('Caminho Git fora do repositório.')
            digest.update(name.encode('utf-8'))
            if path.exists():
                if not path.is_file():
                    raise ValueError('Submódulos não suportados neste fluxo.')
                digest.update(self.service.digest(path, context).encode())
        return digest.hexdigest()

    def branch(self, root, name, context):
        if not name or name.startswith('-') or name == 'HEAD':
            raise ValueError('Nome de branch inválido.')
        self.call(root, ['check-ref-format', '--branch', name], context)
        return name

    def remote(self, root, name, action, context):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', name) or name.startswith('-'):
            raise ValueError('Use um remoto configurado pelo nome.')
        flags = ['--push'] if action == 'push' else []
        urls = self.call(root, ['remote', 'get-url', *flags, '--all', name], context).decode().splitlines()
        if len(urls) != 1:
            raise ValueError('A operação exige um único destino remoto.')
        url = urls[0]
        if '://' in url:
            parsed = urlsplit(url)
            if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError('Use HTTPS sem credenciais embutidas ou repositório local autorizado.')
        else:
            # No arbitrary SSH commands, ext:: transport or implicit scp syntax.
            path = Path(url)
            if not path.is_absolute():
                path = root/path
            url = str(self.policy.path(str(path)))
        return url

    def remote_head(self, root, url, branch, context):
        rows = self.call(root, ['ls-remote', '--heads', '--', url, 'refs/heads/'+branch], context).decode().splitlines()
        if not rows:
            return ''
        if len(rows) != 1 or not re.fullmatch(r'[a-f0-9]{40,64}\s+refs/heads/'+re.escape(branch), rows[0]):
            raise ValueError('Resposta de referência remota inválida.')
        return rows[0].split()[0]

    def execute(self, args, context):
        if len(args) < 2:
            raise ValueError(USAGE)
        action, folder, *rest = args
        root = self.root(folder, context)
        read = {'status': ['status', '--short'], 'branches': ['branch', '--list'], 'log': ['log', '-10', '--oneline'],
                'diff': ['diff', '--no-ext-diff', '--no-textconv']}
        if action in read and not rest:
            self.filters(root, context)
            text = self.call(root, read[action], context).decode('utf-8', 'replace')
            return self.service.ok(text[:16000] or 'Sem alterações.')
        if action == 'message' and not rest:
            names = self.names(root, ['diff', '--cached', '--name-only', '-z'], context)
            return self.service.ok('Sugestão baseada apenas nos arquivos staged: Atualiza '+', '.join(names[:5]) if names else 'Nenhum arquivo staged.')
        if action not in ('add', 'commit', 'branch', 'push', 'pull'):
            raise ValueError(USAGE)
        state = self.state(root, context)
        payload = {'root': str(root), 'state': state, 'action': action}
        preview = f'Repositório: {root}\nAção: {action}\nHooks e assinatura de commit não serão executados neste fluxo.\n'
        if action == 'add' and 1 <= len(rest) <= 50:
            names = []
            for name in rest:
                path = self.policy.path(str(root/name), exists=False)
                if not path.is_relative_to(root) or path.is_dir():
                    raise ValueError('Escolha arquivos individuais dentro do repositório; não use pasta ou curinga.')
                names.append(path.relative_to(root).as_posix())
            payload['argv'] = ['add', '--', *names]
            preview += 'Arquivos a adicionar ao índice (inclui exclusões já feitas):\n'+'\n'.join(names)
            diff = self.call(root, ['diff', '--no-ext-diff', '--no-textconv', '--', *names], context).decode('utf-8', 'replace')
            tracked = set(self.names(root, ['ls-files', '-z'], context))
            for name in names:
                if name not in tracked:
                    path = self.policy.path(str(root/name))
                    if path.stat().st_size > 100_000:
                        diff += f'\nNovo arquivo: {name}; bytes={path.stat().st_size}; SHA256={self.service.digest(path, context)}\n'
                    else:
                        raw = path.read_bytes()
                        diff += '\nNovo arquivo: '+name+'\n'+(raw.decode('utf-8', 'replace') if b'\0' not in raw else 'Binário SHA256='+hashlib.sha256(raw).hexdigest())
            if len(diff) > 12000:
                raise ValueError('Prévia excedeu 12.000 caracteres; selecione menos arquivos.')
            if redact(diff) != diff:
                raise ValueError('Possível credencial no conteúdo; revise antes de adicionar.')
            preview += '\nAlterações a adicionar:\n'+diff
        elif action == 'commit' and len(rest) == 1 and rest[0].strip():
            names = self.names(root, ['diff', '--cached', '--name-only', '-z'], context)
            if not names:
                raise ValueError('Nenhuma alteração staged para commit.')
            for name in names:
                self.policy.path(str(root/name), exists=False)
            diff = self.call(root, ['diff', '--cached', '--no-ext-diff', '--no-textconv'], context).decode('utf-8', 'replace')
            if len(diff) > 12000 or redact(diff) != diff:
                raise ValueError('Diff staged excedeu a prévia ou contém possível credencial; revise no Git antes de continuar.')
            payload['argv'] = ['commit', '--no-verify', '-m', rest[0]]
            preview += 'Mensagem: '+rest[0]+'\nArquivos staged:\n'+'\n'.join(names)+'\n'+diff[:12000]
        elif action == 'branch' and len(rest) == 1:
            branch = self.branch(root, rest[0], context)
            payload['argv'] = ['branch', '--', branch]
            head = self.call(root, ['rev-parse', 'HEAD'], context).decode().strip()
            preview += 'Criar branch '+branch+' em '+head+', sem trocar o checkout.'
        elif action in ('push', 'pull') and len(rest) == 2:
            remote, branch = rest
            self.branch(root, branch, context)
            local = self.call(root, ['symbolic-ref', '--short', 'HEAD'], context).decode().strip()
            if local != branch:
                raise ValueError('A branch solicitada deve ser a branch local atual: '+local)
            if action == 'pull' and self.call(root, ['status', '--porcelain'], context).strip():
                raise ValueError('Pull exige árvore e índice limpos; preserve suas alterações primeiro.')
            url = self.remote(root, remote, action, context)
            expected = self.remote_head(root, url, branch, context)
            if action == 'pull' and not expected:
                raise ValueError('Branch remota inexistente.')
            payload.update(url=url, branch=branch, expected=expected)
            head = self.call(root, ['rev-parse', 'HEAD'], context).decode().strip()
            preview += f'Destino: {url}\nBranch: {branch}\nHEAD local: {head}\nHEAD remoto observado: {expected or "inexistente"}\n'
            preview += ('Publicará o histórico de commits da branch, sem force e sem tags.' if action == 'push' else
                        'Buscará a branch e atualizará somente por fast-forward; recusará divergências e arquivos ignorados em conflito.')
        else:
            raise ValueError(USAGE)
        if self.state(root, context) != state:
            raise ValueError('Repositório mudou durante a prévia; solicite novamente.')
        return self.service.plan('git', payload, preview)

    def apply(self, payload, context):
        root = self.root(payload['root'], context)
        if self.state(root, context) != payload['state']:
            raise ValueError('HEAD, índice, configuração ou arquivos mudaram; solicite nova prévia Git.')
        action = payload['action']
        if action not in ('push', 'pull'):
            output = self.call(root, payload['argv'], context)
            return self.service.ok('Git '+action+' concluído.\n'+output.decode('utf-8', 'replace')[:12000])
        url, branch = payload['url'], payload['branch']
        if self.remote_head(root, url, branch, context) != payload['expected']:
            raise ValueError('A branch remota mudou; solicite nova prévia.')
        if action == 'push':
            output = self.call(root, ['push', '--porcelain', '--no-verify', '--', url, 'HEAD:refs/heads/'+branch], context)
            return self.service.ok('Push concluído para a branch aprovada.\n'+output.decode('utf-8', 'replace')[:12000])
        fetched = False
        try:
            self.call(root, ['fetch', '--no-tags', '--no-recurse-submodules', '--', url, 'refs/heads/'+branch], context)
            fetched = True
            head = self.call(root, ['rev-parse', 'FETCH_HEAD'], context).decode().strip()
            if head != payload['expected'] or self.state(root, context) != payload['state']:
                raise ValueError('Contexto mudou durante fetch; checkout não atualizado.')
            # Refuse incoming links/submodules and protected paths before writing the tree.
            tree = self.call(root, ['ls-tree', '-r', '-z', 'FETCH_HEAD'], context)
            incoming = []
            for row in tree.split(b'\0'):
                if not row:
                    continue
                meta, name = row.split(b'\t', 1)
                if meta.split()[0] not in (b'100644', b'100755'):
                    raise ValueError('Árvore remota contém links/submódulos; checkout não atualizado.')
                self.policy.path(str(root/name.decode('utf-8')), exists=False)
                incoming.append(name.decode('utf-8'))
            self.filters(root, context, incoming, 'FETCH_HEAD')
            self.call(root, ['merge', '--ff-only', '--no-edit', '--no-overwrite-ignore', 'FETCH_HEAD'], context)
            return self.service.ok('Pull fast-forward concluído no commit '+head+'.')
        except (ValueError, OSError, ExecutionStopped) as error:
            if not fetched:
                raise
            return SkillResult(False, 'git', 'partial', 'Fetch realizado; pull não concluído. Confira /git status.\n'+redact(str(error)))
