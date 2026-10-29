"""Explicit local roots; no shell, dynamic imports or model-driven permissions."""
from pathlib import Path
import os

BLOCKED = {'.git', '.env', '.ssh', '.aws', '.codex', '__pycache__', 'node_modules', '.venv', 'venv'}


class LocalPolicy:
    def __init__(self, roots, protected=()):
        self.roots = tuple(Path(p).resolve() for p in roots)
        self.protected = {str(Path(p).resolve()).casefold() for p in protected if p != ':memory:'}

    def path(self, value='.', *, exists=True):
        if str(value).startswith('\\\\'):
            raise ValueError('Caminhos de rede não habilitados.')
        raw = Path(value)
        for part in raw.parts[1:] if raw.drive else raw.parts:
            stem = part.split('.')[0].upper()
            if ':' in part or stem in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1,10)), *(f'LPT{i}' for i in range(1,10))}:
                raise ValueError('Fluxos alternativos e nomes de dispositivo não são permitidos.')
        if not raw.is_absolute():
            raw = self.roots[0] / raw
        resolved = raw.resolve()
        if str(resolved).casefold() in self.protected:
            raise ValueError('Arquivo operacional do SAZABI protegido.')
        if resolved.suffix.lower() in ('.pem', '.key', '.pfx') or resolved.name.lower() in ('credentials.json', 'credentials', 'id_rsa', 'id_ed25519'):
            raise ValueError('Arquivo de credenciais protegido.')
        if not any(resolved.is_relative_to(root) for root in self.roots):
            raise ValueError('Caminho fora de LOCAL_ROOTS autorizadas no .env.')
        if any(part.lower() in BLOCKED or part.lower().startswith('.env') for part in raw.parts):
            raise ValueError('Caminho reservado ou sensível.')
        if any(part.lower() in BLOCKED or part.lower().startswith('.env') for part in resolved.parts):
            raise ValueError('Caminho reservado ou sensível.')
        # Reject links and Windows reparse points, including ancestors.
        for part in (raw, *raw.parents):
            if part.exists() and (part.is_symlink() or getattr(part, 'is_junction', lambda: False)()):
                raise ValueError('Links e junctions não são permitidos.')
        if exists and not resolved.exists():
            raise ValueError('Caminho inexistente.')
        return resolved

    def files(self, root, context, limit=5000):
        root = self.path(root)
        if not root.is_dir():
            raise ValueError('Selecione uma pasta para pesquisar.')
        count = 0
        def failed(error):
            raise error
        for directory, folders, files in os.walk(root, followlinks=False, onerror=failed):
            context.checkpoint()
            folders[:] = sorted(f for f in folders if not f.startswith('.') and f.lower() not in BLOCKED
                                and not (Path(directory)/f).is_symlink()
                                and not getattr(Path(directory)/f, 'is_junction', lambda: False)())
            for name in sorted(files):
                context.checkpoint()
                if name.startswith('.'):
                    continue
                try:
                    path = self.path(str(Path(directory)/name))
                except ValueError:
                    continue
                count += 1
                if count > limit:
                    raise ValueError('Limite de 5.000 arquivos; selecione uma pasta menor.')
                yield path
