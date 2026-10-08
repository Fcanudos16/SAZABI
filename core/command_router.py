"""Roteador de comandos: /comandos explícitos e linguagem natural -> Command.

Determinístico (regex). A IA só entra depois, para o que as regras não entendem.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from database.models import SearchCriteria
from utils.normalization import normalize_text, title_case_pt


@dataclass
class Command:
    name: str                              # search, investigate, company, results, interesting, history,
                                           # save, ignore, forget, status, help, set, exit, empty, unknown
    criteria: Optional[SearchCriteria] = None
    target: Optional[str] = None
    period: Optional[str] = None           # today | yesterday | last
    refresh: bool = False
    args: Optional[str] = None


SLASH_ALIASES = {
    "search": "search", "research": "search", "procure": "search",
    "investigate": "investigate", "investigar": "investigate", "investigue": "investigate",
    "company": "company", "empresa": "company",
    "results": "results", "resultados": "results",
    "interesting": "interesting", "interessantes": "interesting",
    "history": "history", "historico": "history", "histórico": "history",
    "save": "save", "salvar": "save", "ignore": "ignore", "ignorar": "ignore",
    "forget": "forget", "esquecer": "forget",
    "status": "status", "help": "help", "ajuda": "help", "?": "help",
    "set": "set", "exit": "exit", "quit": "exit", "sair": "exit",
}

SEGMENTS: List[Tuple[str, str]] = [
    (r"odont", "clínica odontológica"), (r"clinic", "clínica"),
    (r"restaurante|pizzaria|lanchonete", "restaurante"), (r"oficin|mecanic|auto ?center", "oficina"),
    (r"academia", "academia"), (r"salao|saloes|barbearia", "salão"), (r"imobili", "imobiliária"),
    (r"escritori|contabil|advocacia", "escritório"), (r"e-?commerce|loja virtual", "e-commerce"),
    (r"\bloja", "loja"), (r"industri", "indústria"), (r"startup", "startup"),
    (r"tecnologia|software house", "tecnologia"), (r"servico", "serviços"),
]
SIZES: List[Tuple[str, str]] = [(r"\bmicro", "micro"), (r"pequen", "pequena"),
                                (r"\bmedi[ao]s?\b", "média"), (r"grande", "grande")]
NEEDS: List[Tuple[str, str]] = [(r"automa", "automação"), (r"processos? (?:aparentemente )?manua", "processos manuais"),
                                (r"software|sistema", "software/sistemas")]

_GREETING = re.compile(r"^\s*sazabi\s*[,:\-]?\s*", re.I)
_CITY_CUT = re.compile(r"[,.;!?]|\s+(?:que|com|para|onde|cuja|cujo|e regi[aã]o|silencios\w*)\b", re.I)

_SAVE = re.compile(r"^(?:guard(?:e|ar|a)|salv(?:e|ar|a))\b\s*(.*)$", re.I)
_IGNORE = re.compile(r"^ignor(?:e|ar|a)\b\s*(.*)$", re.I)
_FORGET = re.compile(r"^(?:esque[cç](?:a|er|e)|apag(?:ue|ar)|delete|remova)\b\s*(.*)$", re.I)
_INVESTIGATE = re.compile(
    r"^(?:investig(?:ue|ar)|an[aá]lis(?:e|ar)|aprofunde|"
    r"(?P<again>pesquis(?:e|ar)\s+(?:novamente|de novo)|atualiz(?:e|ar)\s+(?:a\s+)?(?:investiga[cç][aã]o|pesquisa)))"
    r"\b\s*(?P<rest>.*)$", re.I)
_INVESTIGATE_COMPANY = re.compile(r"^(?:pesquis(?:e|ar)|procur(?:e|ar))\s+(?:a\s+)?empresa\s+(?P<rest>.+)$", re.I)
_SHOW_COMPANY = re.compile(r"^(?:me\s+)?(?:mostre|mostrar|exiba)\s+(?:a\s+)?empresa\s+(?P<rest>.+)$", re.I)
_SEARCH_VERB = re.compile(r"^(procur\w+|busc\w+|busqu\w+|ach\w+|encontr\w+|pesquis\w+|quero|preciso|faca|"
                          r"gostaria|descubra)\b")


def _period(n: str) -> Optional[str]:
    if "ontem" in n:
        return "yesterday"
    if "hoje" in n:
        return "today"
    if re.search(r"ultim[ao]s?", n):
        return "last"
    return None


def _clean_target(text: str, strip_article: bool = False) -> Optional[str]:
    s = text.strip(" .!?\"'")
    if strip_article:                      # "investigue a Oficina Silva" -> "Oficina Silva"
        s = re.sub(r"^(?:a|o|as|os)\s+(?=\S)", "", s, flags=re.I)
    s = re.sub(r"^(?:(?:essa|esta|aquela|a|o|d[aeo])\s+)?empresa\s+", "", s, flags=re.I)
    s = re.sub(r"^(?:essa|esta|aquela)\s+", "", s, flags=re.I)
    return None if s.lower() in {"", "empresa", "essa", "esta", "isso", "ela"} else s


def parse_criteria(text: str) -> SearchCriteria:
    n = normalize_text(text)
    criteria = SearchCriteria(raw_query=text.strip(), silent="silencios" in n)
    for pattern, value in SEGMENTS:
        if re.search(pattern, n):
            criteria.segment = value
            break
    if not criteria.segment:
        segment = re.split(r'\bem\s+', text, maxsplit=1, flags=re.I)[0]
        segment = re.sub(r'^(?:procure|buscar|busque|pesquise|encontre|quero|preciso de)\s+', '', segment, flags=re.I).strip()
        if segment:
            criteria.segment = segment[:150]
    for pattern, value in SIZES:
        if re.search(pattern, n):
            criteria.size = value
            break
    for pattern, value in NEEDS:
        if re.search(pattern, n):
            criteria.need = value
            break
    m = re.search(r"\bem\s+(.+)$", text, re.I)
    if m:
        piece = _CITY_CUT.split(m.group(1), maxsplit=1)[0].strip()
        if "/" in piece:
            piece, uf = piece.split("/", 1)
            criteria.state = uf.strip().upper() or None
        if piece and len(piece.split()) <= 5:
            criteria.city = title_case_pt(piece)
    return criteria


def route(text: str) -> Command:
    raw = _GREETING.sub("", (text or "").strip(), count=1).strip()
    if not raw:
        return Command("empty")
    if raw.startswith("/"):
        return _route_slash(raw)
    return _route_natural(raw)


def _route_slash(raw: str) -> Command:
    parts = raw[1:].split(None, 1)
    name = SLASH_ALIASES.get(parts[0].lower()) if parts else None
    rest = parts[1].strip() if len(parts) > 1 else ""
    if name == "search":
        return Command("search", criteria=parse_criteria(rest))
    if name == "investigate":
        refresh = "--refresh" in rest
        return Command("investigate", target=_clean_target(rest.replace("--refresh", "")), refresh=refresh)
    if name in ("company", "save", "ignore", "forget"):
        return Command(name, target=_clean_target(rest))
    if name in ("results", "history"):
        return Command(name, period=_period(normalize_text(rest)))
    if name in ("interesting", "status", "help", "exit"):
        return Command(name)
    if name == "set":
        return Command("set", args=rest)
    return Command("unknown")


def _route_natural(raw: str) -> Command:
    n = normalize_text(raw)
    if n in {"sair", "exit", "quit", "tchau"}:
        return Command("exit")
    if n in {"ajuda", "help", "o que voce faz", "o que voce sabe fazer"}:
        return Command("help")
    if n in {"status", "como voce esta"}:
        return Command("status")
    for regex, name in ((_SAVE, "save"), (_IGNORE, "ignore"), (_FORGET, "forget")):
        m = regex.match(raw)
        if m:
            return Command(name, target=_clean_target(m.group(1), True))
    m = _INVESTIGATE.match(raw)
    if m:
        rest = m.group("rest")
        if m.group("again"):
            rest = re.sub(r"^(?:da|do|de|das|dos)\s+", "", rest, flags=re.I)
        return Command("investigate", target=_clean_target(rest, True), refresh=bool(m.group("again")))
    m = _INVESTIGATE_COMPANY.match(raw)
    if m:
        return Command("investigate", target=_clean_target(m.group("rest"), True))
    m = _SHOW_COMPANY.match(raw)
    if m:
        return Command("company", target=_clean_target(m.group("rest"), True))
    if re.search(r"\b(o que (eu )?pesquisei|historico|minhas pesquisas|pesquisas (que )?(eu )?fiz)\b", n):
        return Command("history", period=_period(n))
    if re.search(r"interessantes|melhores oportunidades|quais oportunidades", n):
        return Command("interesting")
    if re.search(r"o que voce (encontrou|achou)|empresas encontradas|quais empresas (voce )?(encontrou|achou)"
                 r"|ultima pesquisa|^resultados?$", n):
        return Command("results", period=_period(n))
    if _SEARCH_VERB.match(n):
        return Command("search", criteria=parse_criteria(raw))
    return Command("unknown")
