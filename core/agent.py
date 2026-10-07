"""Núcleo do SAZABI: interpreta pedidos, orquestra o pipeline e responde.

Independente da interface (CLI hoje, Telegram depois): recebe texto, devolve texto.
Pipeline: pesquisa -> normalização -> deduplicação -> investigação -> sinais -> hipóteses -> banco.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from analysis.evidence_manager import rank
from analysis.scoring import opportunity_score
from analysis.opportunity_analyzer import OpportunityAnalyzer
from analysis.signal_detector import SignalDetector
from core import reports
from core.command_router import Command, route
from core.config import Config
from core.memory import Memory
from database.database import Database
from database.models import CompanyProfile, Hypothesis, Observation, SearchCriteria, Signal
from database.repositories import (CompanyRepository, HypothesisRepository, IgnoredRepository,
                                   NotificationRepository, RunRepository, SavedRepository,
                                   SignalRepository, SourceRepository)
from notifications.notifier import Notifier
from research.company_finder import CompanyFinder, build_profile, merge_profiles
from research.company_investigator import CompanyInvestigator
from utils.deduplication import deduplicate, find_existing
from utils.normalization import normalize_name, normalize_text, title_case_pt
from utils.timeutils import day_bounds, now_iso

log = logging.getLogger("sazabi.agent")

OPPORTUNITY_MIN_RANK = rank("moderado")
YES = {"sim", "s", "confirmo", "confirmar", "pode", "ok"}
NO = {"nao", "n", "cancelar", "cancela"}


@dataclass
class Outcome:
    profile: CompanyProfile
    observations: List[Observation]
    signals: List[Signal]
    hypotheses: List[Hypothesis]
    from_cache: bool


class SazabiAgent:
    def __init__(self, config: Config, db: Database, finder: CompanyFinder,
                 investigator: CompanyInvestigator, detector: SignalDetector,
                 analyzer: OpportunityAnalyzer, notifier: Notifier):
        self.config, self.db = config, db
        self.finder, self.investigator = finder, investigator
        self.detector, self.analyzer, self.notifier = detector, analyzer, notifier
        self.companies = CompanyRepository(db)
        self.sources = SourceRepository(db)
        self.signals = SignalRepository(db)
        self.hypotheses = HypothesisRepository(db)
        self.runs = RunRepository(db)
        self.ignored = IgnoredRepository(db)
        self.saved = SavedRepository(db)
        self.notifications = NotificationRepository(db)
        self.memory = Memory(db, config.session_scope)
        self._pending: Optional[Dict] = None      # pergunta aguardando resposta (região / confirmação)

    # ------------------------------------------------------------------ entrada
    def handle(self, text: str) -> str:
        import re
        if re.search(r'\btvly-[A-Za-z0-9_-]+', text):
            return 'Use o campo protegido em Configuração para informar a chave Tavily. Ela não foi salva na conversa.'
        if text.strip() == '/ai' or text.strip().startswith('/ai '):
            return self._ai_summary(text.strip()[3:].strip())
        self.memory.log_turn("user", text)
        try:
            reply = self._dispatch(route(text), text)
        except Exception:
            log.exception("Erro ao processar mensagem")
            reply = "Ocorreu um erro interno ao processar o pedido. O detalhe foi registrado no log."
        self.memory.log_turn("assistant", reply)
        return reply

    def _ai_summary(self, target):
        if self.config.mock or self.config.ai_provider != 'ollama':
            return 'IA desativada. Abra Configuração → IA local (Ollama), selecione um modelo instalado e ative.'
        profile, error = self._resolve_company(target)
        if error:
            return error
        try:
            from analysis.ai_provider import OllamaProvider
            text = OllamaProvider(self.config.ollama_model).summarize(self.sources.list_for_company(profile.id))
            return 'Interpretação por IA (não validada; não altera dados nem prioridade):\n' + text
        except ValueError as error:
            return 'Interpretação indisponível: ' + str(error)
        except Exception:
            return 'IA local indisponível. Os relatórios determinísticos continuam disponíveis.'

    def _dispatch(self, cmd: Command, text: str) -> str:
        if self._pending:
            reply = self._resolve_pending(cmd, text)
            if reply is not None:
                return reply
        handlers = {
            "empty": lambda: "Pode falar. Digite /help para ver o que sei fazer.",
            "search": lambda: self._cmd_search(cmd.criteria),
            "investigate": lambda: self._cmd_investigate(cmd.target, cmd.refresh),
            "company": lambda: self._cmd_company(cmd.target),
            "results": lambda: self._cmd_results(cmd.period),
            "interesting": self._cmd_interesting,
            "history": lambda: self._cmd_history(cmd.period),
            "save": lambda: self._cmd_save(cmd.target),
            "ignore": lambda: self._cmd_ignore(cmd.target),
            "forget": lambda: self._cmd_forget(cmd.target),
            "status": self._cmd_status,
            "help": reports.format_help,
            "set": lambda: self._cmd_set(cmd.args or ""),
            "exit": lambda: "Até logo.",
            "unknown": lambda: ("Não entendi o pedido. Exemplos: \"procure clínicas em Campinas\", "
                                "\"investigue a Oficina Silva\". Digite /help para ver tudo."),
        }
        return handlers[cmd.name]()

    def _resolve_pending(self, cmd: Command, text: str) -> Optional[str]:
        pending, n = self._pending, normalize_text(text).strip(" .!?")
        if pending["type"] == "region":
            if n in NO or n in {"deixa", "deixa pra la"}:
                self._pending = None
                return "Pesquisa cancelada."
            if cmd.name == "unknown":
                self._pending = None
                criteria: SearchCriteria = pending["criteria"]
                criteria.city = title_case_pt(text.strip(" .!?"))[:60]
                return self._run_search(criteria)
            self._pending = None
            return None
        if pending["type"] == "forget":
            self._pending = None
            if n in YES:
                self.companies.delete(pending["company_id"])
                return f"Dados de {pending['name']} apagados. Se ela aparecer em uma nova pesquisa, será tratada como nova."
            if n in NO:
                return "Ok, nada foi apagado."
            return None
        self._pending = None
        return None

    # ------------------------------------------------------------------ pesquisa
    def _cmd_search(self, criteria: SearchCriteria) -> str:
        if not criteria.city:
            region = self.memory.get_setting("region") or self.config.default_region
            if region:
                criteria.city = region
            else:
                self._pending = {"type": "region", "criteria": criteria}
                return "Qual região devo pesquisar?"
        return self._run_search(criteria)

    def _run_search(self, criteria: SearchCriteria) -> str:
        if not self.finder.sources:
            return 'Pesquisa não iniciada. Abra Configuração e conecte sua chave Tavily, ou preencha SEARCH_API_KEY no .env.'
        run = self.runs.create(criteria)
        log.info("Pesquisa iniciada: %s", run.query)
        self.finder.errors, self.investigator.errors = [], []
        raws = self.finder.find(criteria)
        for hit in self.finder.hits:
            self.db.execute('INSERT INTO discovery_results (run_id,title,url,snippet,retrieved_at,status,reason) VALUES (?,?,?,?,?,?,?)',
                            (run.id, *(hit[key] for key in ('title', 'url', 'snippet', 'retrieved_at', 'status', 'reason'))))
        run.found = len(raws)
        log.info("%d empresas encontradas", run.found)

        profiles = [build_profile(r) for r in raws]
        unique, run.duplicates = deduplicate(profiles, merge_profiles)
        log.info("%d duplicatas removidas", run.duplicates)

        ranked: List[Tuple[CompanyProfile, Optional[str], int]] = []
        for candidate in unique:
            existing = find_existing(candidate, self.companies.candidates_for(candidate))
            if existing:
                if self.ignored.is_ignored(existing.id):
                    run.ignored_count += 1
                    continue
                profile, is_new = merge_profiles(existing, candidate), False
                self.companies.update(profile)
                run.known_count += 1
            else:
                profile, is_new = candidate, True
                self.companies.add(profile)
                run.new_count += 1
            self.runs.add_company(run.id, profile.id, is_new)

            outcome = self._investigate(profile, refresh=False)
            run.investigated += 1
            run.with_data += 1 if outcome.observations else 0
            run.signals_count += len(outcome.signals)
            best = outcome.hypotheses[0].evidence_level if outcome.hypotheses else None
            if best and rank(best) >= OPPORTUNITY_MIN_RANK:
                run.opportunities += 1
            ranked.append((profile, best, len(outcome.signals)))

        ranked.sort(key=lambda e: (-opportunity_score(e[0].signals), -(rank(e[1]) if e[1] else 0), e[0].name))
        errors = self.finder.errors + self.investigator.errors
        run.status = 'failed' if self.finder.errors and not raws and not self.finder.hits else 'partial' if errors else 'completed'
        run.error_message = '; '.join(errors)
        self.runs.finish(run)
        self.memory.set_last_run(run.id)
        log.info("%d empresas investigadas, %d sinais detectados", run.investigated, run.signals_count)
        reply = reports.format_search_report(run, criteria, ranked, errors,
                                             no_sources=not self.finder.sources, mock=self.config.mock)
        if errors and not raws and not self.finder.hits:
            reply = 'Pesquisa não concluída.\n' + '\n'.join(errors)
        reply += reports.format_discovery(self.finder.hits)
        if self.finder.sources and not (errors and not raws):
            self._notify_run(run, criteria, ranked)
        return reply

    def _notify_run(self, run, criteria: SearchCriteria, ranked) -> None:
        if not criteria.silent:     # modo silencioso: só o resumo
            top = [(p, best) for p, best, _ in ranked if best and rank(best) >= OPPORTUNITY_MIN_RANK][:3]
            for p, _ in top:
                self._send("opportunity", reports.format_opportunity_notification(
                    p, self.hypotheses.list_for_company(p.id)), p.id)
        self._send("summary", reports.format_summary_notification(run))

    def _send(self, kind: str, message: str, company_id: Optional[str] = None) -> None:
        if self.notifier.channel == 'none':
            return
        if company_id and self.db.query_one(
                'SELECT id FROM notifications WHERE company_id=? AND kind=? AND channel=? AND message=?',
                (company_id, kind, self.notifier.channel, message)):
            return
        try:
            self.notifier.send(message)
            self.notifications.add(kind, self.notifier.channel, message, company_id)
        except Exception:
            log.exception("Falha ao enviar notificação (%s)", kind)

    # ------------------------------------------------------------------ investigação
    def _investigate(self, profile: CompanyProfile, refresh: bool) -> Outcome:
        stored = self.sources.list_for_company(profile.id)
        result = self.investigator.investigate(profile, refresh=refresh, stored=stored)
        if result.from_cache:
            profile.observations = result.observations
            profile.signals = self.signals.list_for_company(profile.id)
            profile.hypotheses = self.hypotheses.list_for_company(profile.id)
            return Outcome(profile, result.observations, profile.signals, profile.hypotheses, True)

        signals = self.detector.detect(profile, result.observations)
        hypotheses = self.analyzer.analyze(profile, signals)
        self.sources.replace_for_company(profile.id, result.observations)
        self.signals.replace_for_company(profile.id, signals)
        self.hypotheses.replace_for_company(profile.id, hypotheses)
        profile.observations, profile.signals, profile.hypotheses = result.observations, signals, hypotheses
        profile.investigated, profile.last_researched = True, now_iso()
        if profile.status == "NEW":
            self.companies.set_status(profile.id, "RESEARCHED")
            profile.status = "RESEARCHED"
        self.companies.update(profile)
        return Outcome(profile, result.observations, signals, hypotheses, False)

    def _resolve_company(self, target: Optional[str], allow_lookup: bool = False
                         ) -> Tuple[Optional[CompanyProfile], Optional[str]]:
        if not target:
            last = self.memory.last_company_id()
            profile = self.companies.get(last) if last else None
            if profile:
                return profile, None
            return None, "Qual empresa? Informe o nome (ex.: /investigate Oficina Silva)."
        matches = self.companies.search_by_name(target)
        if len(matches) > 1:
            exact = [m for m in matches if m.normalized_name == normalize_name(target)]
            if len(exact) == 1:
                return exact[0], None
            names = "\n".join(f"• {m.name} ({m.location})" for m in matches[:8])
            return None, f"Encontrei mais de uma empresa parecida:\n{names}\nEspecifique o nome."
        if matches:
            return matches[0], None
        if allow_lookup:
            raw = self.finder.lookup(target)
            if raw:
                profile = build_profile(raw)
                existing = find_existing(profile, self.companies.candidates_for(profile))
                if existing:
                    return existing, None
                self.companies.add(profile)
                return profile, None
            if self.finder.errors:
                return None, 'Investigação não concluída: ' + '; '.join(self.finder.errors)
        return None, f'Não identifiquei a empresa "{target}" no histórico nem nas fontes disponíveis.'

    def _cmd_investigate(self, target: Optional[str], refresh: bool) -> str:
        self.investigator.errors = []
        profile, msg = self._resolve_company(target, allow_lookup=True)
        if msg:
            return msg
        outcome = self._investigate(profile, refresh=refresh)
        self.memory.set_last_company(profile.id)
        text = self._company_report(profile, outcome)
        if self.investigator.errors:
            text += '\n\nFonte indisponível nesta tentativa; dados anteriores não confirmam a situação atual.'
        if outcome.from_cache:
            text += (f"\n\n(Resultado em cache da pesquisa de {reports.fmt_date(profile.last_researched)}. "
                     f'Para refazer: "atualize a investigação da {profile.name}".)')
        return text

    def _company_report(self, profile: CompanyProfile, outcome: Outcome) -> str:
        return reports.format_company_report(profile, outcome.observations, outcome.signals,
                                             outcome.hypotheses, self.ignored.is_ignored(profile.id),
                                             self.saved.is_saved(profile.id))

    def _cmd_company(self, target: Optional[str]) -> str:
        profile, msg = self._resolve_company(target)
        if msg:
            return msg
        self.memory.set_last_company(profile.id)
        if not profile.investigated:
            return f"{profile.name} ainda não foi investigada. Use: investigue {profile.name}"
        return reports.format_company_report(
            profile, self.sources.list_for_company(profile.id), self.signals.list_for_company(profile.id),
            self.hypotheses.list_for_company(profile.id), self.ignored.is_ignored(profile.id),
            self.saved.is_saved(profile.id))

    # ------------------------------------------------------------------ gestão
    def _cmd_save(self, target: Optional[str]) -> str:
        profile, msg = self._resolve_company(target)
        if msg:
            return msg
        self.ignored.remove(profile.id)
        self.saved.add(profile.id)
        self.companies.set_status(profile.id, "SAVED")
        self.memory.set_last_company(profile.id)
        return f"Empresa salva no histórico de oportunidades: {profile.name}."

    def _cmd_ignore(self, target: Optional[str]) -> str:
        profile, msg = self._resolve_company(target)
        if msg:
            return msg
        self.saved.remove(profile.id)
        self.ignored.add(profile.id, "ignorada pelo usuário")
        self.companies.set_status(profile.id, "DISCARDED")
        return (f"Ok. Vou ignorar {profile.name}: ela não será apresentada novamente em novas pesquisas. "
                f"(Para voltar atrás: \"guarde {profile.name}\".)")

    def _cmd_forget(self, target: Optional[str]) -> str:
        profile, msg = self._resolve_company(target)
        if msg:
            return msg
        self._pending = {"type": "forget", "company_id": profile.id, "name": profile.name}
        return (f"Vou apagar todos os dados de {profile.name} (sinais, hipóteses, histórico). "
                "Isso não pode ser desfeito. Confirma? (sim/não)")

    def _cmd_set(self, args: str) -> str:
        parts = args.split(None, 1)
        if len(parts) == 2 and parts[0].lower() in ("region", "regiao", "região"):
            region = title_case_pt(parts[1])
            self.memory.set_setting("region", region)
            return f"Região padrão definida: {region}."
        return "Uso: /set region <cidade>"

    # ------------------------------------------------------------------ consultas
    def _entries(self, profiles: List[CompanyProfile]) -> List[reports.Entry]:
        ids = [p.id for p in profiles]
        best, counts = self.hypotheses.best_level_map(ids), self.signals.count_map(ids)
        entries = [(p, best.get(p.id), counts.get(p.id, 0)) for p in profiles]
        for profile in profiles:
            profile.signals = self.signals.list_for_company(profile.id)
        return sorted(entries, key=lambda e: (-opportunity_score(e[0].signals), -(rank(e[1]) if e[1] else 0), e[0].name))

    def _runs_for(self, period: Optional[str]):
        if period in ("today", "yesterday"):
            return self.runs.between(*day_bounds(period))
        last = self.runs.last()
        return [last] if last else []

    def _cmd_results(self, period: Optional[str]) -> str:
        runs = self._runs_for(period)
        if not runs:
            return "Não encontrei pesquisas nesse período."
        ids: List[str] = []
        for r in runs:
            ids += [i for i in self.runs.company_ids(r.id) if i not in ids]
        profiles = self.companies.get_many(ids)
        label = {"today": "de hoje", "yesterday": "de ontem"}.get(period, f'da última pesquisa ("{runs[0].query}")')
        if profiles:
            self.memory.set_last_company(profiles[0].id) if len(profiles) == 1 else None
        hits = [dict(hit) for run in runs for hit in self.db.query('SELECT * FROM discovery_results WHERE run_id=?', (run.id,))]
        failures = '\n'.join(r.error_message for r in runs if r.error_message)
        return reports.format_company_list(f"Empresas encontradas {label}:", self._entries(profiles)) + reports.format_discovery(hits) + ('\nFalhas registradas: ' + failures if failures else '')

    def _cmd_interesting(self) -> str:
        pairs = self.hypotheses.companies_with_min_level("moderado")
        profiles = [p for p in (self.companies.get(cid) for cid, _ in pairs) if p and p.status != 'DISCARDED']
        return reports.format_company_list(
            "Empresas com hipóteses de evidência moderada ou forte (ainda hipóteses, não fatos):",
            self._entries(profiles)[:10])

    def _cmd_history(self, period: Optional[str]) -> str:
        if period in ("today", "yesterday"):
            runs = self.runs.between(*day_bounds(period))
        else:
            runs = self.runs.recent(10)
        return reports.format_history(runs)

    def _cmd_status(self) -> str:
        return reports.format_status({
            "Ambiente": self.config.env, "Modo": "mock (dados fictícios)" if self.config.mock else "real",
            "Banco": self.config.database_path, "Fontes ativas": ", ".join(s.name for s in self.finder.sources) or "nenhuma",
            "Região padrão": self.memory.get_setting("region") or self.config.default_region or "não definida",
            "Empresas no banco": self.companies.count(), "Pesquisas realizadas": self.runs.count(),
            "Sinais registrados": self.signals.total(), "Cache": f"{self.config.cache_ttl_hours:g} h",
            "Serviços configurados": ", ".join(self.config.services)})
