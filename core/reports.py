"""Formatação de respostas (texto puro). Mantém fato, inferência e hipótese separados."""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from analysis.evidence_manager import level_label
from analysis.scoring import opportunity_score
from database.models import (CONFIDENCE_LABELS, CompanyProfile, Hypothesis, Observation,
                             ResearchRun, SearchCriteria, Signal)
from utils.timeutils import fmt_date

NA = "Não identificado"
PLATFORM_NAMES = {"whatsapp": "WhatsApp", "linkedin": "LinkedIn", "youtube": "YouTube", "tiktok": "TikTok"}
DISCLAIMER = ("As necessidades acima são hipóteses baseadas em informações públicas. Elas não "
              "confirmam que a empresa esteja procurando esse tipo de solução. A decisão de contato é da equipe.")

Entry = Tuple[CompanyProfile, Optional[str], int]       # (empresa, melhor nível de evidência, nº de sinais)


def _pl(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _bullets(items: Sequence[str]) -> str:
    return "\n".join(f"• {i}" for i in items)


def format_company_report(profile: CompanyProfile, observations: Sequence[Observation],
                          signals: Sequence[Signal], hypotheses: Sequence[Hypothesis],
                          ignored: bool = False, saved: bool = False) -> str:
    presence = []
    if profile.domain:
        presence.append(f"Site ({profile.domain})")
    presence += [PLATFORM_NAMES.get(k, k.capitalize()) for k in profile.social_profiles]
    size = f"{profile.estimated_size.capitalize()}, estimado" if profile.estimated_size else NA
    tags = [t for t, on in (("IGNORADA", ignored), ("SALVA", saved)) if on]

    lines = ["SAZABI", "", f"Empresa: {profile.name}" + (f"  [{', '.join(tags)}]" if tags else ""),
             f"Segmento: {profile.segment or NA}", f"Localização: {profile.location}", f"Porte: {size}",
             f"Site: {profile.website or NA}", f"Telefone: {profile.phone or NA}",
             f"Unidades identificadas: {profile.units if profile.units else NA}",
             "Presença digital:", _bullets(presence) if presence else "• " + NA,
             f"Status: {profile.status}", f"Última pesquisa: {fmt_date(profile.last_researched)}", ""]

    lines.append(f'Prioridade de investigação: {opportunity_score(signals)}/100 (não é probabilidade de venda).')
    if signals:
        lines.append("Sinais encontrados:")
        for s in signals:
            where = f"{s.source}" + (f" — {s.source_url}" if s.source_url else "")
            lines += [f"• Possível interpretação: {s.description}",
                      f"    Fato observado: {s.evidence}",
                      f"    Fonte: {where} — consultado em {fmt_date(s.detected_at)}",
                      f"    Confiança: {CONFIDENCE_LABELS.get(s.confidence, s.confidence)}"]
    else:
        lines.append("Sinais encontrados:\nEvidência insuficiente.")
    lines.append("")

    if hypotheses:
        lines.append("Possíveis oportunidades:")
        for h in hypotheses:
            lines.append(f"• Existe uma possível oportunidade para {h.solution}.")
            lines.append("    Por quê:")
            lines += [f"      – {r}" for r in h.reasons]
            lines.append(f"    Nível de evidência: {level_label(h.evidence_level)}")
    elif signals:
        lines.append("Possíveis oportunidades:\nNenhuma hipótese com evidência suficiente para os serviços configurados.")
    else:
        lines.append("Possíveis oportunidades:\nEvidência insuficiente.")

    lines += ["", f"Importante:\n{DISCLAIMER}"]
    sources = []
    for o in observations:
        item = f"{o.source_name}" + (f" — {o.url}" if o.url else "")
        if item not in sources:
            sources.append(item)
    if sources:
        lines += ["", "Fontes consultadas:", _bullets(sources)]
    return "\n".join(lines)


def format_search_report(run: ResearchRun, criteria: SearchCriteria, ranked: Sequence[Entry],
                         errors: Sequence[str], no_sources: bool, mock: bool) -> str:
    lines = ["Pesquisa concluída com limitações." if errors else "Pesquisa concluída.", "", "Critérios:", _bullets(criteria.describe() or ["Sem filtros"]), ""]
    if no_sources:
        lines.append("Configure sua chave Tavily na janela Configuração ou em SEARCH_API_KEY no .env.")
        return "\n".join(lines)
    lines += ["Resultados:", _bullets([
        _pl(run.found, "encontrada nas fontes", "encontradas nas fontes"),
        _pl(run.duplicates, "duplicada removida", "duplicadas removidas"),
        _pl(run.new_count, "nova", "novas"), _pl(run.known_count, "já conhecida", "já conhecidas"),
        _pl(run.ignored_count, "ignorada (não reapresentada)", "ignoradas (não reapresentadas)"),
        _pl(run.with_data, "investigada com observações públicas", "investigadas com observações públicas"),
        _pl(run.signals_count, "sinal detectado", "sinais detectados"),
        _pl(run.opportunities, "oportunidade potencial", "oportunidades potenciais")])]
    if errors:
        lines += ["", f"Atenção: fontes com erro nesta pesquisa: {', '.join(sorted(set(errors)))}."]
    if ranked:
        lines += ["", "Principais resultados:"]
        for i, (p, level, n) in enumerate(ranked[:5], 1):
            best = f"melhor hipótese: {level_label(level)}" if level and level != "insuficiente" else "evidência insuficiente"
            lines.append(f"{i}. {p.name} — {p.segment or NA} — {p.location} ({_pl(n, 'sinal', 'sinais')}; {best}; prioridade {opportunity_score(p.signals)}/100)")
            if p.website:
                lines.append('   Site: ' + p.website)
            for signal in p.signals[:2]:
                if signal.source_url:
                    lines.append(f'   Evidência: {signal.evidence[:200]} — {signal.source_url}')
            if p.hypotheses:
                lines.append('   Possível solução: ' + p.hypotheses[0].solution)
        lines += ["", 'Para detalhes: "investigue <nome da empresa>".']
    if mock:
        lines += ["", "(Modo mock: todas as empresas são fictícias.)"]
    else:
        lines += ['', 'Candidatos encontrados; aderência a segmento e porte exige revisão. Prioridade não é probabilidade de venda.']
    return "\n".join(lines)


def format_discovery(hits):
    pending = [hit for hit in hits if hit['status'] == 'pending']
    if not pending:
        return ''
    lines = ['', '', f'Páginas reais encontradas, pendentes de identificação ({len(pending)}):']
    for hit in pending:
        lines += [f"• {hit['title']}", f"  {hit['url']}",
                  f"  Trecho retornado pela Tavily (não verificado): {hit['snippet'][:500]}",
                  f"  Limitação: {hit['reason']}"]
    lines += ['Estas páginas não contam como empresas qualificadas. Para tentar um site oficial: /investigate <URL>.']
    return '\n'.join(lines)


def format_company_list(title: str, entries: Sequence[Entry]) -> str:
    if not entries:
        return f"{title}\n\nNenhuma empresa para mostrar."
    lines = [title, ""]
    for i, (p, level, n) in enumerate(entries, 1):
        best = level_label(level) if level and level != "insuficiente" else "sem hipótese"
        tag = f" [{p.status}]" if p.status not in ("NEW", "RESEARCHED") else ""
        lines.append(f"{i}. {p.name}{tag} — {p.segment or NA} — {p.location} ({_pl(n, 'sinal', 'sinais')}; evidência: {best}; prioridade {opportunity_score(p.signals)}/100)")
    return "\n".join(lines)


def format_history(runs: Sequence[ResearchRun]) -> str:
    if not runs:
        return "Não encontrei pesquisas nesse período."
    blocks = []
    for r in runs:
        blocks.append("\n".join([
            f"{fmt_date(r.started_at)}", f"Pesquisa: {r.query}",
            'Situação: ' + {'completed': 'concluída', 'partial': 'parcial', 'failed': 'falhou', 'running': 'sem conclusão', 'legacy': 'registro anterior'}.get(r.status, r.status) + (' — ' + r.error_message if r.error_message else ''),
            f"Encontradas: {r.found} | Duplicadas: {r.duplicates} | Novas: {r.new_count} | Já conhecidas: {r.known_count}",
            f"Investigadas: {r.investigated} | Sinais: {r.signals_count} | Oportunidades potenciais: {r.opportunities}"]))
    return "\n\n".join(blocks)


def format_opportunity_notification(profile: CompanyProfile, hypotheses: Sequence[Hypothesis]) -> str:
    needs = [h.solution for h in hypotheses[:3]]
    top = level_label(hypotheses[0].evidence_level) if hypotheses else "—"
    return "\n".join(["🔎 SAZABI", "", "Nova oportunidade potencial.", "", f"Empresa: {profile.name}",
                      f"Segmento: {profile.segment or NA}", f"Localização: {profile.location}",
                      "Possíveis necessidades (hipóteses):", _bullets(needs), f"Nível de evidência: {top}"])


def format_summary_notification(run: ResearchRun) -> str:
    return "\n".join(["🔎 SAZABI — resumo da pesquisa", "", f"Pesquisa: {run.query}",
                      f"{_pl(run.found, 'encontrada', 'encontradas')}, {_pl(run.duplicates, 'duplicada', 'duplicadas')}, "
                      f"{_pl(run.new_count, 'nova', 'novas')}.",
                      f"{_pl(run.signals_count, 'sinal', 'sinais')} e "
                      f"{_pl(run.opportunities, 'oportunidade potencial', 'oportunidades potenciais')}."])


def format_help() -> str:
    return """SAZABI — olheiro digital da software house

Fale naturalmente ou use comandos:

Pesquisar
  "procure pequenas clínicas em São Paulo"      /search clínicas em Campinas
  "faça uma pesquisa silenciosa por oficinas em Campinas"  (só envia o resumo)
Investigar
  "investigue a Oficina Silva"                  /investigate Oficina Silva
  "atualize a investigação da Oficina Silva"    /investigate Oficina Silva --refresh
  /company <nome>                               mostra o que já sei, sem pesquisar de novo
Consultar
  "o que você encontrou hoje?"                  /results [hoje|ontem]
  "quais empresas parecem interessantes?"       /interesting
  "o que eu pesquisei ontem?"                   /history [hoje|ontem]
Gerenciar
  "guarde essa empresa"                         /save [nome]
  "ignore essa empresa"                         /ignore [nome]
  /forget [nome]                                apaga os dados da empresa (pede confirmação)
Outros
  /ai <nome>                                   interpretação opcional via Ollama local
  /set region <cidade>                          região padrão para pesquisas
  /status    /help    sair

Tudo que eu apresento vem com fonte. Sinais são indicadores, não provas; hipóteses não são fatos."""


def format_status(info: Dict[str, object]) -> str:
    lines = ["SAZABI — status", ""]
    lines += [f"{k}: {v}" for k, v in info.items()]
    return "\n".join(lines)
