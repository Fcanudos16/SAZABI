"""Bounded live audit and offline replay of actual captured public observations.

Live mode uses Tavily credits. Replay never makes network requests. Both use a
new audit database, never the production database or notifications.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.config import load_config
from core.bootstrap import build_agent
from research.web_source import TavilySearch, WebSource, PageParser
from research.base import SearchResult
from notifications.notifier import NullNotifier
from utils.http_client import FetchError, HttpClient
from utils.timeutils import now_iso
from analysis.commercial import CommercialService

QUERIES = ['/search clínicas em São Paulo, capital',
           '/search oficinas mecânicas em São Paulo, capital',
           '/search pet shops em São Paulo, capital']


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


class AuditProvider(TavilySearch):
    def __init__(self, key, capture, replay, persist):
        super().__init__(key, 10)
        self.capture, self.replay, self.persist = capture, replay, persist
        self.index = 0

    def search(self, query):
        if self.replay:
            row = self.capture['queries'][self.index]
            self.index += 1
            if row.get('error'):
                raise FetchError(row['error'])
            return [SearchResult(**hit) for hit in row['hits']]
        row = {'query': query, 'checked_at': now_iso()}
        self.capture['queries'].append(row)
        try:
            hits = super().search(query)
            row['hits'] = [asdict(hit) for hit in hits]
            return hits
        except FetchError as error:
            row['error'] = str(error)
            raise
        finally:
            self.persist()


class AuditSource(WebSource):
    def __init__(self, provider, capture, replay, persist):
        super().__init__(provider, HttpClient(interval=2, timeout=8))
        self.capture, self.replay, self.persist = capture, replay, persist

    def _original_dates(self, observations):
        if self.replay:
            stamps = {row['page']['url']:row['checked_at'] for row in self.capture['pages'].values() if 'page' in row}
            for observation in observations:
                observation.retrieved_at = stamps.get(observation.url, self.capture['started_at'])
        return observations

    def extract(self, page, city_filter=None):
        company = super().extract(page, city_filter)
        if company:
            self._original_dates(company.observations)
        return company

    def fetch_observations(self, company):
        return self._original_dates(super().fetch_observations(company))

    def search(self, criteria):
        companies = super().search(criteria)
        if self.replay:
            for hit in self.last_hits:
                hit['retrieved_at'] = self.capture['pages'].get(hit['url'], {}).get('checked_at', self.capture['started_at'])
        return companies

    def page(self, url):
        if self.replay:
            row = self.capture['pages'].get(url)
            if not row:
                raise FetchError('Página não capturada na coleta real; replay sem rede.')
            if row.get('error'):
                raise FetchError(row['error'], row.get('status'))
            page = PageParser()
            for key, value in row['page'].items():
                setattr(page, key, value)
            return page
        try:
            page = super().page(url)
            self.capture['pages'][url] = {'checked_at': now_iso(), 'page': {
                key: getattr(page, key) for key in ('url','documents','meta','links','title','text')}}
            return page
        except FetchError as error:
            self.capture['pages'][url] = {'checked_at': now_iso(), 'error': str(error), 'status': error.status}
            raise
        finally:
            self.persist()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('live','replay'), required=True)
    parser.add_argument('--capture', type=Path, default=Path('data/phase5/capture.json'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repeat-first', action='store_true', help='Replay-only duplicate/persistence validation.')
    args = parser.parse_args()
    replay = args.mode == 'replay'
    if args.repeat_first and not replay:
        parser.error('--repeat-first is offline only.')
    if not replay and args.capture.exists():
        parser.error('Use a new capture path; existing captures are immutable.')
    capture = json.loads(args.capture.read_text(encoding='utf-8')) if replay else {
        'kind':'real_public_capture', 'started_at':now_iso(), 'commands':QUERIES, 'queries':[], 'pages':{}}
    persist = (lambda: None) if replay else lambda: save(args.capture, capture)
    database = Path('data/phase5') / (uuid4().hex+'.db')
    config = load_config(db_path=str(database))
    config.search_limit = 10
    provider = AuditProvider(config.search_api_key, capture, replay, persist)
    source = AuditSource(provider, capture, replay, persist)
    agent = build_agent(config, notifier=NullNotifier(), sources=[source])
    agent.skills.get('search').timeout = 600
    report = {'kind':'replay_of_real_capture' if replay else 'live', 'started_at':now_iso(),
              'capture':str(args.capture), 'database':str(database), 'runs':[], 'companies':[]}
    try:
        commands = list(capture['commands'])
        if args.repeat_first:
            commands.append(commands[0])
        for index, command in enumerate(commands):
            if index == len(capture['commands']):
                provider.index = 0
            print('START:',command,flush=True)
            started = time.perf_counter()
            reply = agent.handle(command)
            elapsed = time.perf_counter()-started
            run = agent.runs.last()
            report['runs'].append({'command':command,'seconds':elapsed,'reply':reply,
                'skill_status':agent.last_skill_result.status,
                'run':asdict(run) if run else None,'hits':list(agent.finder.hits)})
            save(args.output, report)
            print('END:',agent.last_skill_result.status,'seconds:',round(elapsed,2),
                  'hits:',len(agent.finder.hits),'companies:',agent.companies.count(),flush=True)
        service = CommercialService(agent.db, config)
        for row in agent.db.query('SELECT id FROM companies ORDER BY name'):
            company = agent.companies.get(row['id'])
            report['companies'].append({'company':asdict(company),
                'observations':[asdict(o) for o in agent.sources.list_for_company(company.id)],
                'qualification':service.qualify(company.id)})
        report['finished_at'] = now_iso()
        report['counts_before_close'] = {table: agent.db.query_one('SELECT COUNT(*) AS n FROM '+table)['n']
            for table in ('companies','sources','research_runs','discovery_results','lead_evaluations')}
        save(args.output, report)
    finally:
        agent.db.close()
    # Read-only verification of persistence after closing the owning connection.
    import sqlite3
    with sqlite3.connect(database.resolve().as_uri()+'?mode=ro', uri=True) as reopened:
        report['counts_after_reopen'] = {table:reopened.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]
                                       for table in report['counts_before_close']}
    assert report['counts_after_reopen'] == report['counts_before_close']
    save(args.output, report)
    print('PERSISTENCE: PASS', report['counts_after_reopen'],flush=True)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
