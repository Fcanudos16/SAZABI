"""Short-lived OS lock protects research and crash recovery across app instances."""
from contextlib import contextmanager
from pathlib import Path
import os
from utils.timeutils import now_iso


class ResearchBusy(RuntimeError):
    pass


@contextmanager
def research_lock(db):
    if db.path==':memory:':
        yield
        return
    path=Path(db.path).resolve().with_suffix('.research.lock')
    handle=open(path,'a+b')
    locked=False
    try:
        handle.seek(0,2)
        if handle.tell()==0: handle.write(b'0');handle.flush()
        handle.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            locked=True
        except OSError:
            raise ResearchBusy('Outra instância está pesquisando neste banco. Aguarde sua conclusão.') from None
        yield
    finally:
        if locked:
            handle.seek(0)
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(),fcntl.LOCK_UN)
        handle.close()


def recover_locked(db):
    """Caller holds research_lock. Date is recovery time, not a guessed crash time."""
    with db.transaction():
        for row in db.query("SELECT id FROM research_runs WHERE status='running'"):
            counts=db.query_one('SELECT COUNT(*) n,COALESCE(SUM(is_new),0) fresh FROM run_companies WHERE run_id=?',(row['id'],))
            db.execute("UPDATE research_runs SET status='failed',finished_at=?,error_message=?,new_count=?,known_count=? WHERE id=?",
                       (now_iso(),'Execução interrompida; recuperada na inicialização. Dados confirmados preservados; contagens podem ser incompletas.',
                        counts['fresh'],counts['n']-counts['fresh'],row['id']))


def recover(db):
    try:
        with research_lock(db): recover_locked(db)
    except ResearchBusy:
        pass  # A live run in another process is not a crash.
