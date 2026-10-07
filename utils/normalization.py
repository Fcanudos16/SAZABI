"""Normalização determinística de nomes, domínios, telefones e textos."""
from __future__ import annotations

import re
import unicodedata
from typing import Optional
from urllib.parse import urlparse

LEGAL_SUFFIXES = {"ltda", "me", "epp", "eireli", "sa", "mei", "ss", "cia"}
SOCIAL_DOMAINS = {
    "instagram.com", "facebook.com", "linkedin.com", "wa.me", "whatsapp.com",
    "linktr.ee", "twitter.com", "x.com", "tiktok.com", "youtube.com",
}
LOWER_WORDS = {"de", "da", "do", "das", "dos", "e"}


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def normalize_text(text: Optional[str]) -> str:
    """minúsculas, sem acentos, espaços colapsados."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", strip_accents(text).lower()).strip()


def normalize_name(name: Optional[str]) -> str:
    """Nome comparável: sem acento/pontuação e sem sufixo societário no final."""
    text = normalize_text(name).replace("s/a", "sa")
    tokens = re.sub(r"[^a-z0-9 ]+", " ", text).split()
    while tokens and tokens[-1] in LEGAL_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def normalize_domain(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    candidate = url.strip()
    if "://" not in candidate:
        candidate = "http://" + candidate
    host = (urlparse(candidate).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host if "." in host else None


def is_social_domain(domain: str) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in SOCIAL_DOMAINS)


def company_domain(url: Optional[str]) -> Optional[str]:
    """Domínio próprio da empresa (redes sociais não contam como domínio)."""
    domain = normalize_domain(url)
    if domain is None or is_social_domain(domain):
        return None
    return domain


def normalize_phone(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("55") and len(digits) >= 12:
        digits = digits[2:]
    return digits if len(digits) >= 8 else None


def normalize_address(address: Optional[str]) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", normalize_text(address))).strip()


def normalize_city(city: Optional[str]) -> Optional[str]:
    return normalize_text(city) or None


def title_case_pt(text: str) -> str:
    words = text.strip().split()
    out = []
    for i, w in enumerate(words):
        lw = w.lower()
        out.append(lw if (i > 0 and lw in LOWER_WORDS) else lw.capitalize())
    return " ".join(out)
