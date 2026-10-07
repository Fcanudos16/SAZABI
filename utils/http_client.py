"""Bounded HTTP transport. Public fetches pin a validated IP and reject redirects."""
import http.client
import ipaddress
import json
import socket
import ssl
import time
from urllib.parse import urlsplit


class FetchError(RuntimeError):
    pass


def public_address(host):
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    ips = [item[4][0] for item in addresses]
    if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
        raise FetchError('Destino não público bloqueado')
    return ips[0]


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, address, timeout):
        super().__init__(host, timeout=timeout)
        self.address = address

    def connect(self):
        sock = socket.create_connection((self.address, 443), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


class HttpClient:
    def __init__(self, interval=1.0, timeout=15, max_bytes=1_000_000):
        self.interval, self.timeout, self.max_bytes = interval, timeout, max_bytes
        self.last, self.blocked = {}, set()

    def request(self, url, payload=None, headers=None):
        parts = urlsplit(url)
        if (parts.scheme != 'https' or not parts.hostname or parts.username or
                parts.password or parts.port not in (None, 443)):
            raise FetchError('Apenas HTTPS público sem credenciais é permitido')
        host = parts.hostname
        if host in self.blocked:
            raise FetchError('Fonte suspensa nesta sessão')
        for attempt in range(3 if payload is None else 1):
            time.sleep(max(0, self.interval - (time.monotonic() - self.last.get(host, 0))))
            conn = PinnedHTTPS(host, public_address(host), self.timeout)
            self.last[host] = time.monotonic()
            try:
                body = json.dumps(payload).encode() if payload is not None else None
                request_headers = {'User-Agent': 'SAZABI/1.0', 'Accept': 'application/json', **(headers or {})}
                if body is not None:
                    request_headers['Content-Type'] = 'application/json'
                conn.request('POST' if body is not None else 'GET',
                             parts.path + ('?' + parts.query if parts.query else ''), body, request_headers)
                response = conn.getresponse()
                if response.status in (401, 403, 429, 432, 433):
                    self.blocked.add(host)
                    raise FetchError('Fonte bloqueou ou limitou o acesso; sessão suspensa')
                if response.status >= 500:
                    raise OSError('Fonte indisponível')
                if response.status != 200:
                    raise FetchError('Resposta HTTP não aceita: %d' % response.status)
                data = response.read(self.max_bytes + 1)
                if len(data) > self.max_bytes:
                    raise FetchError('Resposta excedeu o limite')
                return data.decode('utf-8', errors='replace')
            except (OSError, http.client.HTTPException):
                if payload is not None or attempt == 2:
                    self.blocked.add(host)
                    raise FetchError('Falha de conexão; fonte suspensa') from None
                time.sleep(2 ** attempt)
            finally:
                conn.close()

    def json(self, url, payload=None, headers=None):
        try:
            return json.loads(self.request(url, payload, headers))
        except (ValueError, TypeError):
            raise FetchError('Resposta JSON inválida') from None
