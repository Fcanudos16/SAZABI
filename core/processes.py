"""Bounded, cancellable argv execution shared by local routines and Git."""
from dataclasses import dataclass
import os
import subprocess
import tempfile
import time


@dataclass(frozen=True)
class ProcessOutput:
    code: int
    stdout: bytes
    stderr: bytes


def run(argv, cwd, context, timeout=60, limit=1_000_000):
    env = {k: v for k, v in os.environ.items() if k.upper() in {
        'PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'USERPROFILE', 'HOME',
        'APPDATA', 'LOCALAPPDATA', 'PROGRAMFILES', 'PATHEXT'}}
    env.update(GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='Never', GIT_PAGER='cat',
               GIT_OPTIONAL_LOCKS='0', GIT_LITERAL_PATHSPECS='1', PYTHONDONTWRITEBYTECODE='1')
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    context.checkpoint()
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        child = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                 stdout=out, stderr=err, shell=False, creationflags=flags)
        started = time.monotonic()
        try:
            while child.poll() is None:
                context.checkpoint()
                if time.monotonic()-started > timeout:
                    raise ValueError('Processo interrompido: tempo limite atingido.')
                if os.fstat(out.fileno()).st_size + os.fstat(err.fileno()).st_size > limit:
                    raise ValueError('Processo interrompido: saída excedeu o limite.')
                time.sleep(.03)
        finally:
            if child.poll() is None:
                try:
                    if os.name == 'nt':
                        subprocess.run(['taskkill', '/PID', str(child.pid), '/T', '/F'],
                                       capture_output=True, timeout=10, creationflags=flags)
                finally:
                    if child.poll() is None:
                        child.kill()
                    child.wait(timeout=10)
        out.seek(0); err.seek(0)
        stdout, stderr = out.read(limit+1), err.read(limit+1)
        if len(stdout)+len(stderr) > limit:
            raise ValueError('Saída excedeu o limite; consulte os efeitos antes de repetir.')
        return ProcessOutput(child.returncode, stdout, stderr)
