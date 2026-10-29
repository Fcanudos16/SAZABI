"""Explicit public read-only smoke check. No .env, credentials, local file upload or paid API."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.config import Config
from core.bootstrap import build_agent

agent = build_agent(Config(database_path=':memory:', knowledge_language='en'))
failed = False
try:
    for query in ('/research web "Python programming language"',
                  '/research url https://docs.python.org/3/library/pathlib.html'):
        agent.handle(query)
        result = agent.last_skill_result
        print(query)
        print('STATUS:', result.status)
        print(result.message[:700])
        failed |= not result.success
finally:
    agent.db.close()
raise SystemExit(int(failed))
