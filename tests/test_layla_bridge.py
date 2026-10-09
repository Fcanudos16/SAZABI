"""Exercise the real HTTP transport against an isolated contract server."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import pytest
from integrations.layla.bridge import LaylaBridge, LaylaError
from integrations.layla.session import LaylaSession
from core.config import Config

@pytest.fixture
def server():
    class Handler(BaseHTTPRequestHandler):
        requests = []
        deny = 0
        invalid = False
        def log_message(self, *args):
            pass
        def respond(self, value, status=200, cookie=False):
            raw = value.encode('utf-8') if isinstance(value, str) else json.dumps(value).encode()
            self.send_response(status)
            self.send_header('Content-Length', str(len(raw)))
            if cookie:
                self.send_header('Set-Cookie', 'session=test-session; HttpOnly; Path=/')
            self.end_headers()
            self.wfile.write(raw)
        def do_GET(self):
            if self.path == '/':
                return self.respond('<meta name="csrf-token" content="test-csrf">', cookie=True)
            if self.path == '/api/configuracoes':
                return self.respond({'theme': 'test'}, type(self).deny or 200)
            self.respond({}, 404)
        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))))
            type(self).requests.append((self.path, dict(self.headers), data))
            if self.headers.get('X-CSRFToken') != 'test-csrf' or self.headers.get('Cookie') != 'session=test-session':
                return self.respond({}, 403)
            if self.path == '/enviar':
                return self.respond({'resposta': None if type(self).invalid else 'Resposta de teste: '+data['texto']})
            if self.path == '/novo_chat':
                return self.respond({'status': 'resetado'})
            self.respond({}, 404)
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield 'http://127.0.0.1:'+str(httpd.server_port), Handler
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(2)


def test_cookie_csrf_send_receive_reset_and_close(server):
    url, handler = server
    bridge = LaylaBridge(url)
    bridge.connect()
    assert bridge.state == 'connected' and not handler.requests
    assert bridge.send('Mensagem') == 'Resposta de teste: Mensagem'
    assert handler.requests[0][0] == '/enviar' and handler.requests[0][2] == {'texto': 'Mensagem'}
    bridge.new_session()
    assert handler.requests[-1][0] == '/novo_chat'
    bridge.close()
    assert not bridge.cookies and not bridge.csrf
    with pytest.raises(LaylaError):
        bridge.send('não enviar')
    assert len(handler.requests) == 2


@pytest.mark.parametrize('status, state', [(401, 'authentication_required'), (403, 'authentication_required'), (423, 'locked'), (429, 'rate_limited')])
def test_boundaries_never_bypassed(server, status, state):
    url, handler = server
    handler.deny = status
    bridge = LaylaBridge(url)
    with pytest.raises(LaylaError):
        bridge.send('blocked')
    assert bridge.state == state and handler.requests == []
    bridge.close()


def test_invalid_reply_not_displayed_as_success(server):
    url, handler = server
    handler.invalid = True
    bridge = LaylaBridge(url)
    with pytest.raises(LaylaError):
        bridge.send('test')
    assert bridge.state != 'connected'
    bridge.close()


@pytest.mark.parametrize('url', ['https://example.org', 'http://user:pass@localhost:5000', 'http://127.0.0.1:5000/path'])
def test_remote_and_credential_urls_rejected(url):
    with pytest.raises(LaylaError):
        LaylaBridge(url).connect()


def test_session_worker_roundtrip(server):
    url, _ = server
    session = LaylaSession(Config(layla_url=url))
    try:
        assert session.submit('connect')
        assert session.events.get(timeout=3) == ('connect', 'LAYLA conectada.', 'connected')
        assert session.submit('send', 'teste')
        assert session.events.get(timeout=3) == ('reply', 'Resposta de teste: teste', 'connected')
        assert session.submit('reset')
        assert session.events.get(timeout=3)[0] == 'reset'
    finally:
        session.close()
        session.thread.join(3)
    assert not session.thread.is_alive()
