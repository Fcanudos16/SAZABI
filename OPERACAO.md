# Operação do SAZABI

## Execução

Python 3.9+. Runtime sem dependências externas. Copie `.env.example` para `.env`.

```bash
python main.py --mock
python main.py --mock -c "procure clínicas em Campinas"
python main.py --mock --backup
```

Pesquisa real: configure `SEARCH_API_KEY` de uma conta Brave Search e execute sem `--mock`.
Telegram: configure `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USER_IDS=123456789,987654321` e execute `python main.py --telegram`.
Somente chats privados de IDs autorizados chegam ao agente. Outros usuários, grupos e bots são ignorados antes do acesso ao banco.
O bot devolve relatórios consolidados. A base comercial é compartilhada entre autorizados; confirmações e contexto da última empresa são separados por usuário.
Mensagens antigas na fila são descartadas na inicialização. O processo precisa estar aberto para receber comandos; não monitora empresas periodicamente.

## IA local opcional

Use `AI_PROVIDER=ollama`, `OLLAMA_MODEL` com um modelo já instalado e Ollama disponível em `127.0.0.1:11434`.
`/ai Nome da empresa` interpreta no máximo oito trechos de evidência, sem executar ações ou alterar dados, status e score.
A resposta é identificada como interpretação não validada. Falha da IA não impede relatórios determinísticos.
IA em nuvem não foi implementada. Em mock, IA e Telegram ficam bloqueados.

## Evidências e prioridade

Hipóteses exigem sinais com texto, fonte e URL. WhatsApp não comprova trabalho manual e site não identificado não comprova ausência de site.
O score de 0 a 100 representa prioridade de investigação, nunca probabilidade de venda. Repetir o mesmo tipo de sinal não soma pontos.
Serviços vêm de `services.yaml`. A equipe decide se entra em contato; o sistema não envia mensagens para empresas.

## Pesquisa real: limites explícitos

- Brave descobre até `SEARCH_LIMIT` candidatos por consulta (padrão 5, máximo 20).
- Cadastros exigem JSON-LD de organização/empresa com nome e URL no domínio consultado. Títulos e snippets não viram cadastros.
- Localização só é preenchida com informação da fonte. Segmento, porte e aderência aos filtros exigem revisão; não são inventados a partir do pedido.
- A investigação lê a página inicial. Não percorre automaticamente notícias, redes sociais e páginas internas.
- HTTPS público com IP validado e fixado na conexão, sem redirects, login, cookies, CAPTCHA ou contorno de bloqueios.
- `robots.txt` precisa estar disponível e permitir acesso. Ausência, erro ou redirecionamento impede a coleta. Respeita `Crawl-delay`, com mínimo de dois segundos por domínio nas páginas.
- HTTP 403/429 suspende o domínio na sessão. GET tem até três tentativas com backoff; POST não é repetido automaticamente.
- Timeout e limite de resposta. Sites dinâmicos ou sem dados estruturados podem não ser identificados.
- Robots não substitui termos de uso; selecione fontes cuja coleta seja permitida.

## Banco, backups e recuperação

SQLite usa WAL, chaves estrangeiras e espera de cinco segundos por locks. Backup íntegro em `data/backups/` ao iniciar em modo real.
Backup manual: `python main.py --backup`. Não há exclusão automática de backups.
Para recuperar: pare o processo e use `--db caminho/do/backup.db`; preserve uma cópia do backup antes de continuar a escrever nele.
Na instalação local original, `sazabi_before_v1.zip` preserva o código anterior às alterações; esse arquivo não é distribuído no repositório. `.env`, bancos, logs e backups ficam fora do Git.
O mock padrão usa `data/sazabi_mock.db`. Não aponte `--db` ou `DATABASE_PATH` para dados reais durante testes fictícios.

## Testes

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

Opcionalmente, instale dependências de teste em `.test-deps` com `python -m pip install --target .test-deps -r requirements.txt` e execute `python run_tests.py`.
Verificação offline inclui fluxo mock, persistência, hipóteses, score, autorização, robots, transporte e leitura de backup íntegro.
Brave, Telegram e Ollama ainda requerem teste real com credenciais/serviço local. O código não foi declarado validado em produção.

Contratos consultados: [Brave](https://brave.com/search/api/), [Telegram](https://core.telegram.org/bots/api), [Ollama](https://docs.ollama.com/api/chat).
