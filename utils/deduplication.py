"""Deduplicação determinística de empresas (domínio, telefone, endereço, nome)."""
from __future__ import annotations

from difflib import SequenceMatcher
from typing import Callable, List, Optional, Sequence, Tuple, TypeVar

from utils.normalization import (company_domain, normalize_address, normalize_city,
                                 normalize_name, normalize_phone)

T = TypeVar("T")


def _domain(x) -> Optional[str]:
    return getattr(x, "domain", None) or company_domain(getattr(x, "website", None))


def _names_match(a: str, b: str) -> bool:
    if not a or not b:
        return False
    if a == b:
        return True
    ta, tb = set(a.split()), set(b.split())
    small, big = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    if len(small) >= 2 and small <= big:      # "oficina silva" ⊂ "oficina silva auto center"
        return True
    return SequenceMatcher(None, a, b).ratio() >= 0.92


def is_same_company(a, b) -> bool:
    """True quando há evidência suficiente de que a e b são a mesma empresa.

    Regras, em ordem: mesmo domínio próprio; mesmo telefone; mesma cidade +
    mesmo endereço + nome parecido; mesma cidade + nome equivalente.
    """
    da, db_ = _domain(a), _domain(b)
    if da and da == db_:
        return True
    pa, pb = normalize_phone(getattr(a, "phone", None)), normalize_phone(getattr(b, "phone", None))
    if pa and pa == pb:
        return True
    if normalize_city(getattr(a, "city", None)) != normalize_city(getattr(b, "city", None)):
        return False
    na, nb = normalize_name(a.name), normalize_name(b.name)
    aa, ab = normalize_address(getattr(a, "address", None)), normalize_address(getattr(b, "address", None))
    if aa and aa == ab and SequenceMatcher(None, na, nb).ratio() >= 0.6:
        return True
    return _names_match(na, nb)


def deduplicate(items: Sequence[T], merge: Callable[[T, T], T]) -> Tuple[List[T], int]:
    """Remove duplicatas dentro de um lote. Retorna (únicos, nº de duplicatas)."""
    unique: List[T] = []
    duplicates = 0
    for item in items:
        for i, kept in enumerate(unique):
            if is_same_company(kept, item):
                unique[i] = merge(kept, item)
                duplicates += 1
                break
        else:
            unique.append(item)
    return unique, duplicates


def find_existing(item, candidates: Sequence[T]) -> Optional[T]:
    return next((c for c in candidates if is_same_company(c, item)), None)
