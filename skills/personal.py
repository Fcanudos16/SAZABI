"""Local skills using the established SkillResult/SkillContext contracts."""
from collections import defaultdict
from datetime import date, datetime
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time
import uuid

from core.local_policy import LocalPolicy
from database.personal import PersonalStore
from skills.base import SkillResult, ExecutionStopped
from utils.timeutils import now_iso
from utils.logger import redact

COMMANDS = {
    'help': 'Comandos ativos e exemplos',
    'task': 'Tarefas: add, list, edit, done, export',
    'files': 'Arquivos: find, duplicates, organize, move',
    'project': 'Inspecionar estrutura e dependências locais',
    'test': 'Preparar testes Python com confirmação',
    'review': 'Revisar riscos, propor alterações e desfazer',
    'git': 'Consultar Git e preparar escritas com confirmação',
    'run': 'Listar ou preparar rotinas autorizadas',
    'research': 'Pesquisa local, web, resumos e comparação',
    'search': 'Alias de pesquisa técnica local',
    'history': 'Histórico operacional persistente',
    'settings': 'Consultar limites locais, sem credenciais',
    'backup': 'Backup SQLite verificado, sem sobrescrita',
    'confirm': 'Confirmar exatamente a prévia identificada',
    'cancel': 'Descartar uma prévia pendente',
}

USAGE = '''SAZABI — agente pessoal local
/task add "Título" [priority=alta] [due=2026-12-31] [category=pessoal] [project=Casa]
/task list [all|pending|overdue] · /task edit ID title="Novo título" · /task done ID
/task export arquivo.json
/files find pasta [name=texto] [ext=.py] [min=0] [max=100000] [after=2026-01-01]
/files duplicates pasta · /files organize pasta · /files move "origem" "destino"
/project pasta · /review pasta · /test pasta
/git status|branches|log|diff pasta
/git add pasta arquivo · /git commit pasta "mensagem" · /git branch pasta nome
/git push|pull pasta remoto branch · /git message pasta
/review propose original candidato · /review fix arquivo bare-except
/research "termo" pasta · /search "termo" pasta
/research web "consulta" · /research url https://fonte/documento
/research summarize arquivo · /research compare fonte1 fonte2
/run [nome] · /confirm TOKEN · /cancel TOKEN
/history · /settings · /backup · /ai
Use aspas em caminhos com espaços. Web consulta Wikimedia; url lê páginas HTTPS públicas.
Testes e rotinas executam código local: revise a prévia antes de confirmar.'''


def words(text):
    lexer = shlex.shlex(text, posix=True)
    lexer.whitespace_split = True
    lexer.commenters = ''
    lexer.escape = ''  # Preserve Windows path separators.
    return list(lexer)


def options(tokens, allowed):
    result = {}
    for token in tokens:
        key, separator, value = token.partition('=')
        if not separator or key not in allowed or key in result:
            raise ValueError('Parâmetro inválido: use '+', '.join(sorted(allowed))+'.')
        result[key] = value
    return result


class PersonalService:
    def __init__(self, agent):
        self.agent = agent
        self.store = PersonalStore(agent.db)
        self.policy = LocalPolicy(agent.config.local_roots, (agent.db.path, agent.db.path+'-wal', agent.db.path+'-shm', agent.config.log_file))
        self.plans = {}
        from skills.git_local import GitSkill
        from skills.code_review import CodeReview
        from research.knowledge import Knowledge
        self.git = GitSkill(self)
        self.review = CodeReview(self)
        self.knowledge = Knowledge(self)

    def execute(self, name, arguments, context):
        identity = self.store.start(name)  # Never persist raw command arguments.
        try:
            context.checkpoint()
            if redact(arguments) != arguments:
                raise ValueError('Conteúdo semelhante a credencial recusado; configure segredos somente no .env.')
            result = self.dispatch(name, words(arguments), context)
        except ExecutionStopped as error:
            result = SkillResult(False, name, error.status, 'Operação cancelada ou tempo limite atingido. Confira o histórico antes de repetir.')
        except (ValueError, OSError, subprocess.SubprocessError) as error:
            message = str(error) if isinstance(error, ValueError) else 'Operação local falhou; verifique caminhos, permissões e ferramentas.'
            result = SkillResult(False, name, 'failed', redact(message))
        except Exception:
            result = SkillResult(False, name, 'failed', 'A habilidade falhou; as demais funções continuam disponíveis.')
        result.message = redact(result.message)
        stored_message = 'Histórico consultado.' if name == 'history' else result.message
        self.store.finish(identity, 'planned' if result.status == 'needs_confirmation' else result.status, stored_message)
        if result.status == 'needs_confirmation':
            self.plans[result.data['token']]['operation'] = identity
        return result

    def ok(self, message):
        if not isinstance(message, str):
            message = json.dumps(message, ensure_ascii=False, indent=2)
        return SkillResult(True, 'personal', 'completed', message)

    def plan(self, action, payload, preview):
        if len(self.plans) >= 20:
            raise ValueError('Cancele uma prévia pendente antes de criar outra.')
        token = uuid.uuid4().hex[:12]
        self.plans[token] = dict(action=action, payload=payload, expires=time.monotonic()+300)
        return SkillResult(False, 'personal', 'needs_confirmation',
                           preview+f'\nVálido por 5 minutos. /confirm {token} ou /cancel {token}', {'token': token})

    def dispatch(self, name, args, context):
        if name in ('help', 'settings', 'history') and args:
            raise ValueError('Use /'+name+' sem argumentos.')
        if name == 'help':
            return self.ok(USAGE)
        if name == 'settings':
            return self.ok({'local_roots': [str(p) for p in self.policy.roots], 'web': self.agent.config.knowledge_web,
                            'process_timeout_seconds': 60, 'scan_limit': 5000, 'routines': list(self.agent.config.local_routines)})
        if name == 'history':
            return self.ok(self.store.history())
        if name == 'backup':
            if args:
                raise ValueError('Use /backup sem argumentos.')
            return self.ok('Backup verificado: '+self.agent.db.backup())
        if name in ('confirm', 'cancel'):
            if len(args) != 1 or args[0] not in self.plans:
                raise ValueError('Prévia inexistente, consumida ou de outra sessão.')
            plan = self.plans.pop(args[0])
            status, message = 'failed', 'Prévia expirada ou execução interrompida; confira os efeitos.'
            try:
                if name == 'cancel':
                    status, message = 'cancelled', 'Prévia cancelada; nenhuma ação executada.'
                    return self.ok(message)
                if time.monotonic() > plan['expires']:
                    raise ValueError('Prévia expirada; solicite outra.')
                result = self.apply(plan, context)
                status, message = result.status, result.message
                return result
            finally:
                self.store.finish(plan['operation'], status, message)
        if name == 'task':
            return self.task(args)
        if name == 'files':
            return self.files(args, context)
        if name in ('research', 'search'):
            result = self.knowledge.execute(args, context)
            if result is not None:
                return result
            if len(args) != 2:
                raise ValueError('Use /research "termo" pasta ou /research web "consulta". Nenhuma API foi chamada.')
            if not args[0].strip():
                raise ValueError('Informe um termo de pesquisa.')
            rows = []
            for path in self.policy.files(args[1], context):
                if path.suffix.lower() not in ('.md', '.txt', '.py', '.rst', '.log') or path.stat().st_size > 1_000_000:
                    continue
                for number, line in enumerate(path.read_text(encoding='utf-8', errors='replace').splitlines(), 1):
                    if args[0].casefold() in line.casefold():
                        rows.append(f'{path}:{number}: {line[:300]}')
                        if len(rows) >= 50:
                            return self.ok('Trechos locais (limite de 50; não é uma síntese):\n'+'\n'.join(rows))
            return self.ok('\n'.join(rows) or 'Nenhum trecho encontrado nos documentos locais suportados.')
        if name == 'review':
            return self.review.execute(args, context)
        if name in ('project', 'test'):
            if len(args) != 1:
                raise ValueError(f'Use /{name} "pasta autorizada".')
            root = self.policy.path(args[0])
            if not root.is_dir():
                raise ValueError('Selecione uma pasta.')
            if name == 'test':
                argv = [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests']
                if (root/'run_tests.py').is_file():
                    argv = [sys.executable, 'run_tests.py']
                elif (root/'pytest.ini').is_file():
                    argv = [sys.executable, '-m', 'pytest', 'tests']
                if not (root/'tests').is_dir():
                    raise ValueError('Pasta tests ausente. Configure uma rotina explícita para outro executor.')
                return self.process_plan(argv, root, context)
            paths = list(self.policy.files(str(root), context))
            if name == 'project':
                return self.ok({'root': str(root), 'count': len(paths), 'files': [str(p.relative_to(root)) for p in paths[:200]],
                                'limit_display': 200, 'configs': [str(p.relative_to(root)) for p in paths if p.name in
                                ('pyproject.toml', 'requirements.txt', 'package.json', 'Cargo.toml', 'pytest.ini')]})
        if name == 'git':
            return self.git.execute(args, context)
        if name == 'run':
            routines = self.agent.config.local_routines
            if not args:
                return self.ok({'routines': list(routines), 'configuration': 'LOCAL_ROUTINES_JSON no .env; argv e cwd explícitos'})
            if len(args) != 1 or args[0] not in routines:
                raise ValueError('Rotina não autorizada. Consulte /run.')
            routine = routines[args[0]]
            if not isinstance(routine, dict) or set(routine) != {'argv', 'cwd'}:
                raise ValueError('Rotina requer apenas argv e cwd.')
            argv = routine['argv']
            if not isinstance(argv, list) or not argv or not all(isinstance(a, str) and a and '\x00' not in a for a in argv):
                raise ValueError('argv inválido.')
            return self.process_plan(argv, self.policy.path(routine['cwd']), context)
        raise ValueError('Comando indisponível. Use /help.')

    def task(self, args):
        if not args:
            args = ['list', 'pending']
        action, *rest = args
        db = self.agent.db
        if action == 'list' and len(rest) <= 1:
            return self.ok(self.store.tasks(rest[0] if rest else 'pending'))
        if action in ('add', 'edit') and rest:
            fields = options(rest[1:], {'title', 'priority', 'due', 'category', 'project'})
            if action == 'add':
                fields['title'] = rest[0]
            if 'priority' in fields and fields['priority'] not in ('baixa', 'normal', 'alta'):
                raise ValueError('priority=baixa|normal|alta')
            if 'due' in fields:
                fields['due'] = date.fromisoformat(fields['due']).isoformat() if fields['due'] else None
            if 'title' in fields and not fields['title'].strip():
                raise ValueError('Título obrigatório.')
            if any(len(v) > 300 for v in fields.values() if isinstance(v, str)):
                raise ValueError('Limite de 300 caracteres por campo.')
            fields['updated_at'] = now_iso()
            if action == 'add':
                fields['created_at'] = now_iso()
                identity = db.execute('INSERT INTO personal_tasks('+','.join(fields)+') VALUES ('+','.join('?' for _ in fields)+')', fields.values()).lastrowid
            else:
                identity = int(rest[0])
                if not db.query_one('SELECT id FROM personal_tasks WHERE id=?', (identity,)):
                    raise ValueError('Tarefa inexistente.')
                db.execute('UPDATE personal_tasks SET '+','.join(k+'=?' for k in fields)+' WHERE id=?', [*fields.values(), identity])
            return self.ok(f'Tarefa #{identity} salva.')
        if action == 'done' and len(rest) == 1:
            changed = db.execute('UPDATE personal_tasks SET completed=1,updated_at=? WHERE id=?', (now_iso(), int(rest[0]))).rowcount
            if not changed:
                raise ValueError('Tarefa inexistente.')
            return self.ok('Tarefa concluída.')
        if action == 'export' and len(rest) == 1:
            path = self.policy.path(rest[0], exists=False)
            with path.open('x', encoding='utf-8') as stream:
                json.dump(self.store.tasks(), stream, ensure_ascii=False, indent=2)
            return self.ok('Tarefas exportadas: '+str(path))
        raise ValueError('Use /task add "Título", list, edit ID campo=valor, done ID ou export arquivo.json.')

    def digest(self, path, context):
        if path.stat().st_size > 100_000_000:
            raise ValueError('Hash limitado a arquivos de até 100 MB.')
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            while chunk := stream.read(1024*1024):
                context.checkpoint()
                digest.update(chunk)
        return digest.hexdigest()

    def files(self, args, context):
        if len(args) < 2:
            raise ValueError('Use /files find|duplicates|organize pasta ou /files move origem destino.')
        action, root, *rest = args
        if action == 'move' and len(rest) == 1:
            source, target = self.policy.path(root), self.policy.path(rest[0], exists=False)
            if not source.is_file() or target.exists() or not target.parent.is_dir():
                raise ValueError('Origem deve ser arquivo; destino novo em pasta existente.')
            moves = [(str(source), str(target), self.digest(source, context))]
            return self.plan('moves', moves, '1 arquivo — prévia:\n'+str(source)+' -> '+str(target))
        if action not in ('find', 'duplicates', 'organize'):
            raise ValueError('Ação desconhecida. Use /help.')
        filters = options(rest, {'name', 'ext', 'min', 'max', 'after'}) if action == 'find' else {}
        if rest and action != 'find':
            raise ValueError('Parâmetros extras não aceitos.')
        minimum, maximum = int(filters.get('min', '0')), int(filters.get('max', str(2**63)))
        after = date.fromisoformat(filters['after']) if 'after' in filters else None
        paths = list(self.policy.files(root, context))
        if action == 'find':
            selected = []
            for path in paths:
                stat = path.stat()
                if (filters.get('name', '').casefold() in path.name.casefold() and
                    ('ext' not in filters or path.suffix.casefold() == filters['ext'].casefold()) and
                    minimum <= stat.st_size <= maximum and
                    (after is None or datetime.fromtimestamp(stat.st_mtime).date() >= after)):
                    selected.append({'path': str(path), 'bytes': stat.st_size, 'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()})
            return self.ok({'total': len(selected), 'files': selected[:200], 'display_limit': 200})
        if action == 'duplicates':
            sizes, hashes = defaultdict(list), defaultdict(list)
            for path in paths:
                sizes[path.stat().st_size].append(path)
            for group in sizes.values():
                if len(group) > 1:
                    for path in group:
                        hashes[self.digest(path, context)].append(str(path))
            return self.ok({'duplicates_sha256': [group for group in hashes.values() if len(group) > 1]})
        root = self.policy.path(root)
        moves = []
        for source in paths:
            if source.parent != root:
                continue  # Organize only immediate children, never recursively reshuffle.
            folder = source.suffix.lower().lstrip('.') or 'sem-extensao'
            if not folder.isalnum():
                continue
            target = self.policy.path(str(root/folder/source.name), exists=False)
            if target.exists():
                raise ValueError('Destino já existe; nenhuma alteração realizada.')
            moves.append((str(source), str(target), self.digest(source, context)))
            if len(moves) > 100:
                raise ValueError('Organização limitada a 100 arquivos; selecione pasta menor.')
        if not moves:
            return self.ok('Nenhum arquivo para organizar.')
        return self.plan('moves', moves, f'{len(moves)} arquivos — prévia:\n'+'\n'.join(a+' -> '+b for a,b,_ in moves))

    def snapshot(self, root, context):
        return [(str(p), self.digest(p, context)) for p in self.policy.files(str(root), context)
                if p.suffix.lower() in ('.py', '.ps1', '.cmd', '.bat', '.json', '.toml', '.ini', '.yaml', '.yml', '.txt')
                and not set(p.relative_to(root).parts) & {'data', 'logs', 'reports'}]

    def process_plan(self, argv, root, context):
        payload = {'argv': argv, 'cwd': str(root), 'snapshot': self.snapshot(root, context)}
        return self.plan('process', payload, 'Código local será executado com os privilégios do usuário, sem sandbox.\n'
                         'Pode alterar arquivos e acessar a rede. Limite de 60 segundos.\nPasta: '+str(root)+'\nargv: '+json.dumps(argv, ensure_ascii=False))

    def apply(self, plan, context):
        if plan['action'] == 'git':
            return self.git.apply(plan['payload'], context)
        if plan['action'] == 'patch':
            return self.review.apply(plan['payload'], context)
        if plan['action'] == 'process':
            payload = plan['payload']
            root = self.policy.path(payload['cwd'])
            if self.snapshot(root, context) != payload['snapshot']:
                raise ValueError('Arquivos mudaram desde a prévia. Solicite outra aprovação.')
            return self.process(payload['argv'], root, context)
        moves = plan['payload']
        for old, new, digest in moves:
            source, target = self.policy.path(old), self.policy.path(new, exists=False)
            if target.exists() or self.digest(source, context) != digest:
                raise ValueError('Origem ou destino mudou; nenhuma operação iniciada.')
        completed = []
        try:
            for old, new, digest in moves:
                context.checkpoint()
                source, target = self.policy.path(old), self.policy.path(new, exists=False)
                target.parent.mkdir(exist_ok=True)
                # Windows rename refuses overwrite. On other hosts fail closed.
                if os.name != 'nt':
                    raise ValueError('Movimentação protegida disponível somente no Windows.')
                source.rename(target)
                completed.append((new, old, digest))
        except (OSError, ValueError, ExecutionStopped):
            # Persist exact successful effects, even if cancellation interrupts a batch.
            self.store.finish(plan['operation'], 'partial', 'Movidos antes da falha: '+json.dumps(completed, ensure_ascii=False))
            return SkillResult(False, 'files', 'partial', 'Lote interrompido. Movimentos executados (destino, origem, hash):\n'+json.dumps(completed, ensure_ascii=False))
        reverse = self.plan('moves', completed, 'Movimentos concluídos. Prévia para desfazer:\n'+'\n'.join(a+' -> '+b for a,b,_ in completed))
        # Undo has its own journal identity; completion is never recorded as just planned.
        undo_id = self.store.start('files.undo')
        self.store.finish(undo_id, 'planned', reverse.message)
        self.plans[reverse.data['token']]['operation'] = undo_id
        return self.ok(reverse.message)

    def process(self, argv, root, context):
        from core.processes import run
        root = self.policy.path(str(root))
        if not root.is_dir():
            raise ValueError('Pasta de execução inválida.')
        output = run(argv, root, context)
        text = (output.stdout+output.stderr)[:16000].decode('utf-8', errors='replace')
        return SkillResult(output.code == 0, 'process', 'completed' if output.code == 0 else 'failed',
                           f'Código de saída: {output.code}\n'+redact(text)+'\n(saída limitada a 16 KB)')


class PersonalSkill:
    enabled = True
    dependencies = ()
    permissions = ('authorized_local_roots', 'contextual_confirmation_for_execution')

    def __init__(self, name, service):
        self.name, self.service = name, service
        self.description = COMMANDS[name]

    def execute(self, query, context):
        return self.service.execute(self.name, query, context)
