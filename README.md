# SAZABI — inteligência comercial local

Mascote de desktop que pesquisa páginas públicas pela **Tavily**, identifica empresas a partir dos próprios sites e organiza evidências e possíveis oportunidades em SQLite. Ao iniciar, aparece somente o personagem 2D da arte original do usuário. Não abre dashboard, navegador, servidor ou porta web.

**O uso normal não carrega empresas fictícias.** A base começa vazia. Dados sintéticos existem apenas em `tests/`, para testes isolados; o antigo comando `--mock` foi removido.

## Abrir e configurar

O mascote requer **Windows e Python 3.9+ com Tcl/Tk**. Usa GDI+ e regiões nativas do Windows. O monitor do computador usa `psutil`; CLI e backend continuam independentes da camada visual.

```powershell
git clone https://github.com/Fcanudos16/SAZABI.git
cd SAZABI
python -m pip install -r requirements.txt
python main.py
```

No Windows, abra `iniciar_sazabi.cmd` para iniciar com `pythonw`, sem manter um console aberto. Se houver um ambiente `.venv`, o iniciador usa esse Python. `iniciar_sazabi.pyw` também pode ser aberto diretamente quando arquivos `.pyw` estão associados ao Python.

1. Clique com o botão direito no **mascote → Configuração · Tavily / Ollama**.
2. Cole sua chave obtida no [painel da Tavily](https://app.tavily.com/).
3. Clique em **Salvar e conectar**. O SAZABI valida a chave no endpoint de uso da conta, salva no `.env` local e habilita a pesquisa sem reiniciar.
4. Clique no mascote para abrir o terminal e envie, por exemplo, `procure clínicas em Campinas`.

### Usar o mascote

- **Arraste** o personagem para movê-lo. Um arraste não abre o terminal.
- **Clique** para abrir ou fechar o terminal preto e verde, próximo ao personagem (até 620 × 440 px).
- **Escape, × ou clique fora** fecham apenas o terminal. A pesquisa continua em segundo plano.
- **Clique direito** dá acesso a nova pesquisa, configuração, Monitor do sistema, Sempre no topo e Encerrar SAZABI.
- Ao terminar, a pose muda e um pequeno aviso aparece por 5,5 segundos. Os resultados não são abertos automaticamente e o foco de outro aplicativo é preservado.
- A posição e as preferências do mascote ficam em `data/companion.json`, junto à pasta do banco configurado.

As seis poses vêm da mesma prancha JPEG, sem recoloração, redesenho ou geração por IA. O arquivo original permanece intacto em `assets/sazabi/original.jpg`, verificado por SHA-256. O mapeamento central está em `assets/sazabi/states.json`. O repouso usa a pose superior central; arrastar inicia pulo e soltar inicia pouso, com escala uniforme mínima de 98%. A pose inferior direita aparece apenas sobre a opção Encerrar. Durante o sono, o primeiro clique apenas acorda; comandos aguardam o despertar. Consulte [DESIGN.md](DESIGN.md).

### Monitor do sistema

**Clique direito no mascote → Monitor do sistema** abre uma janela nativa preta e verde com CPU, frequência disponível, RAM, disco da unidade atual, tempo ligado, sistema operacional, nome do computador, processador, arquitetura e núcleos. Integra os coletores do projeto System monitor fornecido pelo usuário.

As leituras são reais e atualizadas a cada segundo, sem API ou envio de informações. Fechar ou minimizar pausa a coleta; reabrir reutiliza a mesma janela e o mesmo coletor. A primeira porcentagem de CPU aparece após formar uma amostra de aproximadamente um segundo. Falhas são indicadas como indisponíveis; não são substituídas por números fictícios. Sem `psutil`, o mascote continua funcionando e o monitor mostra a instrução de instalação.

Sem chave, a janela, o histórico, a ajuda e os dados já salvos continuam disponíveis. Pesquisas novas mostram a configuração necessária. Nenhum resultado de demonstração é usado como substituto.

A validação da chave não executa pesquisa. Cada busca usa Tavily Search com `search_depth=basic` e `auto_parameters=false`. Limites, saldo e cobrança são os da sua conta Tavily; consulte o painel do provedor.

Alternativamente, copie `.env.example` para `.env` e preencha `SEARCH_API_KEY`. Variáveis do ambiente têm prioridade na inicialização; salvar pela janela atualiza também a configuração do processo atual. Se você definiu uma chave global no Windows, mantenha-a consistente com o `.env` nas próximas execuções.

## O que a pesquisa entrega

- Empresas com identidade publicada em JSON-LD ou metadados do próprio site, acompanhadas de URL e observações. Identidade publicada não equivale a validação cadastral independente.
- Páginas retornadas pela Tavily que não puderam ser identificadas: título, URL, trecho do provedor e motivo da limitação. São persistidas em `/results` sem virar empresas ou oportunidades fictícias.
- Sinais e hipóteses baseados em trechos consultados. Campos sem informação ficam como **Não identificado**. Cidade, porte e segmento não são preenchidos a partir do pedido.
- Histórico com situação da execução, inclusive falhas de API, e relatórios com contagens reais do banco.

O score indica prioridade de investigação, não probabilidade de venda. Hipóteses não comprovam que uma empresa precisa de software. O aplicativo não envia mensagens às empresas.

## Comandos

| Ação | Exemplo |
|---|---|
| Pesquisar | `/search clínicas em Campinas` |
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
| `AI_PROVIDER` / `OLLAMA_MODEL` | `none` por padrão; `ollama` habilita `/ollama Nome` |

`services.yaml` define os serviços oferecidos pela sua software house. IA não é necessária para a pesquisa e a análise por regras. Telegram e Ollama são opcionais; veja [OPERACAO.md](OPERACAO.md).

### Interpretação com Ollama local

Instale e abra o [Ollama](https://ollama.com/download), com um modelo de conversação baixado para seu computador. Clique direito no mascote → **Configuração**, e na seção Ollama clique em **Atualizar**, selecione um modelo e clique em **Ativar**. A escolha é salva no `.env` e passa a valer sem reiniciar. **Desativar** mantém a pesquisa e os relatórios por regras disponíveis.

Depois de investigar uma empresa, envie `/ollama Nome da empresa`, ou `/ollama` para a empresa selecionada anteriormente. O modelo recebe até oito trechos com URL e data, e produz uma interpretação separada em fatos, hipóteses e limitações. A resposta não é salva como evidência e não altera cadastro, score ou oportunidades. Não há acesso a ferramentas ou envio automático de contatos.

A conexão é fixa em `127.0.0.1:11434`. Modelos de nuvem são recusados; não exige chave de API para a IA local. Se o serviço não estiver disponível, a configuração orienta a abrir o Ollama ou executar `ollama serve`. A geração aguarda até 120 segundos por operação de rede; o primeiro carregamento depende do hardware e do modelo.

Diagnóstico sem baixar modelos: `python tests/ollama_local_check.py`. A validação da configuração verifica a presença e o tipo do modelo; a primeira execução de `/ollama` verifica a geração efetiva.

## Testes e limites

```powershell
python -m pip install -r requirements.txt
python -m pytest -q
python tests/native_desktop_check.py
python tests/public_network_check.py
```

Os testes de integração usam respostas controladas e bases temporárias. O teste de rede separado consulta uma página pública real e verifica que a Tavily recusa acesso sem autenticação. Ele **não valida uma busca autenticada**. Para essa verificação, conecte sua chave na janela e realize uma pesquisa.

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

- `/search empresas de tecnologia em São Paulo`: executa a Search Skill no backend, usando os serviços reais já existentes. Resultados continuam no terminal principal e no SQLite.
- **Nova pesquisa**: executa uma consulta `/search ...` já preparada uma única vez. Sem consulta, prepara `/search ` para digitação.
- **Cancelar**: disponível durante a Search Skill. Interrompe entre etapas/requisições; a chamada HTTP atual ainda pode aguardar seu timeout. Dados já gravados são preservados e a execução fica marcada como cancelada.
- `/ai`: abre exclusivamente o **SAZABI AI TERMINAL**. `/ai texto` preenche um rascunho, sem enviá-lo automaticamente.
- `/ollama Nome da empresa`: mantém a interpretação local opcional anterior. O antigo `/ai` do Ollama foi renomeado para liberar `/ai` para a LAYLA.

### Configurar e estender a Search Skill

`core/commands/parser.py` separa comando e argumentos; `registry.py` contém metadados públicos; `router.py` encaminha para Skills ou ações da interface. A pesquisa não está no parser.

`skills/search/skill.py` implementa `execute(query, context)` e adapta os serviços existentes do agente. `skills/search/config.json` controla `enabled` e `timeout_seconds` (5–600 segundos, limite cooperativo entre etapas/requisições). Sem fontes/chave ou configuração válida, a resposta é `unconfigured`, sem resultados inventados. Não foram adicionados filtros ou mecanismos fictícios.

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
