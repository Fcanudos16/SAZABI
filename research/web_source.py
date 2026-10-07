"""Tavily discovery + conservative structured company extraction from public pages."""
import json
import re
import time
from html.parser import HTMLParser
from urllib.parse import urlsplit, urljoin, urlunsplit, quote
from urllib.robotparser import RobotFileParser

from database.models import RawCompany, Observation
from research.base import CompanySource, SearchProvider, SearchResult
from utils.http_client import HttpClient, FetchError
from utils.timeutils import now_iso
from utils.normalization import normalize_text


class TavilySearch(SearchProvider):
    def __init__(self, key, limit=5, client=None):
        self.key, self.limit = key, min(max(limit, 1), 20)
        self.client = client or HttpClient()

    def search(self, query):
        data = self.client.json('https://api.tavily.com/search',
            payload={'query': query, 'max_results': self.limit, 'search_depth': 'basic',
                     'topic': 'general', 'auto_parameters': False, 'include_answer': False,
                     'include_raw_content': False, 'include_images': False},
            headers={'Authorization': 'Bearer ' + self.key})
        if not isinstance(data, dict) or not isinstance(data.get('results'), list):
            raise FetchError('Resposta Tavily inválida')
        return [SearchResult(r['title'], r['url'], r.get('content', '') or '')
                for r in data['results'][:self.limit]
                if isinstance(r, dict) and isinstance(r.get('url'), str) and isinstance(r.get('title'), str)]

    def check_connection(self):
        data = self.client.json('https://api.tavily.com/usage', headers={'Authorization': 'Bearer ' + self.key})
        if not isinstance(data, dict) or not isinstance(data.get('key'), dict):
            raise FetchError('Resposta de validação Tavily inválida')
        usage, limit = data['key'].get('usage'), data['key'].get('limit')
        return {'usage': usage if isinstance(usage, (int, float)) else None,
                'limit': limit if isinstance(limit, (int, float)) else None}


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.structured = False
        self.buffer, self.documents, self.text = [], [], []
        self.meta, self.links, self.title, self.in_title = {}, [], '', False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == 'meta':
            key = attributes.get('property') or attributes.get('name')
            if key and attributes.get('content'):
                self.meta[key.lower()] = attributes['content']
        if tag == 'a' and attributes.get('href'):
            self.links.append(attributes['href'])
        if tag == 'title':
            self.in_title = True
        if tag in ('script', 'style', 'noscript'):
            self.hidden += 1
        if tag == 'script' and dict(attrs).get('type') == 'application/ld+json':
            self.structured = True
            self.buffer = []

    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False
        if tag == 'script' and self.structured:
            try:
                self.documents.append(json.loads(''.join(self.buffer)))
            except ValueError:
                pass
            self.structured = False
        if tag in ('script', 'style', 'noscript'):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self.structured:
            self.buffer.append(data)
        elif not self.hidden and data.strip():
            self.text.append(' '.join(data.split()))


def organizations(document):
    if isinstance(document, list):
        for value in document:
            yield from organizations(value)
    elif isinstance(document, dict):
        types = document.get('@type', [])
        types = [types] if isinstance(types, str) else types if isinstance(types, list) else []
        types = [value for value in types if isinstance(value, str)]
        allowed = {'Organization', 'LocalBusiness', 'Dentist', 'MedicalClinic', 'Restaurant',
                   'Store', 'AutoRepair', 'ProfessionalService', 'Corporation'}
        if set(types or []) & allowed and isinstance(document.get('name'), str):
            yield document
        yield from organizations(document.get('@graph', []))


def clean_url(url):
    try:
        parts = urlsplit(url)
        if parts.scheme not in ('https', 'http') or not parts.hostname or parts.username or parts.password:
            return None
        if parts.port not in (None, 80 if parts.scheme == 'http' else 443):
            return None
        hostname = parts.hostname.encode('idna').decode('ascii')
        host = '[' + hostname + ']' if ':' in hostname else hostname
        return urlunsplit((parts.scheme, host, quote(parts.path or '/', safe='/%:@!$&\'()*+,;=-._~'),
                          quote(parts.query, safe='/%?:@!$&\'()*+,;=-._~'), ''))
    except (ValueError, UnicodeError):
        return None


class WebSource(CompanySource):
    name = 'Web pública (Tavily + site da empresa)'

    def __init__(self, search, client=None):
        self.provider, self.client = search, client or HttpClient(interval=2)
        self.robots = {}
        self.pages, self.last_hits, self.errors = {}, [], []

    def _robots(self, url):
        parts = urlsplit(url)
        origin = '%s://%s' % (parts.scheme, parts.netloc)
        if origin not in self.robots:
            rules = RobotFileParser()
            target = origin + '/robots.txt'
            for _ in range(4):
                try:
                    text = self.client.request(target, allow_http=True)
                    rules.parse(text.splitlines())
                    break
                except FetchError as error:
                    if error.status in (404, 410):
                        rules.parse(['User-agent: *', 'Allow: /'])
                        break
                    if error.location:
                        target = clean_url(urljoin(target, error.location))
                        if not target:
                            raise FetchError('Redirecionamento inválido em robots.txt')
                    else:
                        raise
            else:
                raise FetchError('Excesso de redirecionamentos em robots.txt')
            self.robots[origin] = rules
        rules = self.robots[origin]
        if not rules.can_fetch('SAZABI', url):
            raise FetchError('Coleta não permitida por robots.txt')
        delay = rules.crawl_delay('SAZABI') or rules.crawl_delay('*') or 0
        if delay > 15:
            raise FetchError('Fonte exige intervalo longo; coleta automática adiada')
        self.client.interval = max(2, delay)

    def page(self, url):
        original = clean_url(url)
        if not original:
            raise FetchError('URL pública inválida')
        cached = self.pages.get(original)
        if cached and time.monotonic()-cached[0] < 300:
            return cached[1]
        target = original
        for _ in range(4):
            self._robots(target)
            try:
                html = self.client.request(target, allow_http=True)
                parser = PageParser()
                parser.feed(html)
                parser.url = target
                self.pages[original] = (time.monotonic(), parser)
                if len(self.pages) > 100:
                    self.pages.pop(next(iter(self.pages)))
                return parser
            except FetchError as error:
                if not error.location:
                    raise
                target = clean_url(urljoin(target, error.location))
                if not target:
                    raise FetchError('Redirecionamento inválido')
        raise FetchError('Excesso de redirecionamentos')

    def search(self, criteria):
        query = ' '.join(str(x) for x in (criteria.segment, criteria.city, criteria.state,
                                         criteria.size, criteria.need) if x)
        results = []
        self.last_hits, self.errors = [], []
        for hit in self.provider.search(query):
            record = dict(title=hit.title[:500], url=hit.url, snippet=str(hit.snippet)[:2000],
                          retrieved_at=now_iso(), status='pending', reason='Identidade da empresa não confirmada no site.')
            self.last_hits.append(record)
            try:
                page = self.page(hit.url)
            except FetchError as error:
                record['reason'] = str(error)
                continue
            company = self.extract(page, criteria.city)
            if company:
                record.update(status='identified', reason='Identidade publicada no próprio site; filtros exigem revisão.')
                results.append(company)
        return results

    def extract(self, page, city_filter=None):
        # Directories/social networks are discovery pages, never company identities.
        host = (urlsplit(page.url).hostname or '').removeprefix('www.')
        platforms = ('facebook.com', 'instagram.com', 'linkedin.com', 'youtube.com',
                     'google.com', 'google.com.br', 'econodata.com.br', 'solutudo.com.br',
                     'doctoralia.com.br', 'cnpj.biz', 'yelp.com', 'tripadvisor.com.br')
        if any(host == domain or host.endswith('.' + domain) for domain in platforms):
            return None
        for document in page.documents:
            for item in organizations(document):
                address = item.get('address') or {}
                if not isinstance(address, dict):
                    address = {}
                city = address.get('addressLocality')
                if city_filter and isinstance(city, str) and normalize_text(city_filter) != normalize_text(city):
                    continue
                # Do not turn directory entries into companies on the directory domain.
                official = item.get('url') or page.url
                if not isinstance(official, str) or not clean_url(official) or (urlsplit(official).hostname or '').removeprefix('www.') != host:
                    continue
                observation = Observation('Cadastro público: ' + json.dumps(item, ensure_ascii=False)[:4000],
                                          self.name, page.url, now_iso())
                return RawCompany(name=item['name'][:200], website=official,
                    city=city if isinstance(city, str) else None,
                    state=address.get('addressRegion') if isinstance(address.get('addressRegion'), str) else None,
                    address=address.get('streetAddress') if isinstance(address.get('streetAddress'), str) else None, source_name=self.name,
                    phone=item.get('telephone') if isinstance(item.get('telephone'), str) else None,
                    description=item.get('description') if isinstance(item.get('description'), str) else None,
                    observations=[observation])
        # An explicitly published site identity is usable; title alone is not.
        name = page.meta.get('og:site_name', '').strip()
        if name and 2 <= len(name) <= 150 and normalize_text(name) in normalize_text(' '.join(page.text)):
            return RawCompany(name=name, website=page.url, source_name=self.name,
                observations=[Observation('Identidade declarada pelo site (og:site_name): ' + name,
                                          self.name, page.url, now_iso())])
        return None


    def lookup(self, name):
        from database.models import SearchCriteria
        from utils.normalization import normalize_name
        if name.startswith(('https://', 'http://')):
            return self.extract(self.page(name))
        matches = [r for r in self.search(SearchCriteria(segment=name))
                   if normalize_name(r.name) == normalize_name(name)]
        return matches[0] if len(matches) == 1 else None

    def fetch_observations(self, company):
        if not company.website:
            return []
        page = self.page(company.website)
        pages = [page]
        origin = urlsplit(page.url)
        selected = set()
        for link in page.links:
            url = clean_url(urljoin(page.url, link))
            if not url or url == page.url or url in selected:
                continue
            parts = urlsplit(url)
            if parts.hostname != origin.hostname or parts.query:
                continue
            if not re.search(r'/(?:contato|sobre|quem-somos|unidades|contact|about)(?:/|$|\.html)', parts.path, re.I):
                continue
            selected.add(url)
            try:
                pages.append(self.page(url))
            except FetchError:
                pass  # Main page remains evidence; do not claim the linked page was read.
            if len(selected) >= 2:
                break
        identity = self.extract(page)
        observed = identity.observations if identity else []
        return observed + [Observation(text[:1500], self.name, item.url, now_iso())
                for item in pages for text in item.text[:100] if len(text) > 15]
