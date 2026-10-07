"""Validate a real Tavily credential and update only its local configuration."""
import os
import re
import tempfile
from pathlib import Path

from research.web_source import TavilySearch, WebSource


def save_key(path, key):
    if not re.fullmatch(r'[A-Za-z0-9_-]{10,256}', key):
        raise ValueError('Formato de chave inválido. Cole somente a chave Tavily.')
    save_values(path, {'SEARCH_API_KEY': key})


def save_values(path, values):
    if any('\n' in value or '\r' in value for value in values.values()):
        raise ValueError('Configuração inválida.')
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = target.read_text(encoding='utf-8').splitlines() if target.exists() else []
    lines = [line for line in lines if line.split('=', 1)[0].strip() not in values]
    lines.extend(key + '=' + value for key, value in values.items())
    descriptor, temporary = tempfile.mkstemp(prefix='.sazabi-key-', dir=target.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            stream.write('\n'.join(lines) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def connect(agent, key):
    key = key.strip()
    if not re.fullmatch(r'[A-Za-z0-9_-]{10,256}', key):
        raise ValueError('Cole uma chave Tavily válida, sem espaços.')
    provider = TavilySearch(key, agent.config.search_limit)
    usage = provider.check_connection()
    save_key(agent.config.env_file, key)
    # Keep the current process consistent with load_config's environment precedence.
    os.environ['SEARCH_API_KEY'] = key
    agent.config.search_api_key = key
    source = WebSource(provider)
    agent.finder.sources = [source]
    agent.investigator.sources = [source]
    return usage


def configure_ollama(agent, model):
    from analysis.ai_provider import OllamaProvider
    if model:
        OllamaProvider(model).check_model()
    values = {'AI_PROVIDER': 'ollama' if model else 'none', 'OLLAMA_MODEL': model}
    save_values(agent.config.env_file, values)
    os.environ.update(values)
    agent.config.ai_provider = values['AI_PROVIDER']
    agent.config.ollama_model = model
