# SAZABI — inteligência comercial local

Mascote de desktop com pesquisa pela **Tavily**, autorizada também para `/search` com uso de créditos, que identifica empresas a partir dos próprios sites e organiza evidências e possíveis oportunidades em SQLite. Ao iniciar, aparece somente o personagem 2D da arte original do usuário. Não abre dashboard, navegador, servidor ou porta web.

**O uso normal não carrega empresas fictícias.** A base começa vazia. Dados sintéticos existem apenas em `tests/`, para testes isolados; o antigo comando `--mock` foi removido.

O desktop consolidado, recuperação de falhas, controles e testes da fase final estão em [FASE4_DESKTOP.md](FASE4_DESKTOP.md). A política do `/search` gratuito permanece explícita: não há adaptador de produção autorizado instalado; `/research` usa Tavily com créditos.

## Abrir e configurar

O mascote requer **Windows e Python 3.9+ com Tcl/Tk**. Usa GDI+ e regiões nativas do Windows. O monitor do computador usa `psutil`; CLI e backend continuam independentes da camada visual.

```powershell
git clone https://github.com/Fcanudos16/SAZABI.git
cd SAZABI
python -m pip install -r requirements.txt
python main.py
```

No Windows, abra `iniciar_sazabi.cmd` para iniciar com `pythonw`, sem manter um console aberto. Se houver um ambiente `.venv`, o iniciador usa esse Python. `iniciar_sazabi.pyw` também pode ser aberto diretamente quando arquivos `.pyw` estão associados ao Python.

1. Copie `.env.example` para `.env` **somente se ainda não existir**.
2. Edite `SEARCH_API_KEY` no `.env` privado e reinicie o SAZABI. Não há campo de credenciais na interface.
3. Clique no mascote e envie `/research clínicas em Campinas`. `/search` também usa Tavily e consome créditos da conta.
4. Para Groq, configure `AI_PROVIDER=groq`, `GROQ_API_KEY` e `GROQ_MODEL` no `.env`. A janela de configuração não é disponibilizada na interface.

O tema e o comportamento das janelas estão documentados em [ATUALIZACAO_DESKTOP.md](ATUALIZACAO_DESKTOP.md).

### Usar o mascote

- **Arraste** o personagem para movê-lo. Um arraste não abre o terminal.
- **Clique** para abrir ou fechar o terminal preto e verde, próximo ao personagem (até 620 × 440 px).
- **Duplo clique** mantém o terminal aberto. **Último** recupera a última tentativa de pesquisa; cada comando tem uma saída atual separada.
- **Escape, × ou clique fora** fecham apenas o terminal. A pesquisa continua em segundo plano.
- **Clique direito** dá acesso a nova pesquisa, Monitor do sistema, Sempre no topo e Encerrar SAZABI.
- Ao terminar, a pose muda e um pequeno aviso aparece por 5,5 segundos. Os resultados não são abertos automaticamente e o foco de outro aplicativo é preservado.
- A posição e as preferências do mascote ficam em `data/companion.json`, junto à pasta do banco configurado.

As seis poses vêm da mesma prancha JPEG, sem recoloração, redesenho ou geração por IA. O arquivo original permanece intacto em `assets/sazabi/original.jpg`, verificado por SHA-256. O mapeamento central está em `assets/sazabi/states.json`. O repouso usa a pose superior central; arrastar inicia pulo e soltar inicia pouso, com escala uniforme mínima de 98%. A pose inferior direita aparece apenas sobre a opção Encerrar. Durante o sono, o primeiro clique apenas acorda; comandos aguardam o despertar. Consulte [DESIGN.md](DESIGN.md).

### Monitor do sistema

**Clique direito no mascote → Monitor do sistema** abre uma janela nativa preta e verde com CPU, frequência disponível, RAM, disco da unidade atual, tempo ligado, sistema operacional, nome do computador, processador, arquitetura e núcleos. Integra os coletores do projeto System monitor fornecido pelo usuário.

As leituras são reais e atualizadas a cada segundo, sem API ou envio de informações. Fechar ou minimizar pausa a coleta; reabrir reutiliza a mesma janela e o mesmo coletor. A primeira porcentagem de CPU aparece após formar uma amostra de aproximadamente um segundo. Falhas são indicadas como indisponíveis; não são substituídas por números fictícios. Sem `psutil`, o mascote continua funcionando e o monitor mostra a instrução de instalação.

Sem chave, a janela, o histórico, a ajuda e os dados já salvos continuam disponíveis. Pesquisas novas mostram a configuração necessária. Nenhum resultado de demonstração é usado como substituto.

A validação da chave não executa pesquisa. Cada busca usa Tavily Search com `search_depth=basic` e `auto_parameters=false`. Limites, saldo e cobrança são os da sua conta Tavily; consulte o painel do provedor.

`core/config.py` centraliza a leitura do `.env` e das variáveis de ambiente (estas têm prioridade). Após editar credenciais, reinicie. Nunca versione o `.env`.

## O que a pesquisa entrega

- Empresas com identidade publicada em JSON-LD ou metadados do próprio site, acompanhadas de URL e observações. Identidade publicada não equivale a validação cadastral independente.
- Páginas retornadas pela Tavily que não puderam ser identificadas: título, URL, trecho do provedor e motivo da limitação. São persistidas em `/results` sem virar empresas ou oportunidades fictícias.
- Sinais e hipóteses baseados em trechos consultados. Campos sem informação ficam como **Não identificado**. Cidade, porte e segmento não são preenchidos a partir do pedido.
- Histórico com situação da execução, inclusive falhas de API, e relatórios com contagens reais do banco.

O score indica prioridade de investigação, não probabilidade de venda. Hipóteses não comprovam que uma empresa precisa de software. O aplicativo não envia mensagens às empresas.

## Comandos

### Qualificação comercial (fase 3)

Sem API: `/profile` configura capacidades reais; `/qualify ID` avalia fontes salvas e explica a pontuação; `/evaluations ID` conserva o histórico. `/draft ID email|message|call` prepara uma abordagem para revisão e `/draft-save` guarda a prévia, sem envio. `/qualify-ai ID` prepara um resumo opcional para revisar antes de enviar à LAYLA. Consulte [FASE3_INTELIGENCIA.md](FASE3_INTELIGENCIA.md) para pesos, categorias, configuração e limites.

| Ação | Exemplo |
|---|---|
| Search Skill (Tavily; usa créditos) | `/search clínicas em Campinas` |
| Pesquisa legada Tavily (consome créditos da conta) | `/research clínicas em Campinas` |
| Investigar empresa | `/investigate Nome da empresa` |
| Investigar site | `/investigate https://site-oficial.example` — substitua pelo site real |
| Atualizar investigação | `/investigate Nome da empresa --refresh` |
| Ver dados armazenados | `/company Nome da empresa` |
| Rever resultados | `/results`, `/results hoje` |
| Ver hipóteses qualificadas | `/interesting` |
| Histórico | `/history` |
| Guardar ou ignorar | `/save Nome`, `/ignore Nome` |
| Apagar com confirmação | `/forget Nome` |
| Região padrão | `/set region Campinas` |
| Ajuda / situação | `/help`, `/status` |

Também aceita pedidos como `procure restaurantes em São Paulo`. Se faltar cidade e não houver região padrão, pergunta uma vez.

```powershell
python main.py --cli
python main.py -c "/search clínicas em Campinas"
python main.py --backup
```

`main.py` encontra `.env`, serviços, banco e logs junto ao projeto mesmo quando iniciado de outra pasta. Caminhos personalizados são aceitos por `--env`, `--services` e `--db`.

## Configuração opcional

| Variável | Uso / padrão |
|---|---|
| `SEARCH_API_KEY` | Chave Tavily, exigida para pesquisa online |
| `SEARCH_LIMIT` | Páginas por consulta: 5, máximo 20 |
| `DATABASE_PATH` | `data/sazabi.db` |
| `CACHE_TTL_HOURS` | Cache de investigação: 24 horas |
| `DEFAULT_REGION` | Cidade padrão |
| `LOG_LEVEL` / `LOG_FILE` | `INFO` / `logs/sazabi.log` |
| `TELEGRAM_BOT_TOKEN` | Token para o modo opcional `--telegram` |
| `TELEGRAM_ALLOWED_USER_IDS` | IDs autorizados para o Telegram |
| `AI_PROVIDER` / `GROQ_MODEL` / `GROQ_API_KEY` | `none` por padrão; `groq` habilita `/groq Nome` |

`services.yaml` define os serviços oferecidos pela sua software house. IA não é necessária para a pesquisa e a análise por regras. Telegram e Groq são opcionais; veja [OPERACAO.md](OPERACAO.md).

### Interpretação com Groq

Configure no arquivo privado `.env` e reinicie:

```dotenv
AI_PROVIDER=groq
GROQ_API_KEY=sua_chave_groq
GROQ_MODEL=llama-3.3-70b-versatile
```

Use `/groq Nome da empresa` ou `/groq` para a empresa selecionada. `/ai` continua abrindo a LAYLA.

A interpretação envia à API HTTPS do Groq até oito trechos de 600 caracteres com URL e data. Depende de internet, credencial e limites/custos da conta. A resposta não altera evidências, cadastro, score ou histórico. Respostas incompletas, recusadas ou inválidas são rejeitadas. `AI_PROVIDER=none` desativa a interpretação.

Diagnóstico opcional de conexão: `python tests/groq_connection_check.py`. Referência: [API Groq](https://console.groq.com/docs/api-reference).

## Testes e limites

```powershell
python -m pip install -r requirements.txt
python -m pytest -q
python tests/native_desktop_check.py
python tests/public_network_check.py
```

Os testes de integração usam respostas controladas e bases temporárias. O teste de rede separado consulta uma página pública real e verifica que a Tavily recusa acesso sem autenticação. Ele **não valida uma busca autenticada**. Para essa verificação, configure sua chave no `.env` e reinicie e realize uma pesquisa.

Sites podem bloquear coleta, exigir JavaScript ou não publicar identidade suficiente. Redirecionamentos são limitados e cada destino passa pela validação de endereço público; `robots.txt` é respeitado. Não há contorno de CAPTCHA/login. Detalhes em [OPERACAO.md](OPERACAO.md).

## Organização

- `main.py`, `desktop.py`: execução; `ui/companion.py`: mascote; `ui/terminal.py`: terminal secundário.
- `ui/sprites.py`, `ui/native.py`: leitura da arte original, regiões de janela e posicionamento.
- `ui/preferences.py`: configuração opcional; `core/worker.py`: execução em segundo plano e fila de eventos.
- `core/`: configuração, conexão Tavily, comandos, relatórios e memória.
- `research/`: busca, coleta pública, normalização e investigação.
- `analysis/`: sinais, hipóteses, score e interpretação opcional.
- `database/`: SQLite e repositórios.
- `tests/`: testes e dados sintéticos isolados.

Credenciais, banco, logs e backups ficam fora do Git. Para distribuir o projeto, use o repositório; não copie sua pasta `.env` ou `data/` para uma instalação nova.

O mascote usa animações lentas e discretas permanentemente; não há opção de reduzir movimento. Preferências antigas dessa opção são ignoradas. O monitor usa apenas métricas locais, sem chave de API. Se uma leitura falhar na apresentação, a janela informa o erro e tenta novamente automaticamente.


### Recuperação de falhas

- Investigações sem fontes ou com falha em uma fonte preservam o último conjunto de evidências e a data anterior. Uma coleta incompleta não renova o cache nem apaga o histórico; o relatório informa a limitação.
- Evidências, sinais, hipóteses e data de investigação são gravados em uma transação. Uma falha de gravação desfaz esse conjunto de alterações.
- Uma exceção durante a pesquisa finaliza o registro como falha, preservando resultados parciais já gravados.
- Após queda de conexão, uma nova solicitação pode tentar novamente sem reiniciar o aplicativo. Respostas HTTP 429 aplicam uma pausa de 60 segundos.
- Arquivos `.env` com BOM do Windows são aceitos. TTL inválido volta a 24 horas; lista Telegram inválida desabilita o acesso Telegram sem impedir o desktop.


## Comandos Slash e Skills

A caixa do SAZABI mantém 620 × 440 pixels (ou o limite da área útil da tela). Digitar `/` abre sugestões locais sobre a área de resultados; setas selecionam, Tab/Enter completam e Escape fecha as sugestões.

- `/search empresas de tecnologia em São Paulo`: aciona a Search Skill com Tavily autorizado; exige `SEARCH_API_KEY` e usa créditos.
- **Nova pesquisa**: executa uma consulta `/search ...` já preparada uma única vez. Sem consulta, prepara `/search ` para digitação.
- **Cancelar**: disponível na Search Skill, pesquisa legada e investigação. Interrompe entre etapas/requisições; a chamada HTTP atual ainda pode aguardar seu timeout. Dados já gravados são preservados e a execução fica marcada como cancelada.
- `/ai`: abre exclusivamente o **SAZABI AI TERMINAL**. `/ai texto` preenche um rascunho, sem enviá-lo automaticamente.
- `/groq Nome da empresa`: interpreta evidências com a API Groq.

### Configurar e estender a Search Skill

`core/commands/parser.py` separa comando e argumentos; `registry.py` contém metadados públicos; `router.py` encaminha para Skills ou ações da interface. A pesquisa não está no parser.

`skills/search/skill.py` implementa `execute(query, context)` e adapta os serviços existentes do agente. `skills/search/config.json` controla `enabled` e `timeout_seconds` (5–600 segundos, limite cooperativo entre etapas/requisições). Sem fonte autorizada ou configuração válida, a resposta é `unconfigured`, sem resultados inventados. Tavily é permitido com `allow_tavily=true` e chave válida. Não foram adicionados filtros ou mecanismos fictícios.

Cada Skill fornece `name`, `description`, `version`, `enabled`, `commands` e `execute`. Registre outra implementação com `agent.skills.register(skill)` e seu comando com `agent.command_router.registry.register(CommandDefinition(...))`. Para substituir a implementação de pesquisa, use `register(skill, replace=True)`; o parser e a UI permanecem iguais. Inclua novos comandos no registro padrão para aparecerem no autocomplete.

Resultados usam `SkillResult(success, skill, status, message, data, error)`, convertido em dicionário no worker. `data.companies` contém identificadores, nomes, segmento, localização e site reais; não atribui potencial inventado. A UI pode renderizar resultados estruturados mesmo sem relatório textual. Estados de fila, execução e processamento vêm de eventos reais. A consulta sem região continua pedindo a cidade.

### LAYLA Mark 5 local

A integração fica em `integrations/layla/`. Abra a LAYLA separadamente e configure no `.env` privado do SAZABI:

```dotenv
LAYLA_URL=http://127.0.0.1:5000
LAYLA_SESSION_COOKIE=
```

O adaptador usa o contrato existente da Mark 5: página inicial com token CSRF, leitura protegida de `/api/configuracoes`, envio em `/enviar` (`texto` → `resposta`) e nova sessão em `/novo_chat`. Cookies/CSRF permanecem no backend em memória; não há extração de cookies de navegadores. Apenas endereços loopback são aceitos. Instalações com HTTPS obrigatório exigem URL HTTPS e certificado confiável; não se desativa a validação TLS.

No modo local da LAYLA sem conta proprietária, uma sessão própria é criada automaticamente. Se a instalação exigir autenticação, forneça uma sessão autorizada pelo administrador em `LAYLA_SESSION_COOKIE`; ela é uma credencial sensível e não deve ser versionada ou compartilhada. Sessão expirada, STANDBY ou contrato incompatível produzem erro visível; não há bypass de autenticação. Outra versão da LAYLA requer um adaptador compatível.

O terminal mostra estado verificado da conexão, processamento, histórico da sessão, **Conectar**, **Nova sessão** e **Fechar**. Fechar esconde a janela e preserva a conversa; encerrar o SAZABI fecha a conexão. Nova sessão só limpa o histórico exibido após confirmação da LAYLA. O histórico visual é limitado e fica em memória; a LAYLA pode persistir as mensagens conforme sua própria configuração. O SAZABI envia apenas o texto digitado, nunca todo o banco ou leads automaticamente. Ações retornadas pela LAYLA não são executadas pelo SAZABI.

Validação de contrato: `tests/test_layla_bridge.py` usa um servidor HTTP isolado, com dados explicitamente de teste. Isso não comprova que uma instalação real da LAYLA está online ou que seu modelo está configurado.

## Skill SAZABI Search: Tavily autorizado

`/search` usa o pipeline existente de descoberta, investigação e persistência com Tavily. Configure `SEARCH_API_KEY` no `.env`; `skills/search/config.json` contém `allow_tavily: true`, autorizado pelo usuário. As consultas usam créditos da conta. `SEARCH_LIMIT` limita resultados; `timeout_seconds` mantém o cancelamento cooperativo. Para bloquear Tavily nesta skill, defina `allow_tavily: false`.

Sem argumentos, usa a região salva por `/set` ou `DEFAULT_REGION`. Sem região, pede a localidade. Sem fonte autorizada ou configuração válida, retorna `unconfigured`, sem inventar resultados. Fixtures são restritas ao modo de teste. Não chama LAYLA nem Groq durante a pesquisa.

A especificação está em `skills/search/SKILL.md`. Descoberta em duas passagens e rotação de nichos continuam pendentes; conectar Tavily não implementa esses recursos.

## Gestão local de leads — fase 2

Clique em **Leads** no terminal ou use `/leads`. A mesma base SQLite agora mantém estágios comerciais, observações, histórico de ações e fontes, arquivamento com confirmação e exportação selecionada para CSV/JSON. Exemplos: `/lead ID`, `/stage ID qualified`, `/note ID texto`, `/export csv ID1,ID2`.

Consulte [FASE2_LEADS.md](FASE2_LEADS.md) para comandos, estrutura, migração, backup e recuperação. A migração é automática e preserva IDs e dados existentes. `/search` usa a configuração Tavily descrita acima.


## Countdown e tempo de pesquisa

O contador da pesquisa existe somente dentro do terminal de pesquisa. Aparece quando a busca começa, conta de zero e desaparece ao terminar, falhar, exceder o limite ou confirmar o cancelamento. Não tem janela separada, controles nem acesso pelo menu. Enquanto aguarda uma região, não aparece. Fechar o terminal oculta também o contador, sem interromper a pesquisa; reabrir o terminal durante a busca mostra o tempo decorrido.

Para o timer manual: **clique direito no mascote → Countdown → SET**. Digite `cinco minutos` ou `5:00:00` para definir cinco minutos e depois `iniciar`. Também aceita `iniciar cinco minutos`, `set cinco minutos`, `um minuto e trinta segundos`, `meia hora`, `duas horas e meia` e durações numéricas como `90 segundos`.

`M:SS:CC` significa **minutos:segundos:centésimos**, portanto `5:00:00` são cinco minutos. Durações digitadas sem verbo configuram o timer, sem iniciar automaticamente. São aceitos `start`/`iniciar`, `pause`/`pausar`, `resume`/`retomar`, `reset`/`reiniciar`, `stop`/`parar`/`zerar`, `top on`, `top off`, `clear`/`limpar`, `help`/`ajuda`, `exit`/`sair`. Não é possível alterar a duração durante a contagem sem pausar ou parar antes.

O countdown manual mantém PIN, arraste, redimensionamento e alerta vermelho ao chegar a zero. Espaço inicia/pausa/retoma fora do campo de texto; Enter ou `/` abre o campo; Esc fecha o terminal do countdown ou dispensa o alerta. X e `exit` ocultam apenas o countdown manual; `stop` interrompe e zera. Encerrar o SAZABI encerra os timers. Ambos usam relógio monotônico e funcionam independentemente. Não restauram contagens após reiniciar o aplicativo.

Testes: `python tests/native_countdown_check.py` verifica a interface real usando fontes simuladas e banco em memória. `tests/test_countdown_language.py` cobre as durações e os comandos em português.
