"""Native client for LAYLA Mark 5. Session/CSRF stay in this backend only."""
import http.client
import json
import socket
import threading
from http.cookies import SimpleCookie
from html.parser import HTMLParser
from urllib.parse import urlsplit

class LaylaError(ValueError):
    def __init__(self, message, status='disconnected'):
        super().__init__(message)
        self.status = status

class CSRFParser(HTMLParser):
    token = ''
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta' and attrs.get('name') == 'csrf-token':
            self.token = attrs.get('content', '')

class LaylaBridge:
    def __init__(self, url='http://127.0.0.1:5000', session_cookie='', timeout=60):
        self.url, self._session_cookie = url, session_cookie
        self.timeout = max(5, min(120, timeout))
        self.cookies, self.csrf, self.state = SimpleCookie(), '', 'disconnected'
        self._connection, self._closed = None, threading.Event()
        self._lock = threading.Lock()
        self._restore_cookie()

    def _restore_cookie(self):
        if self._session_cookie:
            if any(c in self._session_cookie for c in '\r\n;'):
                raise LaylaError('Credencial LAYLA inválida.', 'authentication_required')
            self.cookies['session'] = self._session_cookie

    def _request(self, path, payload=None):
        if self._closed.is_set():
            raise LaylaError('Conexão encerrada.')
        try:
            parts = urlsplit(self.url)
            if parts.scheme not in ('http', 'https') or parts.hostname not in ('127.0.0.1', 'localhost', '::1') or parts.username or parts.password or parts.path not in ('', '/') or parts.query or parts.fragment:
                raise ValueError
            port = parts.port
        except ValueError:
            raise LaylaError('Configure um endereço local válido para a LAYLA.') from None
        conn = (http.client.HTTPSConnection if parts.scheme == 'https' else http.client.HTTPConnection)(parts.hostname, port, timeout=self.timeout)
        headers = {'Accept': 'application/json, text/html', 'Content-Type': 'application/json'}
        if self.cookies:
            headers['Cookie'] = '; '.join(morsel.OutputString(attrs=[]) for morsel in self.cookies.values())
        if payload is not None:
            headers['X-CSRFToken'] = self.csrf
        with self._lock:
            if self._closed.is_set():
                raise LaylaError('Conexão encerrada.')
            self._connection = conn
        try:
            conn.request('POST' if payload is not None else 'GET', path,
                         json.dumps(payload, ensure_ascii=False).encode('utf-8') if payload is not None else None, headers)
            response = conn.getresponse()
            raw = response.read(1_000_001)
            if response.status in (401, 403):
                raise LaylaError('A LAYLA exige uma sessão autorizada. Verifique a autenticação da integração.', 'authentication_required')
            if response.status == 423:
                raise LaylaError('LAYLA em STANDBY. Desbloqueie na LAYLA.', 'locked')
            if response.status == 429:
                raise LaylaError('LAYLA atingiu o limite de mensagens. Aguarde antes de tentar novamente.', 'rate_limited')
            if response.status != 200 or len(raw) > 1_000_000:
                raise LaylaError('LAYLA recusou a solicitação ou retornou uma resposta inválida.')
            for name, value in response.getheaders():
                if name.lower() == 'set-cookie':
                    self.cookies.load(value)
            return raw.decode('utf-8')
        except (OSError, http.client.HTTPException):
            raise LaylaError('LAYLA local indisponível ou sem resposta. Abra a LAYLA e tente conectar novamente.') from None
        except UnicodeError:
            raise LaylaError('Resposta LAYLA inválida.') from None
        finally:
            conn.close()
            with self._lock:
                if self._connection is conn:
                    self._connection = None

    def _json(self, path, payload=None):
        try:
            value = json.loads(self._request(path, payload))
        except (ValueError, TypeError) as error:
            if isinstance(error, LaylaError):
                raise
            raise LaylaError('Resposta LAYLA inválida.') from None
        if not isinstance(value, dict) or value.get('erro') or value.get('error'):
            raise LaylaError('A LAYLA não conseguiu concluir a solicitação.')
        return value

    def connect(self):
        self.state = 'connecting'
        try:
            parser = CSRFParser()
            parser.feed(self._request('/'))
            if not parser.token or len(parser.token) > 512:
                raise LaylaError('Esta instalação não oferece o contrato LAYLA Mark 5 esperado.')
            self.csrf = parser.token
            # Protected, read-only route verifies ownership and STANDBY as well.
            self._json('/api/configuracoes')
            self.state = 'connected'
        except LaylaError as error:
            self.state = error.status
            raise

    def send(self, text):
        if not isinstance(text, str) or not text.strip() or len(text) > 2000 or '\x00' in text:
            raise LaylaError('Envie uma mensagem de até 2.000 caracteres.', self.state)
        if self.state != 'connected':
            self.connect()
        try:
            data = self._json('/enviar', {'texto': text.strip()})
            reply = data.get('resposta')
            if not isinstance(reply, str) or not reply.strip() or len(reply) > 24000:
                raise LaylaError('LAYLA não retornou uma resposta textual válida.')
            return reply
        except LaylaError as error:
            self.state = error.status
            raise

    def new_session(self):
        if self.state != 'connected':
            self.connect()
        self._json('/novo_chat', {})

    def close(self):
        self._closed.set()
        self.state = 'disconnected'
        with self._lock:
            conn = self._connection
        if conn:
            try:
                if conn.sock:
                    conn.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            conn.close()
        self.cookies.clear()
        self.csrf = ''
