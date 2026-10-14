# SAZABI — auditoria técnica de prospecção, fase 1

Data: 14/10/2026. Base auditada: commit `8a078e0`. Escopo: diagnóstico do código existente e correções pequenas de defeitos reproduzidos. Nenhuma alteração de arte, posicionamento, arquitetura de integração ou provedor.

## 1. Arquitetura identificada

- `main.py`: entrada padrão; carrega `.env`/ambiente e `services.yaml`, configura logs e escolhe desktop, CLI, comando único, backup ou Telegram. `iniciar_sazabi.cmd`/`.pyw` iniciam o desktop local.
- `desktop.py` → `ui/companion.py`: aplicação Tkinter/Win32 com mascote, terminal secundário, preferências e monitor. Sem servidor web do SAZABI.
- `core/worker.py`: thread proprietária do agente/SQLite, filas de comandos e eventos. O Tk recebe eventos por polling; a pesquisa não roda na thread gráfica. `submit()` reserva a execução sob lock e recusa duplicatas.
- `core/commands/{parser,registry,router}.py`: parser Slash, catálogo e despacho de `/search` e `/ai`. `core/command_router.py` permanece responsável pelos comandos legados e linguagem natural. São camadas com responsabilidades distintas, embora a coexistência exija cuidado ao adicionar aliases.
- `skills/search/skill.py`, `skills/{base,registry}.py`: contrato `SkillResult`, configuração, bloqueio de custos e adaptação ao pipeline existente. `skills/search/SKILL.md` é especificação; sua presença NÃO significa que todas as regras foram implementadas ou que um modelo a executa.
- `research/`: descoberta, coleta, extração e cache. `analysis/`: regras determinísticas, sinais, hipóteses e pontuação antiga. `core/reports.py`: apresentação textual.
- `database/`: SQLite já implementado, WAL, foreign keys, transações/savepoints e backup. Guarda empresas, fontes, sinais, hipóteses, pesquisas, páginas pendentes, preferências e histórico. Persistência não é uma funcionalidade inteiramente futura.
- `integrations/layla/` e `ui/ai_terminal.py`: transporte HTTP local, worker próprio e terminal independente.
- Dependências declaradas: `psutil>=5.9.0` (monitor) e `pytest>=7` (testes). Python padrão fornece SQLite, HTTP, JSON, threading, Tkinter e ctypes. No Python local inspecionado: psutil 7.2.2, pytest 9.1.1. Os testes completos usam o runtime/dependências locais de teste já existentes.

## 2. Fluxo real de `/search`

1. Entrada/atalho Nova pesquisa → `CompanionApp.submit()` valida tamanho/NUL/comando, protege formato de chave Tavily e marca interface ocupada.
2. `AgentWorker.submit()` recusa concorrência/fechamento; publica `queued` e entrega uma `CommandRequest`.
3. `SazabiAgent.handle()` usa parser e registro; chama `SearchSkill.execute()` automaticamente, sem LAYLA ou Ollama.
4. A skill interpreta critérios, usa região salva ou `DEFAULT_REGION`, ou pede somente a região. A resposta retoma a mesma skill.
5. Examina fontes de descoberta E investigação. Tavily não possui o contrato de custo zero; ter uma chave não altera esse fato. Hoje não existe adaptador de produção gratuito compatível. Resultado real: `unconfigured`, nenhuma consulta, nenhuma pesquisa concluída fictícia. Isso é uma limitação funcional conhecida, não falha de reconhecimento do comando.
6. Quando há fonte compatível injetada, o adaptador chama o pipeline do agente: criar pesquisa → descobrir → normalizar → deduplicar → investigar/cache → detectar sinais/hipóteses → persistir → formatar. Esse caminho foi exercitado com fixtures, não com um novo provedor de produção.
7. `SkillResult.to_dict()` segue pela fila `command_result`; `ResultTerminal.render_skill()` mostra mensagem/estado. Erros usam `TASK_ERROR`. Cancelamento é cooperativo entre etapas; uma chamada HTTP corrente ainda pode aguardar seu timeout.

### Pesquisa legada e qualidade dos dados

`/research`, aliases legados e pedidos naturais como “procure clínicas em Campinas” continuam usando Tavily. Não foram redirecionados à nova skill durante esta auditoria, para preservar comportamento existente. A interface e a ajuda agora explicam que essa rota usa créditos.

`WebSource` usa busca Tavily, robots.txt e páginas públicas. Extrai identidade de JSON-LD ou `og:site_name` confirmado no texto; diretórios e redes sociais são páginas de descoberta, não automaticamente empresas. Páginas não identificadas ficam pendentes, com URL, trecho e motivo. Contatos só aparecem quando publicados nos campos extraídos. Segmento, localização e outros campos podem permanecer desconhecidos; ausência não é preenchida artificialmente. A correspondência integral ao nicho/região não é garantida.

Deduplicação usa domínio/telefone e, para comparação por nome/endereço, cidade conhecida. Relatórios distinguem observações, sinais interpretados e hipóteses. A pontuação atual em `analysis/scoring.py` NÃO é a matriz nova da especificação. Existência em um site não comprova atividade comercial recente nem intenção de comprar software.

Falhas de fonte são capturadas; pesquisas podem terminar `failed`/`partial` e preservam registros. Resposta vazia válida não cria empresas. Algumas falhas individuais de páginas aparecem como pendências, não como erro global. O cache preserva dados anteriores em falha de atualização. URLs aparecem como texto no terminal; não há implementação de clique nos links.

## 3. Integração `/ai` / LAYLA

`/ai [texto]` retorna ação `open_ai` e rascunho. No desktop abre a janela e tenta conectar; NÃO envia automaticamente o rascunho. O usuário clica Enviar. Em CLI/Telegram, a resposta orienta usar o desktop, sem fingir uma resposta da LAYLA. `/ollama` é outro comando, de interpretação local opcional de evidências.

O bridge aceita somente localhost/127.0.0.1/::1, sem credenciais na URL ou caminhos adicionais. Obtém CSRF em GET `/`, valida acesso em GET `/api/configuracoes`, envia POST `/enviar` e inicia nova sessão em POST `/novo_chat`. Cookie/CSRF ficam no backend. São tratados autenticação, STANDBY, limite, timeout, JSON/resposta inválida e fechamento. Não executa ações retornadas pela LAYLA.

Verificações: transporte HTTP real contra servidor local sintético; terminal Tk real com bridge simulado. Sondagem adicional de conexão SOMENTE leitura à LAYLA configurada retornou `disconnected`. Nenhuma mensagem foi enviada à LAYLA real. Autenticação e resposta ponta a ponta da instalação real permanecem não verificadas.

## 4. Achados por gravidade

| Gravidade | Evidência e impacto | Tratamento |
|---|---|---|
| Alta | `/forget Empresa` → `/ai` ou `/ollama` → `sim` ainda apagava a empresa. Confirmação antiga sobrevivia ao novo comando. Duas regressões reproduziram a exclusão. | Corrigido: comandos explícitos dessas rotas encerram a pergunta/confirmação anterior. |
| Alta | Logger filtrava apenas mensagem; exceções eram formatadas depois. Uma chave Tavily sintética isolada e token sintético no traceback foram gravados sem máscara. | Corrigido: máscara nos padrões de credenciais e na saída final do formatter, incluindo traceback. Não é alegação de vazamento real encontrado. |
| Média | Duas empresas homônimas com domínios diferentes e cidades desconhecidas eram consideradas a mesma empresa, pois vazio era igual a vazio. | Corrigido: comparação por nome/endereço exige cidade conhecida; domínio/telefone continuam válidos. Não desfaz automaticamente fusões antigas. |
| Média, limitação aberta | `/search` não possui fonte gratuita de produção; especificação de prospecção está parcial. | Mantido bloqueio explícito. Implementar provedor/regras seria fase de implementação, fora desta auditoria. |
| Baixa | Ajuda e confirmação de conexão sugeriam que Tavily habilitava `/search`; `/ai` não esclarecia o rascunho. | Corrigidas as mensagens, sem mudança visual/posicional. |

Não foram encontradas chamadas de execução de shell/eval/exec no código de aplicação inspecionado. O módulo `core/dashboard.py` ainda é referenciado pelo modo opcional de snapshots do worker; não foi removido por parecer antigo. Duas entradas desktop compartilham a implementação, não constituem duas UIs independentes. Nenhum componente foi removido por preferência de arquitetura.

## 5. Segurança e limites verificados

- `.env` ignorado pelo Git; somente `.env.example` versionado entre esses arquivos. Configuração de chaves e cookie usa campos `repr=False`. Escrita de configuração usa arquivo temporário e substituição atômica.
- Comparação dos valores secretos atualmente configurados contra arquivos textuais versionados e logs locais atuais: nenhum encontro. Só caminhos/números de linha seriam exibidos; nenhum valor real foi impresso. Isso não audita todo o histórico Git nem detecta segredos desconhecidos.
- Transporte público valida protocolos, portas e ausência de credenciais; resolve endereços globais e fixa IP para conexão, bloqueando destinos privados. TLS usa validação; respostas e descompressão são limitadas; redirecionamentos são revalidados pelo coletor.
- Página externa é dado: HTML/JSON-LD é analisado, scripts não são executados. robots.txt é consultado, há intervalo e limites de redirecionamento/coleta. Isso não certifica conformidade com termos de todos os sites possíveis.
- HTTP 429 usa espera local fixa de 60 segundos; não interpreta `Retry-After`. Recomenda-se ampliar esse tratamento numa próxima correção testada. Timeouts são por operação de socket, não garantia absoluta de duração total para todos os comandos legados.
- A máscara de logs cobre padrões conhecidos, não qualquer segredo arbitrário. `.env`, SQLite e backups locais não são criptografados pelo aplicativo; dependem das permissões da conta Windows.
- Não houve varredura CVE online nem resolução/lock reprodutível de dependências. Não se afirma ausência de vulnerabilidades conhecidas. Nenhuma dependência nova foi instalada.

## 6. Arquivos alterados

| Arquivo | Motivo |
|---|---|
| `core/agent.py` | Invalidar confirmação anterior ao despachar `/ai`, outra skill registrada ou `/ollama`. |
| `utils/deduplication.py` | Não usar localização desconhecida como prova de identidade. |
| `utils/logger.py` | Mascarar mensagens/tracebacks e fechar handlers substituídos. |
| `core/reports.py` | Ajuda fiel às rotas de pesquisa e ao rascunho de IA. |
| `core/worker.py` | Mensagem de conexão Tavily esclarece alcance da configuração. |
| `ui/terminal.py` | Texto inicial esclarece custo/rotas; sem alterar layout. |
| `tests/test_audit_phase1.py` | Quatro regressões com dados exclusivamente sintéticos. |
| `tests/native_audit_check.py` | Teste Tk/worker focado em `/search` e `/ai`, banco em memória e sem rede externa. |
| `AUDITORIA_FASE1.md` | Este diagnóstico e limites da verificação. |

## 7. Testes executados

- Baseline completo: **188 passed** (31,80 s).
- Novas regressões antes da correção: **4 failed**, reproduzindo os três defeitos.
- Suíte completa após correção: **192 passed** (23,05 s). Inclui parser, skill, pipeline, persistência, deduplicação, falhas, cancelamento e transporte LAYLA em servidor HTTP local sintético. Uma execução intermediária detectou erro de indentação na edição de mensagem; corrigido antes da suíte final.
- `python tests/native_audit_check.py`: **PASS**. Tk e worker reais; busca duplicada recusada, `unconfigured` mostrado, zero chamadas ao transporte externo; `/ai` preserva rascunho, envia uma vez, mostra resposta simulada e reinicia a sessão sem alterar resultado da pesquisa.
- Roteiro completo `python tests/native_desktop_check.py --screenshots`: cenário `run(False)` **PASS** (poses, arraste/pouso, menus, configurações, métricas reais e encerramento); cenário `run(True)` **FAIL** em `tests/native_desktop_check.py:258`, `Completion stole focus`. A comparação usa o foreground global do Windows; não estabelece sozinha qual janela ganhou foco ou se houve interferência externa. Não foi alterada a UI nem relaxada a asserção sem causa comprovada. Resultado global do roteiro: **não aprovado**. Requer reprodução isolada.
- Sondagem LAYLA real de leitura: **disconnected**, sem envio de mensagem.
- Nenhuma busca autenticada Tavily, consumo de créditos, pesquisa comercial real ou teste de Ollama real foi realizado nesta fase.
- `git diff --check`: sem erros de whitespace.

## 8. Recomendações para a próxima fase

1. Decidir e implementar um provedor gratuito autorizado com testes reais controlados; então implementar/verificar a matriz de pontuação e o formato de leads. Não declarar `/search` operacional apenas pelo Markdown ou pelos testes com fixtures.
2. Validar a LAYLA instalada com sessão autorizada e contrato real antes de prometer funcionamento ponta a ponta.
3. Melhorar limites por fonte, `Retry-After`, preservação de falhas parciais e confirmação explícita de atividade/localidade dos negócios. Revisar manualmente registros potencialmente mesclados antes desta correção.
4. Reproduzir isoladamente a falha de foco no cenário nativo mock, identificando a janela que recebeu foco antes de mudar animações/notificações.
5. Definir versões suportadas/lock e varredura de dependências; documentar retenção e proteção dos dados locais. Reaproveitar SQLite já existente.

Conclusão: os defeitos reproduzidos de confirmação, deduplicação e logs foram tratados com alterações pequenas. A base tem pipeline e persistência reais, mas a Search Skill gratuita continua sem provedor de produção e a LAYLA real não foi validada como disponível. Essas limitações são explícitas, sem resultados fabricados.
