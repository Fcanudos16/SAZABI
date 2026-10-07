"""Repositórios SQLite: toda a SQL do projeto fica aqui."""
from __future__ import annotations

import json
import uuid
from typing import Dict, List, Optional, Sequence, Tuple

from database.database import Database
from database.models import (EVIDENCE_RANK, STATUSES, CompanyProfile, Hypothesis, Observation,
                             ResearchRun, SearchCriteria, Signal)
from utils.normalization import normalize_city, normalize_name, normalize_phone
from utils.timeutils import now_iso

_COLS = ["id", "name", "normalized_name", "legal_name", "website", "domain", "segment", "city",
         "city_key", "state", "country", "address", "phone", "phone_key", "estimated_size",
         "description", "social_profiles", "services", "units", "status", "investigated",
         "first_seen", "last_researched", "updated_at"]


def _values(p: CompanyProfile, now: str) -> tuple:
    return (p.id, p.name, p.normalized_name or normalize_name(p.name), p.legal_name, p.website,
            p.domain, p.segment, p.city, normalize_city(p.city), p.state, p.country, p.address,
            p.phone, normalize_phone(p.phone), p.estimated_size, p.description,
            json.dumps(p.social_profiles, ensure_ascii=False),
            json.dumps(p.services, ensure_ascii=False), p.units, p.status, int(p.investigated),
            p.first_seen, p.last_researched, now)


def _to_profile(r) -> CompanyProfile:
    return CompanyProfile(
        id=r["id"], name=r["name"], normalized_name=r["normalized_name"], legal_name=r["legal_name"],
        website=r["website"], domain=r["domain"], segment=r["segment"], city=r["city"],
        state=r["state"], country=r["country"], address=r["address"], phone=r["phone"],
        estimated_size=r["estimated_size"], description=r["description"],
        social_profiles=json.loads(r["social_profiles"] or "{}"),
        services=json.loads(r["services"] or "[]"), units=r["units"], status=r["status"],
        investigated=bool(r["investigated"]), first_seen=r["first_seen"],
        last_researched=r["last_researched"])


def _marks(n: int) -> str:
    return ", ".join("?" for _ in range(n))


class CompanyRepository:
    def __init__(self, db: Database):
        self.db = db

    def add(self, p: CompanyProfile) -> str:
        now = now_iso()
        p.id = p.id or uuid.uuid4().hex
        p.first_seen = p.first_seen or now
        self.db.execute(f"INSERT INTO companies ({', '.join(_COLS)}) VALUES ({_marks(len(_COLS))})",
                        _values(p, now))
        return p.id

    def update(self, p: CompanyProfile) -> None:
        sets = ", ".join(f"{c}=?" for c in _COLS[1:])
        self.db.execute(f"UPDATE companies SET {sets} WHERE id=?", _values(p, now_iso())[1:] + (p.id,))

    def get(self, company_id: str) -> Optional[CompanyProfile]:
        row = self.db.query_one("SELECT * FROM companies WHERE id=?", (company_id,))
        return _to_profile(row) if row else None

    def get_many(self, ids: Sequence[str]) -> List[CompanyProfile]:
        profiles = [self.get(i) for i in ids]
        return [p for p in profiles if p]

    def count(self) -> int:
        return self.db.query_one("SELECT COUNT(*) AS n FROM companies")["n"]

    def search_by_name(self, text: str) -> List[CompanyProfile]:
        key = normalize_name(text)
        if not key:
            return []
        rows = self.db.query("SELECT * FROM companies WHERE normalized_name = ?", (key,))
        if not rows:
            rows = self.db.query("SELECT * FROM companies WHERE normalized_name LIKE ? ORDER BY name",
                                 (f"%{key}%",))
        return [_to_profile(r) for r in rows]

    def candidates_for(self, p: CompanyProfile) -> List[CompanyProfile]:
        """Empresas já conhecidas que podem ser duplicatas de p (via índices)."""
        clauses: List[str] = []
        params: List[str] = []
        city_key = normalize_city(p.city)
        if city_key:
            clauses.append("city_key = ?")
            params.append(city_key)
        else:
            clauses.append("city_key IS NULL")
        if p.domain:
            clauses.append("domain = ?")
            params.append(p.domain)
        phone_key = normalize_phone(p.phone)
        if phone_key:
            clauses.append("phone_key = ?")
            params.append(phone_key)
        rows = self.db.query("SELECT * FROM companies WHERE " + " OR ".join(clauses), params)
        return [_to_profile(r) for r in rows]

    def set_status(self, company_id: str, status: str) -> None:
        if status not in STATUSES:
            raise ValueError(f"Status inválido: {status}")
        row = self.db.query_one("SELECT status FROM companies WHERE id=?", (company_id,))
        if row is None or row["status"] == status:
            return
        self.db.execute("UPDATE companies SET status=?, updated_at=? WHERE id=?",
                        (status, now_iso(), company_id))
        self.log_change(company_id, "status", row["status"], status)

    def log_change(self, company_id: str, field: str, old: Optional[str], new: Optional[str]) -> None:
        self.db.execute("INSERT INTO company_changes (company_id, field, old_value, new_value, changed_at) "
                        "VALUES (?,?,?,?,?)", (company_id, field, old, new, now_iso()))

    def list_changes(self, company_id: str) -> List[Tuple[str, str, str, str]]:
        rows = self.db.query("SELECT field, old_value, new_value, changed_at FROM company_changes "
                             "WHERE company_id=? ORDER BY id", (company_id,))
        return [(r["field"], r["old_value"], r["new_value"], r["changed_at"]) for r in rows]

    def delete(self, company_id: str) -> None:
        self.db.execute("DELETE FROM companies WHERE id=?", (company_id,))


class SourceRepository:
    """Observações (fatos + fonte + URL) coletadas por empresa."""

    def __init__(self, db: Database):
        self.db = db

    def replace_for_company(self, company_id: str, observations: Sequence[Observation]) -> None:
        with self.db.conn:
            self.db.conn.execute("DELETE FROM sources WHERE company_id=?", (company_id,))
            self.db.conn.executemany(
                "INSERT INTO sources (company_id, source_name, url, text, retrieved_at) VALUES (?,?,?,?,?)",
                [(company_id, o.source_name, o.url, o.text, o.retrieved_at or now_iso()) for o in observations])

    def list_for_company(self, company_id: str) -> List[Observation]:
        rows = self.db.query("SELECT * FROM sources WHERE company_id=? ORDER BY id", (company_id,))
        return [Observation(r["text"], r["source_name"], r["url"], r["retrieved_at"]) for r in rows]


class SignalRepository:
    def __init__(self, db: Database):
        self.db = db

    def replace_for_company(self, company_id: str, signals: Sequence[Signal]) -> None:
        with self.db.conn:
            self.db.conn.execute("DELETE FROM signals WHERE company_id=?", (company_id,))
            self.db.conn.executemany(
                "INSERT INTO signals (company_id, type, description, source, source_url, evidence, "
                "detected_at, confidence) VALUES (?,?,?,?,?,?,?,?)",
                [(company_id, s.type, s.description, s.source, s.source_url, s.evidence,
                  s.detected_at, s.confidence) for s in signals])

    def list_for_company(self, company_id: str) -> List[Signal]:
        rows = self.db.query("SELECT * FROM signals WHERE company_id=? ORDER BY id", (company_id,))
        return [Signal(id=r["id"], company_id=r["company_id"], type=r["type"],
                       description=r["description"], source=r["source"], source_url=r["source_url"],
                       evidence=r["evidence"], detected_at=r["detected_at"],
                       confidence=r["confidence"]) for r in rows]

    def count_map(self, ids: Sequence[str]) -> Dict[str, int]:
        if not ids:
            return {}
        rows = self.db.query(f"SELECT company_id, COUNT(*) AS n FROM signals WHERE company_id IN "
                             f"({_marks(len(ids))}) GROUP BY company_id", ids)
        return {r["company_id"]: r["n"] for r in rows}

    def total(self) -> int:
        return self.db.query_one("SELECT COUNT(*) AS n FROM signals")["n"]


class HypothesisRepository:
    def __init__(self, db: Database):
        self.db = db

    def replace_for_company(self, company_id: str, hypotheses: Sequence[Hypothesis]) -> None:
        with self.db.conn:
            self.db.conn.execute("DELETE FROM hypotheses WHERE company_id=?", (company_id,))
            self.db.conn.executemany(
                "INSERT INTO hypotheses (company_id, solution, reasons, evidence_level, created_at) "
                "VALUES (?,?,?,?,?)",
                [(company_id, h.solution, json.dumps(h.reasons, ensure_ascii=False),
                  h.evidence_level, h.created_at) for h in hypotheses])

    def list_for_company(self, company_id: str) -> List[Hypothesis]:
        rows = self.db.query("SELECT * FROM hypotheses WHERE company_id=? ORDER BY id", (company_id,))
        hyps = [Hypothesis(id=r["id"], company_id=r["company_id"], solution=r["solution"],
                           reasons=json.loads(r["reasons"] or "[]"),
                           evidence_level=r["evidence_level"], created_at=r["created_at"]) for r in rows]
        return sorted(hyps, key=lambda h: -EVIDENCE_RANK.get(h.evidence_level, 0))

    def best_level_map(self, ids: Sequence[str]) -> Dict[str, str]:
        if not ids:
            return {}
        rows = self.db.query(f"SELECT company_id, evidence_level FROM hypotheses WHERE company_id IN "
                             f"({_marks(len(ids))})", ids)
        best: Dict[str, str] = {}
        for r in rows:
            cur = best.get(r["company_id"])
            if cur is None or EVIDENCE_RANK.get(r["evidence_level"], 0) > EVIDENCE_RANK.get(cur, 0):
                best[r["company_id"]] = r["evidence_level"]
        return best

    def companies_with_min_level(self, min_level: str = "moderado") -> List[Tuple[str, str]]:
        """(company_id, melhor nível) das empresas não descartadas, melhores primeiro."""
        rows = self.db.query("SELECT h.company_id, h.evidence_level FROM hypotheses h "
                             "JOIN companies c ON c.id = h.company_id WHERE c.status != 'DISCARDED'")
        best: Dict[str, str] = {}
        for r in rows:
            cur = best.get(r["company_id"])
            if cur is None or EVIDENCE_RANK.get(r["evidence_level"], 0) > EVIDENCE_RANK.get(cur, 0):
                best[r["company_id"]] = r["evidence_level"]
        keep = [(cid, lvl) for cid, lvl in best.items() if EVIDENCE_RANK.get(lvl, 0) >= EVIDENCE_RANK[min_level]]
        return sorted(keep, key=lambda x: -EVIDENCE_RANK[x[1]])


_RUN_COLS = ["found", "duplicates", "new_count", "known_count", "ignored_count", "investigated",
             "with_data", "signals_count", "opportunities"]


def _to_run(r) -> ResearchRun:
    return ResearchRun(id=r["id"], query=r["query"] or "", started_at=r["started_at"],
                       segment=r["segment"], city=r["city"], state=r["state"], size=r["size"],
                       need=r["need"], silent=bool(r["silent"]), finished_at=r["finished_at"],
                       **{c: r[c] for c in _RUN_COLS})


class RunRepository:
    def __init__(self, db: Database):
        self.db = db

    def create(self, criteria: SearchCriteria, started_at: Optional[str] = None) -> ResearchRun:
        started = started_at or now_iso()
        query = criteria.raw_query or "; ".join(criteria.describe())
        cur = self.db.execute(
            "INSERT INTO research_runs (query, segment, city, state, size, need, silent, started_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (query, criteria.segment, criteria.city, criteria.state, criteria.size, criteria.need,
             int(criteria.silent), started))
        return ResearchRun(id=cur.lastrowid, query=query, started_at=started, segment=criteria.segment,
                           city=criteria.city, state=criteria.state, size=criteria.size,
                           need=criteria.need, silent=criteria.silent)

    def finish(self, run: ResearchRun) -> None:
        run.finished_at = run.finished_at or now_iso()
        sets = ", ".join(f"{c}=?" for c in _RUN_COLS)
        self.db.execute(f"UPDATE research_runs SET finished_at=?, {sets} WHERE id=?",
                        (run.finished_at, *[getattr(run, c) for c in _RUN_COLS], run.id))

    def add_company(self, run_id: int, company_id: str, is_new: bool) -> None:
        self.db.execute("INSERT OR IGNORE INTO run_companies (run_id, company_id, is_new) VALUES (?,?,?)",
                        (run_id, company_id, int(is_new)))

    def company_ids(self, run_id: int) -> List[str]:
        rows = self.db.query("SELECT company_id FROM run_companies WHERE run_id=? ORDER BY rowid", (run_id,))
        return [r["company_id"] for r in rows]

    def last(self) -> Optional[ResearchRun]:
        row = self.db.query_one("SELECT * FROM research_runs ORDER BY id DESC LIMIT 1")
        return _to_run(row) if row else None

    def recent(self, limit: int = 10) -> List[ResearchRun]:
        return [_to_run(r) for r in self.db.query("SELECT * FROM research_runs ORDER BY id DESC LIMIT ?", (limit,))]

    def between(self, start_iso: str, end_iso: str) -> List[ResearchRun]:
        rows = self.db.query("SELECT * FROM research_runs WHERE started_at >= ? AND started_at < ? "
                             "ORDER BY started_at, id", (start_iso, end_iso))
        return [_to_run(r) for r in rows]

    def count(self) -> int:
        return self.db.query_one("SELECT COUNT(*) AS n FROM research_runs")["n"]


class IgnoredRepository:
    def __init__(self, db: Database):
        self.db = db

    def add(self, company_id: str, reason: Optional[str] = None) -> None:
        self.db.execute("INSERT OR REPLACE INTO ignored_companies (company_id, reason, ignored_at) "
                        "VALUES (?,?,?)", (company_id, reason, now_iso()))

    def remove(self, company_id: str) -> None:
        self.db.execute("DELETE FROM ignored_companies WHERE company_id=?", (company_id,))

    def is_ignored(self, company_id: Optional[str]) -> bool:
        return bool(company_id) and self.db.query_one(
            "SELECT 1 FROM ignored_companies WHERE company_id=?", (company_id,)) is not None


class SavedRepository:
    def __init__(self, db: Database):
        self.db = db

    def add(self, company_id: str, note: Optional[str] = None) -> None:
        self.db.execute("INSERT OR REPLACE INTO saved_companies (company_id, note, saved_at) VALUES (?,?,?)",
                        (company_id, note, now_iso()))

    def remove(self, company_id: str) -> None:
        self.db.execute("DELETE FROM saved_companies WHERE company_id=?", (company_id,))

    def is_saved(self, company_id: Optional[str]) -> bool:
        return bool(company_id) and self.db.query_one(
            "SELECT 1 FROM saved_companies WHERE company_id=?", (company_id,)) is not None


class ConversationRepository:
    def __init__(self, db: Database):
        self.db = db

    def add(self, role: str, text: str) -> None:
        self.db.execute("INSERT INTO conversation_history (role, text, created_at) VALUES (?,?,?)",
                        (role, text, now_iso()))

    def recent(self, limit: int = 20) -> List[Tuple[str, str]]:
        rows = self.db.query("SELECT role, text FROM conversation_history ORDER BY id DESC LIMIT ?", (limit,))
        return [(r["role"], r["text"]) for r in reversed(rows)]


class NotificationRepository:
    def __init__(self, db: Database):
        self.db = db

    def add(self, kind: str, channel: str, message: str, company_id: Optional[str] = None) -> None:
        self.db.execute("INSERT INTO notifications (company_id, kind, channel, message, sent_at) "
                        "VALUES (?,?,?,?,?)", (company_id, kind, channel, message, now_iso()))

    def count(self) -> int:
        return self.db.query_one("SELECT COUNT(*) AS n FROM notifications")["n"]


class SettingsRepository:
    def __init__(self, db: Database):
        self.db = db

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        row = self.db.query_one("SELECT value FROM settings WHERE key=?", (key,))
        return row["value"] if row else default

    def set(self, key: str, value: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?,?,?)",
                        (key, value, now_iso()))
