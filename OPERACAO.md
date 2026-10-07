# Operação do SAZABI

## Primeira execução

Execute `python main.py` ou `iniciar_sazabi.cmd`. Abra Configuração, informe sua chave Tavily e clique em Salvar e conectar. A chave é validada por `GET /usage` antes de substituir a configuração anterior. Uma falha de validação preserva a chave anterior.

A chave fica no `.env` local, não na conversa nem no banco. O arquivo é gravado por substituição atômica, preservando as outras variáveis. O campo é mascarado e limpo ao enviar. Proteja o acesso à sua pasta: o `.env` é texto local, não um cofre criptografado.

O programa abre sem chave. Configurar Tavily não exige OpenAI, Ollama ou Telegram. A chave antiga do Brave não é compatível.

## Pesquisa e evidências

Tavily retorna até `SEARCH_LIMIT` páginas por consulta (padrão 5, máximo 20), usando busca basic sem seleção automática de parâmetros. Esse limite não é teto mensal de gastos. O plano e o saldo são controlados na sua conta Tavily.

Cada página descoberta é armazenada com URL, título, trecho retornado, data, situação de identificação e motivo da limitação. Um trecho Tavily não verificado não gera sinais, hipóteses ou cadastro automaticamente.

A identificação usa JSON-LD de organização/empresa no domínio consultado ou `og:site_name` corroborado pelo texto do site. Diretórios e redes sociais conhecidos ficam como páginas pendentes. A identificação é uma declaração do site; não certifica CNPJ, atividade, porte ou aderência ao pedido.

A investigação consulta a página encontrada e até duas páginas internas de contato, apresentação ou unidades quando vinculadas. Somente páginas efetivamente lidas aparecem como evidência. Falhas nas páginas extras não invalidam as observações da página principal. Páginas renderizadas apenas por JavaScript podem não fornecer texto.

Campos ausentes ficam sem preenchimento. Hipóteses exigem sinais com fonte, texto e URL. WhatsApp não comprova trabalho manual; ausência de site identificado não comprova ausência de site. O score representa prioridade de investigação. A equipe decide sobre contato.

## Rede e falhas

- URLs públicas HTTP/HTTPS, sem credenciais embutidas e nas portas padrão. HTTP só é permitido na coleta pública sem tokens; a API usa HTTPS.
- IPs privados/reservados são bloqueados. O IP validado é fixado na conexão; HTTPS mantém a verificação TLS do hostname.
- Até quatro etapas de redirecionamento, com nova validação em cada destino. Tokens da API nunca seguem redirecionamentos.
- `robots.txt` é respeitado; 404/410 permitem coleta. Proibição, falha de rede, 403 e 5xx impedem acesso. Intervalo mínimo de dois segundos por domínio; `Crawl-delay` superior a 15 segundos adia a coleta.
- GET tem até três tentativas; POST não é repetido automaticamente. Timeout padrão de 15 segundos por operação de socket.
- Respostas comprimidas gzip/deflate são decodificadas com limite de tamanho também após descompressão. Respostas maiores que 1 MB são recusadas.
- 401 informa chave inválida; 429 informa limite de requisições; 432/433 informam limite do plano/conta. A fonte é suspensa na sessão após bloqueio. Aguarde o limite do provedor e reconecte pela configuração para tentar novamente.
- Erros de API ficam no relatório, histórico e situação da execução. Páginas bloqueadas permanecem consultáveis como descobertas pendentes.

Robots não substitui termos de uso. Não há login, cookies autenticados, quebra de CAPTCHA ou contorno de restrições.

## Interface local

Painel e conversa usam o mesmo banco. `ONLINE` significa que o agente local está pronto, não que a chave foi validada. A configuração mostra o resultado da validação. A janela continua respondendo durante a coleta; fechar aguarda a operação em andamento para encerrar o banco com segurança.

Pausa bloqueia novos comandos da janela. Redução de animações e pausa valem para a sessão atual. O aplicativo não mantém rotina de prospecção contínua.

## Banco e recuperação

SQLite usa WAL e chaves estrangeiras. Ao iniciar com banco em arquivo, é criado backup verificado em `data/backups/`. `python main.py --backup` cria outro backup. Não há exclusão automática.

Para recuperação, pare o aplicativo, preserve uma cópia do backup e execute `python main.py --db caminho/do/backup.db`. O schema é atualizado ao abrir bases anteriores, sem apagar as empresas existentes.

Dados de demonstração das versões antigas continuam apenas no antigo `data/sazabi_mock.db`, caso ele exista; esse arquivo não é aberto por padrão. Os testes atuais injetam dados sintéticos explicitamente e usam bases isoladas. Nunca aponte testes para seu banco real.

## Recursos opcionais

Terminal: `python main.py --cli`. Execução única: `python main.py -c "/status"`.

Telegram: configure `TELEGRAM_BOT_TOKEN` e `TELEGRAM_ALLOWED_USER_IDS`, depois execute `python main.py --telegram`. Somente chats privados autorizados acessam o agente. A base é compartilhada entre autorizados; o contexto e as confirmações são separados por usuário. Não envia mensagens comerciais automaticamente.

IA local: configure `AI_PROVIDER=ollama`, `OLLAMA_MODEL` e disponibilize Ollama em `127.0.0.1:11434`. `/ai Nome` interpreta trechos, sem alterar evidências ou score. IA em nuvem não faz parte desta versão.

Também pode configurar pela janela **Configuração → IA local (Ollama)**: liste modelos instalados, selecione e ative. O SAZABI consulta `/api/tags` e `/api/show` antes de ativar; modelos remotos e modelos sem capacidade de geração de texto são recusados. Ativação não baixa nem carrega um modelo. `/api/chat` executa a interpretação somente quando você pede `/ai` e existem evidências com fonte.

Respostas incompletas, vazias, excessivas ou com chamadas de ferramentas são rejeitadas. O texto gerado é apresentado como interpretação não validada e não é incorporado ao histórico de evidências. Em falha, os relatórios determinísticos continuam disponíveis. Referências: [modelos instalados](https://docs.ollama.com/api/tags) e [chat](https://docs.ollama.com/api/chat).

## Verificação

`python -m pytest -q` executa os testes offline depois de instalar `requirements.txt`. Como alternativa de ambiente, instale em `.test-deps` e rode `python run_tests.py`.

`python tests/native_desktop_check.py` verifica a janela real com bases em memória, incluindo configuração com respostas controladas. `--screenshots` captura somente as próprias janelas de teste em `data/desktop-previews/`.

`python tests/public_network_check.py` realiza GETs públicos sem credenciais e sem gravar empresas. Busca Tavily autenticada, Telegram e Ollama precisam de validação com sua conta/serviço. Não confunda teste offline com validação em produção.

Contratos: [Tavily Search](https://docs.tavily.com/documentation/api-reference/endpoint/search), [Tavily Usage](https://docs.tavily.com/documentation/api-reference/endpoint/usage), [robots.txt](https://www.rfc-editor.org/rfc/rfc9309.html).
