"""Explicit Groq connectivity check; uses credentials from the private .env."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.config import load_config
from analysis.ai_provider import list_models, GroqError

if __name__ == '__main__':
    try:
        print('Modelos Groq: ' + ', '.join(list_models(load_config().groq_api_key)))
    except GroqError as error:
        print(str(error))
        raise SystemExit(1)
