"""Deterministic Python risk review and reviewed, reversible file replacement."""
import ast
import difflib
import hashlib
import io
import os
import re
import tempfile
import tokenize
from pathlib import Path

from utils.logger import redact


def decode(raw):
    encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
    return raw.decode(encoding), encoding


def scan(text, filename):
    findings = []
    def add(node, rule, severity, message, recommendation):
        findings.append(dict(file=filename, line=node.lineno, rule=rule, severity=severity,
                             evidence=message, recommendation=recommendation))
    try:
        tree = ast.parse(text, filename=filename)
    except SyntaxError as error:
        return [dict(file=filename, line=error.lineno or 1, rule='syntax', severity='error',
                     evidence=error.msg, recommendation='Corrigir a sintaxe e executar os testes do projeto.')]
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name] = item.name
        elif isinstance(node, ast.ImportFrom):
            for item in node.names:
                aliases[item.asname or item.name] = (node.module or '')+'.'+item.name
    def qualified(node):
        if isinstance(node, ast.Name):
            return aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            return qualified(node.value)+'.'+node.attr
        return ''
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for default in node.args.defaults + [d for d in node.args.kw_defaults if d is not None]:
                if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    add(default, 'mutable-default', 'warning', 'Argumento padrão mutável compartilhado entre chamadas.',
                        'Avaliar usar None e criar uma coleção por chamada; testar chamadas consecutivas.')
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                add(node, 'bare-except', 'warning', 'except sem tipo captura inclusive interrupções do usuário.',
                    'Escolher exceções específicas; /review fix arquivo bare-except prepara except Exception para revisão.')
            if isinstance(node.type, ast.Name) and node.type.id in ('Exception', 'BaseException') and all(isinstance(n, ast.Pass) for n in node.body):
                add(node, 'swallowed-error', 'warning', 'Exceção ampla descartada sem tratamento.',
                    'Registrar um erro sanitizado ou retornar falha; não indicar sucesso.')
        if isinstance(node, ast.Call):
            name = qualified(node.func)
            keywords = {k.arg: k.value for k in node.keywords}
            if name in ('eval', 'exec', 'builtins.eval', 'builtins.exec'):
                add(node, 'dynamic-code', 'high', 'Execução dinâmica de código.', 'Remover ou validar estritamente a origem; nunca executar respostas de modelos.')
            if name.startswith('subprocess.') and isinstance(keywords.get('shell'), ast.Constant) and keywords['shell'].value is True:
                add(node, 'shell', 'high', 'Processo com shell=True.', 'Preferir argv explícito e shell=False; revisar a origem dos argumentos.')
            if name.startswith(('requests.', 'httpx.')) and isinstance(keywords.get('verify'), ast.Constant) and keywords['verify'].value is False:
                add(node, 'tls-disabled', 'high', 'Verificação TLS desativada.', 'Restaurar verificação de certificado e corrigir a cadeia de confiança.')
            if name in ('pickle.load', 'pickle.loads', 'yaml.unsafe_load', 'tempfile.mktemp'):
                add(node, 'unsafe-api', 'high', 'API que requer origem confiável ou proteção adicional: '+name,
                    'Usar formato não executável ou criação exclusiva de temporário, conforme o caso.')
            if isinstance(node.func, ast.Attribute) and node.func.attr in ('execute', 'executemany') and node.args:
                query = node.args[0]
                if isinstance(query, (ast.JoinedStr, ast.BinOp)) or (isinstance(query, ast.Call) and isinstance(query.func, ast.Attribute) and query.func.attr == 'format'):
                    add(node, 'dynamic-sql', 'warning', 'SQL montado dinamicamente; risco depende da origem dos valores.',
                        'Usar parâmetros para valores e allowlist para identificadores; verificar antes de alterar.')
        if isinstance(node, ast.Try):
            for statement in node.finalbody:
                if isinstance(statement, (ast.Return, ast.Break, ast.Continue)):
                    add(statement, 'finally-control', 'warning', 'Controle de fluxo em finally pode ocultar uma falha.',
                        'Mover retorno/controle para fora do finally e testar o caminho de erro.')
    return findings


class CodeReview:
    def __init__(self, service):
        self.service, self.policy = service, service.policy

    def read(self, value):
        path = self.policy.path(value)
        if not path.is_file() or path.stat().st_size > 1_000_000:
            raise ValueError('Selecione arquivo textual de até 1 MB.')
        raw = path.read_bytes()
        if b'\0' in raw:
            raise ValueError('Arquivo binário não suportado.')
        return path, raw

    def execute(self, args, context):
        if args and args[0] == 'propose' and len(args) == 3:
            target, original = self.read(args[1])
            _, replacement = self.read(args[2])
            return self.proposal(target, original, replacement, 'Versão candidata fornecida pelo usuário.')
        if args and args[0] == 'fix' and len(args) == 3 and args[2] == 'bare-except':
            path, raw = self.read(args[1])
            if path.suffix != '.py':
                raise ValueError('Correção disponível apenas para Python.')
            text, encoding = decode(raw)
            tree = ast.parse(text)
            lines = text.splitlines(keepends=True)
            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler) and node.type is None:
                    lines[node.lineno-1] = re.sub(r'^(\s*)except\s*:', r'\1except Exception:', lines[node.lineno-1], count=1)
            return self.proposal(path, raw, ''.join(lines).encode(encoding),
                                 'Proposta: deixar KeyboardInterrupt/SystemExit propagarem. Confirme somente se esse comportamento for desejado.')
        if len(args) != 1:
            raise ValueError('/review pasta|arquivo; /review propose original candidato; /review fix arquivo bare-except')
        root = self.policy.path(args[0])
        paths = [root] if root.is_file() else self.policy.files(str(root), context)
        findings, count, skipped = [], 0, 0
        for path in paths:
            context.checkpoint()
            if path.suffix != '.py':
                continue
            if path.stat().st_size > 1_000_000:
                skipped += 1
                continue
            try:
                text, _ = decode(path.read_bytes())
            except (SyntaxError, UnicodeError):
                skipped += 1
                continue
            count += 1
            findings.extend(scan(text, str(path)))
        rows = [f"{row['file']}:{row['line']} [{row['severity']}/{row['rule']}] {row['evidence']}\n  Sugestão: {row['recommendation']}" for row in findings[:100]]
        result = self.service.ok(f'Revisão estática: {count} arquivos Python; {skipped} não analisados; {len(findings)} achados.\n'
                                 'São indícios para revisão humana; nenhum teste foi executado e nenhum bug foi declarado corrigido.\n'+'\n'.join(rows))
        result.data['findings'] = findings[:100]
        return result

    def proposal(self, path, original, replacement, reason):
        if original == replacement:
            return self.service.ok('Nenhuma alteração proposta.')
        if path.suffix == '.py':
            before, _ = decode(original)
            after, _ = decode(replacement)
            try:
                ast.parse(after, filename=str(path))
            except SyntaxError as error:
                raise ValueError(f'Candidato Python com sintaxe inválida na linha {error.lineno}. Nenhuma alteração aplicada.') from None
        else:
            before, after = original.decode('utf-8'), replacement.decode('utf-8')
        diff = ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                            fromfile=str(path), tofile=str(path)+' (proposto)'))
        if len(diff) > 14000:
            raise ValueError('Diff excedeu a prévia completa de 14.000 caracteres; divida a alteração.')
        if redact(diff) != diff:
            raise ValueError('Diff contém possível credencial; remova o segredo antes de propor a alteração.')
        payload = dict(path=str(path), before=original, after=replacement,
                       digest=hashlib.sha256(original).hexdigest(), validation='syntax' if path.suffix == '.py' else 'text')
        return self.service.plan('patch', payload, reason+'\n'+diff+'\nAplicação exige confirmação; testes ainda não executados.')

    def apply(self, payload, context):
        path, original = self.read(payload['path'])
        if hashlib.sha256(original).hexdigest() != payload['digest']:
            raise ValueError('Arquivo mudou desde a proposta; solicite outra prévia.')
        context.checkpoint()
        # Keep a durable original next to the changed file, without overwriting anything.
        with tempfile.NamedTemporaryFile(prefix='.sazabi-original-', dir=path.parent, delete=False) as backup:
            backup.write(original)
            backup_path = Path(backup.name)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(prefix='.sazabi-patch-', dir=path.parent, delete=False) as stream:
                stream.write(payload['after'])
                stream.flush(); os.fsync(stream.fileno())
                temporary = Path(stream.name)
            os.chmod(temporary, path.stat().st_mode)
            if path.read_bytes() != original:
                raise ValueError('Arquivo mudou antes da escrita; original preservado em '+str(backup_path))
            os.replace(temporary, path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
        reverse_diff = ''.join(difflib.unified_diff(payload['after'].decode('utf-8-sig', 'replace').splitlines(True),
                                                   original.decode('utf-8-sig', 'replace').splitlines(True),
                                                   fromfile=str(path), tofile=str(path)+' (restaurado)'))
        undo = self.service.plan('patch', dict(path=str(path), before=payload['after'], after=original,
                                               digest=hashlib.sha256(payload['after']).hexdigest(), validation='restore'),
                                 'Prévia para restaurar exatamente a versão anterior (pode reintroduzir problemas):\n'+reverse_diff)
        operation = self.service.store.start('review.undo')
        self.service.store.finish(operation, 'planned', undo.message)
        self.service.plans[undo.data['token']]['operation'] = operation
        validation = {'syntax': 'Sintaxe do candidato validada; execute /test para validar o comportamento.',
                      'text': 'Arquivo textual aplicado; nenhuma validação de comportamento executada.',
                      'restore': 'Versão anterior restaurada; ela pode conter problemas anteriores.'}[payload['validation']]
        return self.service.ok('Alteração aplicada. Original preservado em '+str(backup_path)+'\n'+validation+'\n'+undo.message)
