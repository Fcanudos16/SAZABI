"""Optional real network probe; no API key, no production database writes."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research.web_source import WebSource
from utils.http_client import HttpClient, FetchError

if __name__ == '__main__':
    page = WebSource(None).page('https://www.python.org/')
    assert 'Python' in page.title and page.text
    print('PASS: actual HTTPS, robots.txt and HTML extraction on python.org', flush=True)
    try:
        HttpClient().json('https://api.tavily.com/usage')
    except FetchError as error:
        assert error.status == 401, str(error)
        print('PASS: actual Tavily endpoint reachable; unauthenticated request rejected (401)', flush=True)
    else:
        raise AssertionError('Expected authentication requirement')
