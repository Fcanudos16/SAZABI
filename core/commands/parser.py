"""Transport-neutral parsing; no skill or provider logic."""
from dataclasses import dataclass
import re

MAX_INPUT = 2000

@dataclass(frozen=True)
class SlashCommand:
    name: str
    arguments: str = ''


def parse(text):
    if not isinstance(text, str) or len(text) > MAX_INPUT or '\x00' in text:
        raise ValueError('Limite: 2.000 caracteres; caracteres inválidos não são aceitos.')
    text = text.strip()
    if not text.startswith('/'):
        return None
    match = re.fullmatch(r'/([a-zA-Z][a-zA-Z0-9_-]*)(?:\s+(.*))?', text, re.S)
    if not match:
        raise ValueError('Comando inválido. Digite / para consultar os comandos.')
    return SlashCommand(match[1].lower(), (match[2] or '').strip())
