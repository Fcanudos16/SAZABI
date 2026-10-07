"""Bounded HTTP transport. Pin validated public IPs; leave redirects to the caller."""
import http.client
import ipaddress
import json
import re
import socket
import ssl
import time
import zlib
from urllib.parse import urlsplit


class FetchError(RuntimeError):
    def __init__(self, message, status=None, location=None):
        super().__init__(message)
        self.status, self.location = status, location


def public_address(host, port=443):
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
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


class PinnedHTTP(http.client.HTTPConnection):
    def __init__(self, host, address, timeout):
        super().__init__(host, timeout=timeout)
        self.address = address

    def connect(self):
        self.sock = socket.create_connection((self.address, 80), self.timeout)


class HttpClient:
    def __init__(self, interval=1.0, timeout=15, max_bytes=1_000_000):
        self.interval, self.timeout, self.max_bytes = interval, timeout, max_bytes
        self.last, self.blocked = {}, set()

    def request(self, url, payload=None, headers=None, allow_http=False):
        try:
            parts = urlsplit(url)
            port = parts.port
        except ValueError:
            raise FetchError('URL inválida') from None
        valid_scheme = parts.scheme == 'https' or (allow_http and parts.scheme == 'http' and payload is None and not headers)
        if (not valid_scheme or not parts.hostname or parts.username or parts.password or
                port not in (None, 443 if parts.scheme == 'https' else 80)):
            raise FetchError('Apenas HTTPS público sem credenciais é permitido')
        host = parts.hostname
        if host in self.blocked:
            raise FetchError('Fonte suspensa nesta sessão')
        for attempt in range(3 if payload is None else 1):
            time.sleep(max(0, self.interval - (time.monotonic() - self.last.get(host, 0))))
            conn = None
            try:
                address = public_address(host, 443 if parts.scheme == 'https' else 80)
                conn = (PinnedHTTPS if parts.scheme == 'https' else PinnedHTTP)(host, address, self.timeout)
                self.last[host] = time.monotonic()
                body = json.dumps(payload).encode() if payload is not None else None
                request_headers = {'User-Agent': 'SAZABI/1.0', 'Accept': 'application/json, text/html, text/plain;q=0.9',
                                   'Accept-Encoding': 'gzip, deflate', **(headers or {})}
                if body is not None:
                    request_headers['Content-Type'] = 'application/json'
                conn.request('POST' if body is not None else 'GET',
                             (parts.path or '/') + ('?' + parts.query if parts.query else ''), body, request_headers)
                response = conn.getresponse()
                if response.status in (401, 403, 429, 432, 433):
                    self.blocked.add(host)
                    messages = {401: 'Chave API inválida ou sem autorização. Confira a configuração.',
                                403: 'Acesso recusado pela fonte.', 429: 'Limite de requisições atingido. Aguarde antes de tentar novamente.',
                                432: 'Créditos ou limite do plano Tavily esgotados.', 433: 'Limite de cobrança da Tavily atingido.'}
                    raise FetchError(messages[response.status], response.status)
                if response.status >= 500:
                    raise OSError('Fonte indisponível')
                if response.status != 200:
                    location = response.getheader('Location') if response.status in (301, 302, 303, 307, 308) else None
                    raise FetchError('Resposta HTTP não aceita: %d' % response.status, response.status,
                                     location if isinstance(location, str) else None)
                data = response.read(self.max_bytes + 1)
                if len(data) > self.max_bytes:
                    raise FetchError('Resposta excedeu o limite')
                encoding_header = response.getheader('Content-Encoding')
                compression = encoding_header.lower().strip() if isinstance(encoding_header, str) else ''
                if compression in ('gzip', 'deflate'):
                    try:
                        decoder = zlib.decompressobj(31 if compression == 'gzip' else 15)
                        data = decoder.decompress(data, self.max_bytes + 1)
                        if len(data) > self.max_bytes or decoder.unconsumed_tail:
                            raise FetchError('Resposta descompactada excedeu o limite')
                        if not decoder.eof:
                            raise FetchError('Resposta compactada incompleta')
                    except zlib.error:
                        raise FetchError('Compressão da resposta inválida') from None
                elif compression not in ('', 'identity'):
                    raise FetchError('Compressão da fonte não suportada: ' + compression[:20])
                content_type = response.getheader('Content-Type')
                match = re.search(r'charset=([\w-]+)', content_type, re.I) if isinstance(content_type, str) else None
                encoding = match.group(1) if match else 'utf-8'
                try:
                    return data.decode(encoding, errors='replace')
                except LookupError:
                    return data.decode('utf-8', errors='replace')
            except (OSError, http.client.HTTPException):
                if payload is not None or attempt == 2:
                    self.blocked.add(host)
                    raise FetchError('Falha de conexão; fonte suspensa') from None
                time.sleep(2 ** attempt)
            finally:
                if conn is not None:
                    conn.close()

    def json(self, url, payload=None, headers=None):
        try:
            return json.loads(self.request(url, payload, headers))
        except (ValueError, TypeError):
            raise FetchError('Resposta JSON inválida') from None
