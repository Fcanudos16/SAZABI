"""Brave discovery + conservative structured company extraction from public pages."""
import json
from html.parser import HTMLParser
from urllib.parse import urlencode, urlsplit
from urllib.robotparser import RobotFileParser

from database.models import RawCompany, Observation
from research.base import CompanySource, SearchProvider, SearchResult
from utils.http_client import HttpClient, FetchError
from utils.timeutils import now_iso
from utils.normalization import normalize_text


class BraveSearch(SearchProvider):
    def __init__(self, key, limit=5, client=None):
        self.key, self.limit = key, min(max(limit, 1), 20)
        self.client = client or HttpClient()

    def search(self, query):
        data = self.client.json('https://api.search.brave.com/res/v1/web/search?' +
                                urlencode({'q': query, 'count': self.limit, 'country': 'br'}),
                                headers={'X-Subscription-Token': self.key})
        return [SearchResult(r['title'], r['url'], r.get('description', ''))
                for r in data.get('web', {}).get('results', [])[:self.limit]
                if isinstance(r.get('url'), str) and isinstance(r.get('title'), str)]


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.structured = False
        self.buffer, self.documents, self.text = [], [], []

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript'):
            self.hidden += 1
        if tag == 'script' and dict(attrs).get('type') == 'application/ld+json':
            self.structured = True
            self.buffer = []

    def handle_endtag(self, tag):
        if tag == 'script' and self.structured:
            try:
                self.documents.append(json.loads(''.join(self.buffer)))
            except ValueError:
                pass
            self.structured = False
        if tag in ('script', 'style', 'noscript'):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
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
        types = [types] if isinstance(types, str) else types
        allowed = {'Organization', 'LocalBusiness', 'Dentist', 'MedicalClinic', 'Restaurant',
                   'Store', 'AutoRepair', 'ProfessionalService', 'Corporation'}
        if set(types or []) & allowed and isinstance(document.get('name'), str):
            yield document
        yield from organizations(document.get('@graph', []))


class WebSource(CompanySource):
    name = 'Web pública (Brave + dados estruturados)'

    def __init__(self, search, client=None):
        self.provider, self.client = search, client or HttpClient(interval=2)
        self.robots = {}

    def page(self, url):
        parts = urlsplit(url)
        origin = '%s://%s' % (parts.scheme, parts.netloc)
        if origin not in self.robots:
            rules = RobotFileParser()
            # Fail closed, including missing/unavailable robots and redirects.
            rules.parse(self.client.request(origin + '/robots.txt').splitlines())
            self.robots[origin] = rules
        rules = self.robots[origin]
        if not rules.can_fetch('SAZABI', url):
            raise FetchError('Coleta não permitida por robots.txt')
        delay = rules.crawl_delay('SAZABI') or rules.crawl_delay('*') or 0
        self.client.interval = max(self.client.interval, delay)
        parser = PageParser()
        parser.feed(self.client.request(url))
        return parser

    def search(self, criteria):
        query = ' '.join(str(x) for x in (criteria.segment, criteria.city, criteria.state,
                                         criteria.size, criteria.need) if x)
        results = []
        failures = 0
        for hit in self.provider.search(query):
            try:
                page = self.page(hit.url)
            except FetchError:
                failures += 1
                continue
            for document in page.documents:
                for item in organizations(document):
                    address = item.get('address') or {}
                    if not isinstance(address, dict):
                        address = {}
                    city = address.get('addressLocality')
                    if criteria.city and isinstance(city, str) and normalize_text(criteria.city) != normalize_text(city):
                        continue
                    # Do not turn directory entries into companies on the directory domain.
                    official = item.get('url')
                    if not isinstance(official, str) or urlsplit(official).hostname != urlsplit(hit.url).hostname:
                        continue
                    observation = Observation('Cadastro público: ' + json.dumps(item, ensure_ascii=False)[:4000],
                                              self.name, hit.url, now_iso())
                    results.append(RawCompany(name=item['name'][:200], website=official,
                        city=city if isinstance(city, str) else None,
                        state=address.get('addressRegion') if isinstance(address.get('addressRegion'), str) else None,
                        address=address.get('streetAddress') if isinstance(address.get('streetAddress'), str) else None, source_name=self.name,
                        observations=[observation]))
                    break
                if results and results[-1].observations[0].url == hit.url:
                    break
        if failures and not results:
            raise FetchError('Páginas indisponíveis ou coleta não permitida')
        return results

    def lookup(self, name):
        from database.models import SearchCriteria
        from utils.normalization import normalize_name
        matches = [r for r in self.search(SearchCriteria(segment=name))
                   if normalize_name(r.name) == normalize_name(name)]
        return matches[0] if len(matches) == 1 else None

    def fetch_observations(self, company):
        if not company.website:
            return []
        page = self.page(company.website)
        return [Observation(text[:1500], self.name, company.website, now_iso())
                for text in page.text[:100] if len(text) > 15]
