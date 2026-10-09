"""One bounded native session worker; no Tk calls from background threads."""
from queue import Queue, Full
from threading import Thread, Lock
from integrations.layla.bridge import LaylaBridge, LaylaError

class LaylaSession:
    def __init__(self, config, bridge=None):
        self.bridge = bridge or LaylaBridge(config.layla_url, config.layla_session_cookie)
        self.events, self.requests = Queue(), Queue(maxsize=1)
        self._busy, self._closed = False, False
        self._lock = Lock()
        self.thread = Thread(target=self._run, name='SAZABI-LAYLA', daemon=True)
        self.thread.start()

    def submit(self, action, text=''):
        if action not in ('connect', 'send', 'reset'):
            return False
        with self._lock:
            if self._busy or self._closed:
                return False
            self._busy = True
            self.requests.put_nowait((action, text))
            return True

    def _run(self):
        while True:
            request = self.requests.get()
            if request is None:
                return
            action, text = request
            try:
                if action == 'send':
                    reply = self.bridge.send(text)
                elif action == 'reset':
                    self.bridge.new_session()
                    reply = 'Nova sessão iniciada.'
                else:
                    self.bridge.connect()
                    reply = 'LAYLA conectada.'
                result = ('reply' if action == 'send' else action, reply)
            except LaylaError as error:
                self.bridge.state = error.status
                result = ('error', str(error))
            except Exception:
                self.bridge.state = 'disconnected'
                result = ('error', 'Falha na integração LAYLA. Tente conectar novamente.')
            with self._lock:
                self._busy = False
                if self._closed:
                    return
                self.events.put((result[0], result[1], self.bridge.state))

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self.bridge.close()
        try:
            self.requests.put_nowait(None)
        except Full:
            pass
