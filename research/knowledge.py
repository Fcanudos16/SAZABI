"""Public research adapters; never upload local documents or invoke paid providers."""
from collections import Counter
from dataclasses import dataclass
from html.parser import HTMLParser
import re
from urllib.parse import urlencode, urlsplit, urljoin
from urllib.robotparser import RobotFileParser

from utils.http_client import HttpClient, FetchError
from utils.logger import redact
from utils.timeutils import now_iso


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.text = []
        self.title = ''
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript', 'svg', 'nav', 'footer'):
            self.hidden += 1
        if tag == 'title':
            self.in_title = True
        if tag in ('p', 'div', 'li', 'br', 'h1', 'h2', 'h3', 'pre', 'section'):
            self.text.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript', 'svg', 'nav', 'footer'):
            self.hidden = max(0, self.hidden-1)
        if tag == 'title':
            self.in_title = False

    def handle_data(self, value):
        if self.in_title:
            self.title += value
        if not self.hidden:
            self.text.append(value)

    def lines(self):
        return [' '.join(line.split()) for line in ''.join(self.text).splitlines() if line.strip()]


def plain(html):
    parser = TextParser(); parser.feed(html)
    return ' '.join(parser.lines())


@dataclass
class Document:
    source: str
    title: str
    lines: list
    fetched_at: str
    external: bool = False


class WikimediaSearch:
    """Documented MediaWiki search API, limited discovery, not a general web index."""
    def __init__(self, client, language='pt'):
        if language not in ('pt', 'en'):
            raise ValueError('KNOWLEDGE_LANGUAGE deve ser pt ou en.')
        self.client, self.language = client, language

    def search(self, query):
        params = urlencode(dict(action='query', list='search', srsearch=query, srlimit=5,
                                srnamespace=0, format='json', utf8=1, maxlag=5))
        data = self.client.json(f'https://{self.language}.wikipedia.org/w/api.php?'+params)
        if not isinstance(data, dict) or data.get('error') or not isinstance(data.get('query'), dict) or not isinstance(data['query'].get('search'), list):
            raise FetchError('Resposta inválida da pesquisa Wikimedia; nenhum resultado foi inventado.')
        rows = []
        for item in data['query']['search'][:5]:
            if (not isinstance(item, dict) or not isinstance(item.get('title'), str) or
                not item['title'].strip() or type(item.get('pageid')) is not int or item['pageid'] <= 0 or
                not isinstance(item.get('snippet', ''), str)):
                raise FetchError('Resultado Wikimedia malformado.')
            rows.append(dict(title=item['title'], url=f'https://{self.language}.wikipedia.org/?curid={item["pageid"]}',
                             snippet=plain(item.get('snippet', ''))[:500], retrieved_at=now_iso()))
        return rows


class PublicDocuments:
    def __init__(self, client):
        self.client = client

    @staticmethod
    def validate(url):
        parts = urlsplit(url)
        if (parts.scheme != 'https' or not parts.hostname or parts.username or parts.password or
            parts.port not in (None, 443) or len(url) > 1800 or redact(url) != url):
            raise ValueError('Use URL HTTPS pública, sem credenciais.')
        return parts

    def allowed(self, url):
        parts = self.validate(url)
        robots = f'https://{parts.netloc}/robots.txt'
        try:
            text = self.client.request(robots)
        except FetchError as error:
            if error.status == 404:
                return
            raise FetchError('Não foi possível verificar robots.txt; leitura suspensa.') from None
        policy = RobotFileParser(); policy.parse(text.splitlines())
        if not policy.can_fetch('SAZABI', url):
            raise FetchError('A fonte não permite esta leitura em robots.txt.')

    def fetch(self, url):
        seen = set()
        for _ in range(4):
            if url in seen:
                raise FetchError('Redirecionamento circular.')
            seen.add(url)
            self.allowed(url)
            try:
                text = self.client.request(url)
            except FetchError as error:
                if error.status in (301, 302, 303, 307, 308) and error.location:
                    url = urljoin(url, error.location)
                    self.validate(url)
                    continue
                raise
            if '\x00' in text or text.startswith('%PDF'):
                raise FetchError('Fonte binária não suportada; selecione HTML ou texto.')
            parser = TextParser()
            if re.search(r'<(?:html|body|p|div|h1|!doctype)\b', text, re.I):
                parser.feed(text)
                lines = parser.lines()
            else:
                lines = text.splitlines()
            if not any(line.strip() for line in lines):
                raise FetchError('A fonte não retornou texto legível.')
            return Document(url, parser.title.strip() or url, lines, now_iso(), True)
        raise FetchError('Limite de redirecionamentos atingido.')


def terms(text):
    stop = {'para','with','this','that','from','como','mais','uma','the','and','que','com','por','dos','das','you','your','are'}
    return [word for word in re.findall(r'[^\W\d_]{3,}', text.casefold()) if word not in stop]


def summary(document):
    """Extractive, auditable selection; never claim inferred facts as sourced facts."""
    candidates = [(i, line.strip()) for i, line in enumerate(document.lines, 1) if len(line.strip()) >= 35]
    frequencies = Counter(terms(' '.join(line for _, line in candidates)))
    ranked = sorted(candidates, key=lambda row: sum(min(frequencies[w], 20) for w in set(terms(row[1]))) / max(1, len(terms(row[1]))**.5), reverse=True)
    chosen, seen = [], set()
    for number, line in ranked:
        if line in seen:
            continue
        seen.add(line)
        chosen.append((number, line[:500]))
        if len(chosen) == 5:
            break
    if not chosen:
        chosen = [(i, line[:500]) for i, line in enumerate(document.lines, 1) if line.strip()][:5]
    chosen.sort()
    return [{'line': number, 'text': text} for number, text in chosen]


class Knowledge:
    def __init__(self, service, client=None):
        self.service = service
        self.client = client or HttpClient(interval=1, timeout=10, max_bytes=1_000_000)
        self.documents = PublicDocuments(self.client)
        self.search_adapter = WikimediaSearch(self.client, service.agent.config.knowledge_language)

    def document(self, value):
        if value.startswith('https://'):
            if self.service.agent.config.knowledge_web == 'disabled':
                raise ValueError('Pesquisa web desativada no .env; documentos locais continuam disponíveis.')
            return self.documents.fetch(value)
        path = self.service.policy.path(value)
        if not path.is_file() or path.stat().st_size > 1_000_000 or path.suffix.lower() not in ('.md', '.txt', '.rst', '.log', '.py', '.json', '.toml'):
            raise ValueError('Use documento textual local de até 1 MB ou URL HTTPS pública.')
        raw = path.read_bytes()
        if b'\0' in raw:
            raise ValueError('Documento binário não suportado.')
        return Document(str(path), path.name, raw.decode('utf-8-sig', 'replace').splitlines(), now_iso())

    def execute(self, args, context):
        self.client.checkpoint = context.checkpoint
        try:
            if args and args[0] == 'web' and len(args) == 2 and args[1].strip():
                if self.service.agent.config.knowledge_web != 'wikimedia':
                    raise ValueError('Pesquisa web desativada. Configure KNOWLEDGE_WEB=wikimedia no .env.')
                rows = self.search_adapter.search(args[1])
                result = self.service.ok('Pesquisa Wikimedia (descoberta enciclopédica, não índice completo da web).\n'
                                         'Somente a consulta explícita foi enviada; fontes ainda precisam de avaliação.\n'+
                                         '\n\n'.join(row['title']+'\n'+row['url']+'\n'+row['snippet'] for row in rows))
                if not rows:
                    result.message += '\nNenhum resultado encontrado.'
                result.data['sources'] = rows
                return result
            if args and args[0] in ('url', 'summarize') and len(args) == 2:
                if args[0] == 'url' and not args[1].startswith('https://'):
                    raise ValueError('/research url exige HTTPS.')
                doc = self.document(args[1])
                extracts = summary(doc)
                message = 'Resumo extrativo — trechos selecionados, sem conclusões geradas por IA.\nFonte: '+doc.source+'\nObtido em: '+doc.fetched_at
                message += '\n'+'\n'.join(f"L{row['line']}: {row['text']}" for row in extracts)
                if doc.external:
                    message += '\nLinhas referem-se ao texto extraído desta leitura, não ao HTML original.'
                result = self.service.ok(message)
                result.data['sources'] = [dict(url=doc.source, title=doc.title, retrieved_at=doc.fetched_at)]
                return result
            if args and args[0] == 'compare' and len(args) == 3:
                docs = [self.document(value) for value in args[1:]]
                vocab = [set(dict(Counter(terms(' '.join(doc.lines))).most_common(20))) for doc in docs]
                message = 'Comparação documental; frequência de termos não comprova capacidade ou superioridade.\n'
                for index, doc in enumerate(docs):
                    message += f'\nFonte {index+1}: {doc.source}\n'+ '\n'.join(f"L{x['line']}: {x['text']}" for x in summary(doc)[:3])+'\n'
                message += '\nTermos compartilhados: '+', '.join(sorted(vocab[0] & vocab[1]))
                message += '\nSó entre os termos frequentes da fonte 1: '+', '.join(sorted(vocab[0]-vocab[1]))
                message += '\nSó entre os termos frequentes da fonte 2: '+', '.join(sorted(vocab[1]-vocab[0]))
                message += '\nRecomendação metodológica: verificar documentação e requisitos antes de escolher. Nenhuma recomendação de produto foi inferida.'
                return self.service.ok(message)
            return None  # Existing local term search retains its syntax.
        except FetchError as error:
            from skills.base import SkillResult
            return SkillResult(False, 'research', 'failed', 'Pesquisa indisponível: '+str(error)+'. Nenhum resultado foi inventado.')
        finally:
            self.client.checkpoint = lambda: None
