# SAZABI — contexto compacto para outra IA

Revisão estática: **16/10/2026**. Mapa completo: `docs/PROJECT_MAP.md`, especialmente C (catálogo com símbolos/linhas/importadores), D/E (fluxos), I (arquivos por alteração) e K (lacunas). Foram catalogados 175 arquivos relevantes: 145 fontes Python/PYW e 30 configurações, recursos e referências. Nenhuma integração ou UI foi executada para produzir este mapa.

## Objetivo e arquitetura

Assistente local de inteligência comercial: busca empresas em páginas públicas, preserva observações com URL/data, detecta sinais determinísticos e sugere hipóteses compatíveis com serviços configurados. SQLite guarda empresas, pesquisas, histórico comercial, tarefas, avaliações e rascunhos. Score não comprova necessidade nem intenção de compra. Não há envio automático de abordagem às empresas.

Python + Tkinter/ttk + SQLite sem ORM + Win32/GDI+ via ctypes. HTTP/JSON/HTML usam biblioteca padrão; psutil coleta métricas; pytest/unittest validam contratos. Não há frontend web ou servidor HTTP do SAZABI encontrado. UI e lógica comunicam-se por threads/filas Python. LAYLA é outro serviço local, consumido por HTTP.

## Índice de arquivos e responsabilidades

Todos os caminhos abaixo são relativos à raiz do repositório.

| Área | Arquivos e responsabilidade |
|---|---|
| Inicialização | `main.py`: escolhe desktop/CLI/Telegram/backup/comando único; `desktop.py`: Tk e mainloop; `iniciar_sazabi.cmd` → `iniciar_sazabi.pyw`: pythonw sem console |
| Composição/configuração | `core/bootstrap.py`: build_agent e serviços; `core/config.py`: env/ambiente, defaults e YAML simples; `core/connection.py`: valida/salva Tavily/Groq |
| Agente/execução | `core/agent.py`: comandos e pipeline; `core/worker.py`: thread dona do banco, filas, cancelamento e manutenção; `core/memory.py`: conversa/settings/contexto scoped |
| Comandos | `core/command_router.py`: legado e linguagem natural; `core/commands/parser.py`: slash; `registry.py`: metadados/sugestões; `router.py`: despacho (estes três em core/commands) |
| Handlers | `core/lead_commands.py`: leads/tarefas/export; `core/commercial_commands.py`: perfil/estratégias/avaliação/draft; `core/maintenance_commands.py`: health/backup/integrity/maintenance |
| Saída/operação | `core/reports.py`: texto, fontes/ressalvas e ajuda; `core/dashboard.py`: projeção opcional de contagens, sem servidor; `core/maintenance.py`: backups/retention/alertas/refresh opcional |
| Skills | `skills/base.py`: SkillContext/SkillResult/checkpoint; `skills/registry.py`: registro/execução; `skills/search/skill.py`: adaptador /search; `skills/search/config.json`: enabled/timeout/allow_tavily |
| Pesquisa | `research/base.py`: interfaces; `company_finder.py`: descoberta/normalização/merge; `company_investigator.py`: TTL/coleta/preservação em falhas; `web_source.py`: Tavily/HTML/robots/extração conservadora (todos em research) |
| Análise determinística | `analysis/signal_detector.py`: regras/negações/canais existentes; `opportunity_analyzer.py`: hipóteses; `evidence_manager.py`: níveis de evidência; `scoring.py`: prioridade por sinal (todos em analysis) |
| Comercial | `analysis/qualification.py`: avaliação explicável 0–100; `commercial.py`: hash/cache/snapshots/drafts/prompt; `commercial_profile.py`: valida/edita perfil; `strategies.py`: plano, defaults e política de evidência (todos em analysis) |
| IA externa | `analysis/ai_provider.py`: Groq HTTPS, modelos e resumo limitado sem ferramentas/escrita no banco; não é LAYLA |
| Dados | `database/models.py`: dataclasses/constantes; `database.py`: schema/WAL/FKs/transações/backup; `repositories.py`: CRUD/histórico; `leads.py`: companies existentes, estágio/manual_fields/tarefas/export; `migrations.py`: versões 1–4; `recovery.py`: locks/reinício; `restore.py`: restore offline/rescue (todos em database) |
| LAYLA | `integrations/layla/bridge.py`: loopback, cookie/CSRF, endpoints e erros; `session.py`: thread/fila própria no mesmo diretório |
| Notificações | `notifications/notifier.py`: console/null; `telegram.py`: Bot API/polling/allowlist/rate limit no mesmo diretório |
| Shell visual | `ui/companion.py`: mascote, menu, janelas, eventos e preferências; `terminal.py`: resultados/última tentativa; `ai_terminal.py`: conversa LAYLA; `autocomplete.py`: sugestões locais (todos em ui) |
| Visual nativo | `ui/theme.py`: tema; `native.py`: Win32/foco/topmost/área útil; `sprites.py`: JPEG/hash/viewports/máscaras; `renderer.py`: pose/pálpebra/transição; `presentation.py`: corpo inteiro; `behavior.py`: sono/idle/trabalho/arraste; `motion.py`: deslocamentos; `interaction.py`: popup não modal; `effects.py`: bolhas/avisos (todos em ui) |
| Configuração visual opcional | `ui/preferences.py`: classe existente de conexões/modelos, sem campo de chave, mas nenhum item do menu atual chama open_settings; disponibilidade normal não confirmada |
| Relógios | `ui/countdown/timer_engine.py`: countdown monotônico; `commands.py`: português/HUD; `window.py`: janela manual; `stopwatch.py`: elapsed pesquisa; `embedded.py`: HUD terminal; `renderer.py`, `geometry.py`, `theme.py`: desenho comum (todos em ui/countdown) |
| Monitor | `ui/system_monitor.py`: janela; `system_monitor/service.py`: agregador/sampler pausável; `cpu.py`, `memory.py`, `disk.py`, `uptime.py`, `system_info.py`: sensores; `formatter.py`: unidades (estes em system_monitor) |
| Utilitários | `utils/normalization.py`: chaves; `deduplication.py`: identidade/possíveis duplicatas; `http_client.py`: transporte público limitado/SSRF/checkpoint; `logger.py`: rotação/segredos; `timeutils.py`: UTC e calendário local (todos em utils) |
| Ferramentas/testes | `run_tests.py`, `pytest.ini`, `tests/conftest.py`, `tests/factories.py`, `tests/mock_source.py`; `scripts/restore_backup.py`: explícito/offline; `scripts/phase5_audit.py`: live/replay; `scripts/phase5_review.py`: métricas históricas; `data/windowless_check.py`: diagnóstico não importado pelo launcher |
| Recursos/configs | `.env.example`, `services.yaml`, `commercial_profile.json`, `requirements.txt`, `.gitignore`; `assets/sazabi/original.jpg`, `states.json`, `animation.json`; `data/companion.json` é preferência local, não anexo público |
| Referências | README, OPERACAO, DESIGN, ATUALIZACAO_DESKTOP, AUDITORIA_FASE1 e FASE*.md são documentos históricos; código prevalece. `skills/search/SKILL.md` é especificação, não implementação integral; reports/phase5 contém artefatos históricos |

## Fluxos e fronteiras críticas

1. **Pesquisa `/search`:** CompanionApp.submit → AgentWorker.submit/fila → SazabiAgent.handle/_handle → CommandRouter → SkillRegistry → SearchSkill.execute → strategies.plan → agent._cmd_search/_run_search (lock) → _execute_search → CompanyFinder/WebSource/Tavily → normalize/deduplicate → _investigate/CompanyInvestigator → detector/analyzer/qualificação → repositories/SQLite → reports → SkillResult → worker.events → CompanionApp.poll/ResultTerminal.
2. **`/research`/linguagem natural:** roteador legado → mesmo pipeline do agente, sem adaptador de plano/política da Search Skill. Não alterar só a Skill para corrigir todos os caminhos.
3. **`/ai`:** retorna action=open_ai; desktop abre AITerminal. Só Enviar submete texto a LaylaSession/LaylaBridge. `/qualify-ai` prepara draft reduzido para revisão. Bridge consome GET `/`, GET `/api/configuracoes`, POST `/enviar`, POST `/novo_chat`; não são rotas do SAZABI.
4. **`/groq`:** _ai_summary → GroqProvider.summarize; até oito trechos de 600 caracteres com URL/data; exige finish_reason=stop/texto válido; não muda score/fatos. Groq está implementado; Ollama/Gemini/OpenRouter não foram encontrados no código atual.
5. **Banco:** uma base; lead é a própria company. Fonte atual e source_history são distintos. Avaliação preserva snapshot/hash. Campos manuais sobrevivem à coleta. Migrações até v4. Atomicidade/locks e thread dona do SQLite são obrigatórios para preservar comportamento.
6. **Desktop:** ocultar terminal não interrompe worker; estados de tarefa precedem autonomia; não emitir sucesso após falha. Countdown manual e stopwatch de pesquisa são independentes. Monitor não usa rede/banco.

Configuração backend em `.env`/ambiente, nunca frontend/log/anexo. Variáveis: DATABASE_PATH, CACHE_TTL_HOURS, DEFAULT_REGION, LOG_*, SEARCH_API_KEY/LIMIT, AI_PROVIDER/GROQ_API_KEY/GROQ_MODEL, TELEGRAM_BOT_TOKEN/ALLOWED_USER_IDS, LAYLA_URL/SESSION_COOKIE, COMMERCIAL_PROFILE_PATH. Compartilhar só `.env.example`. Search config atual tem allow_tavily=true: exige chave e usa créditos; não prometer busca gratuita. Perfil atual herda serviços de services.yaml e usa limites 40/70; a especificação Markdown tem números diferentes.

## Como solicitar somente os arquivos necessários

- Primeiro identificar entrada, lógica, persistência e apresentação afetadas. Consultar a linha da alteração em `docs/PROJECT_MAP.md`, seção I; não pedir o repositório inteiro.
- Pedir o arquivo principal inteiro e o teste de regressão mais próximo. Acrescentar modelo/contrato e chamador direto quando a mudança atravessar a fronteira. Se faltar evidência, pedir um segundo lote pequeno e explicar a dependência.
- Layout/tema: começar por ui/terminal.py ou ui/theme.py. Busca: skill.py + strategies.py ou web_source.py conforme o problema. Score: qualification.py + comercial/perfil. LAYLA: ai_terminal.py + bridge/session. Persistência: repository/leads + schema/migrations pertinentes.
- Pedir símbolos/chamadores específicos do catálogo quando um módulo grande exceder o limite; incluir imports e contexto do método. Não inventar função/rota ou presumir uso só porque existe import.
- Nunca solicitar `.env` real, banco/log/backup ou credenciais. Para bug de dados, pedir fixture sintética ou exportação mínima sanitizada. Para topmost, pedir somente as preferências não sensíveis necessárias.
- Antes de editar, conferir versão atual dos arquivos: este mapa é uma fotografia estática. Preservar arte, arquitetura nativa, único banco, histórico e contratos. Verificar imports locais que evitam ciclos entre repositories/leads/commercial antes de movê-los.

## Validação após uma alteração

Escolher testes por domínio na seção H do mapa e conferir os casos no catálogo C. Base: `python -m pytest -q` ou `python run_tests.py`; ambos confirmados pelo projeto, não executados nesta análise. Grupos: search (`test_slash_skills`, `test_phase7_strategies`, `test_phase4`), coleta (`test_real_pipeline`, `test_phase5_quality`, `test_backend_recovery`), comercial (`test_commercial`, `test_phase6_workflow`, `test_leads`), banco (`test_database`, `test_phase9_maintenance`), UI (`test_companion`, `test_animation`, `test_presentation`, verificadores native_*), IA (`test_layla_bridge`, `test_groq`), monitor (`test_system_monitor`), relógios (`test_countdown_logic`, `test_countdown_language`, `test_research_stopwatch`). Todos estão em tests/ com extensão .py.

Testes controlados não comprovam conectividade/conta real, autenticação da LAYLA instalada, foco entre apps, DPI ou monitores físicos. Diagnósticos de rede/Groq e auditoria live exigem ação explícita e podem usar credenciais/créditos. Lacunas completas em K: dados privados/gerados excluídos, UI e provedores não executados, acesso normal a Preferences não confirmado, dashboard apenas projeção opcional, documentação histórica/especificação parcialmente divergentes.
