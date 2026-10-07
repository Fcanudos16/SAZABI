# SAZABI V1 — olheiro digital da software house

Bot pessoal de inteligência comercial: pesquisa empresas em fontes públicas, investiga uma a uma,
detecta **sinais**, gera **hipóteses** de oportunidade e guarda tudo em SQLite. Não é SaaS, site nem CRM.
A equipe decide quem contatar; o SAZABI só apresenta informação, sempre com fonte.

**Estado atual:** pipeline local, pesquisa Brave, Telegram privado, score, backup e interpretação opcional via Ollama implementados.
Testes offline passam; APIs reais ainda exigem validação com credenciais. Consulte [operação e limites](OPERACAO.md).

## Instalação e execução

Requer Python 3.9+. Sem dependências de runtime (só biblioteca padrão).

No PowerShell:

```powershell
git clone https://github.com/Fcanudos16/SAZABI.git
cd SAZABI
python -m venv .venv
.\.venv\Scripts\Activate.ps1
Copy-Item .env.example .env
```

Se a ativação do ambiente estiver bloqueada, use `.\.venv\Scripts\python.exe` no lugar de `python` nos comandos abaixo.

```bash
python main.py --mock            # conversa no terminal com dados fictícios
python main.py --mock -c "procure clínicas em São Paulo"   # uma mensagem e sai
pip install -r requirements.txt  # só para os testes
python -m pytest                 # testes offline
```

Com a configuração padrão, o modo mock usa `data/sazabi_mock.db`. Não aponte `--db` ou `DATABASE_PATH` para um banco real durante testes fictícios. Logs em `logs/sazabi.log`.

### Pesquisa real e Telegram

Preencha as variáveis necessárias no `.env` e execute:

```powershell
python main.py               # terminal com pesquisa Brave, quando configurada
python main.py --telegram    # bot privado com IDs autorizados
python main.py --backup      # backup SQLite verificado
```

| Variável | Uso / padrão |
|---|---|
| `SEARCH_API_KEY` | Chave Brave Search; sem ela, pesquisa real fica desativada |
| `SEARCH_LIMIT` | Resultados por consulta: 5, máximo 20 |
| `TELEGRAM_BOT_TOKEN` | Token do bot; necessário para `--telegram` |
| `TELEGRAM_ALLOWED_USER_IDS` | IDs numéricos autorizados, separados por vírgula; obrigatório para o bot |
| `AI_PROVIDER` | `none` (padrão) ou `ollama` |
| `OLLAMA_MODEL` | Nome de um modelo instalado no Ollama local |
| `DATABASE_PATH` | `data/sazabi.db` |
| `CACHE_TTL_HOURS` | Validade da investigação em cache: 24 horas |
| `DEFAULT_REGION` | Cidade padrão opcional |
| `LOG_LEVEL` / `LOG_FILE` | `INFO` / `logs/sazabi.log` |

Ollama usa o endereço local fixo `127.0.0.1:11434`. A chave Brave não é necessária para consultar empresas já armazenadas.
Não coloque tokens em código, comandos versionados ou issues. Veja os detalhes em [OPERACAO.md](OPERACAO.md).

## Comandos (ou fale naturalmente)

| Natural | Comando |
|---|---|
| "procure pequenas clínicas em São Paulo" | `/search clínicas em Campinas` |
| "faça uma pesquisa silenciosa por oficinas em Campinas" | (só envia o resumo) |
| "investigue a Oficina Silva" | `/investigate Oficina Silva` |
| "atualize a investigação da Oficina Silva" | `/investigate Oficina Silva --refresh` |
| "o que você encontrou hoje?" | `/results [hoje\|ontem]` |
| "quais empresas parecem interessantes?" | `/interesting` |
| "o que eu pesquisei ontem?" | `/history [hoje\|ontem]` |
| "guarde / ignore essa empresa" | `/save` `/ignore` `/forget` (apagar pede confirmação) |
| — | `/company <nome>`, `/set region <cidade>`, `/status`, `/help` |
| Interpretação por IA local | `/ai <nome da empresa>` |

Se faltar a região, o SAZABI pergunta uma vez. `/set region Campinas` define uma região padrão.

## Arquitetura

```
CLI (main.py) ──► SazabiAgent (core/agent.py) ◄── Telegram (allowlist)
                      │
 router → finder → normalização → deduplicação → investigator → signal_detector → opportunity_analyzer → SQLite
```

- `core/` agente, roteador de comandos, memória, config, relatórios
- `research/` fontes (`CompanySource`), finder, investigator (com cache), `mock_source.py`
- `analysis/` sinais, hipóteses e score determinísticos; interpretação opcional via Ollama separada
- `database/` schema, modelos, repositórios · `notifications/` notifiers · `utils/` normalização, dedup, logs

Regra central: **fato** (observação + fonte + URL) → **inferência** (sinal) → **hipótese** (com nível de
evidência). Campo sem dado fica "Não identificado"; nada é inventado.

## Configuração

- `.env` (copie `.env.example`): `DATABASE_PATH`, `CACHE_TTL_HOURS`, `LOG_LEVEL`, `DEFAULT_REGION`...
- `services.yaml`: serviços da software house. Hipóteses só são geradas para o que estiver listado.

## Como estender

- **Nova fonte:** implemente `CompanySource` (`search`, `fetch_observations`, `lookup`) em `research/` e
  passe-a em `core/bootstrap.py`. Toda fonte real deve ter timeout, rate limit, retry com backoff e
  respeitar robots.txt/termos de uso.
- **Novo sinal:** adicione o tipo em `database/models.py` e uma `SignalRule` em `analysis/signal_detector.py`.
- **Nova hipótese:** adicione uma `HypothesisRule` em `analysis/opportunity_analyzer.py`.
- **Nova notificação:** implemente `Notifier.send()` em `notifications/`.

## Próximas etapas

Configure as credenciais conforme [OPERACAO.md](OPERACAO.md) e valide a pesquisa e o bot com suas contas.
IA em nuvem e monitoramento comercial 24/7 ficam fora desta versão.

## Validação e limites

A suíte tem 89 testes offline, incluindo execução do terminal em processos separados, persistência, acesso ao Telegram,
bloqueio de destinos privados, HTTP 429 e recuperação de backup. Rode `python -m pytest -q` após instalar `requirements.txt`.
Brave, Telegram e Ollama foram testados com respostas simuladas; o funcionamento real depende das credenciais e do serviço local.

A coleta exige dados estruturados públicos e permissão em `robots.txt`; sites dinâmicos, redirects e páginas sem esses dados podem ser omitidos.
Redes sociais e notícias não são investigadas automaticamente. Segmento, porte e aderência aos filtros precisam de revisão humana.
O score representa prioridade de investigação, nunca chance de venda. Nenhum contato automático com empresas é realizado.

## Estrutura

```text
main.py             Entrada do terminal e Telegram
core/               Configuração, comandos, memória e relatórios
research/           Descoberta, fontes públicas/mock e investigação
analysis/           Evidências, sinais, hipóteses, score e Ollama
database/           Modelos, schema SQLite e repositórios
notifications/      Console e Telegram
utils/              HTTP, normalização, deduplicação, logs e datas
tests/              Testes offline
services.yaml       Serviços oferecidos pela software house
.env.example        Modelo de configuração sem credenciais
OPERACAO.md         Guia de operação, segurança e recuperação
```

Dados, logs, ambientes virtuais, dependências locais de teste e backups não fazem parte do repositório.
