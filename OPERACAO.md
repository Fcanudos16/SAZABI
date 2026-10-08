# Operação do SAZABI

## Primeira execução

Execute `python main.py` ou `iniciar_sazabi.cmd` no Windows. A inicialização mostra somente o mascote, sem dashboard ou terminal aberto. Clique direito no personagem → Configuração, informe sua chave Tavily e clique em Salvar e conectar. A chave é validada por `GET /usage` antes de substituir a configuração anterior. Uma falha de validação preserva a chave anterior.

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

O personagem usa seis poses locais, pré-carregadas da arte original. Estados de trabalho vêm de eventos do agente: análise do comando, consulta às fontes, processamento, resultados encontrados e entrega. Uma pesquisa vazia não emite FOUND. Falhas e páginas ainda não identificadas têm mensagens próprias; não são anunciadas como oportunidades qualificadas.

Clique abre ou fecha o terminal. Arraste move o personagem e salva sua posição. O terminal tem até 620 × 440 px, sem maximização, e é posicionado na área útil do monitor próximo ao mascote. Escape, × ou perda de foco ocultam o terminal sem encerrar o agente. O resultado permanece na memória da sessão e pesquisas ficam no SQLite.

O balão de conclusão dura 5,5 segundos ou até interação. Ele usa uma janela sem ativação para não roubar foco. O personagem não possui caixa de texto permanente. Sempre no topo e redução de movimento podem ser alternados no menu de contexto. O aplicativo não mantém rotina de prospecção contínua.

Para sair, use Clique direito → Encerrar SAZABI, ou `sair` no terminal. O processo aguarda a tarefa atual para fechar o SQLite com segurança; as requisições mantêm seus timeouts. A janela pequena não executa comandos de shell: todas as entradas passam pelo roteador existente.

O mascote usa APIs Win32/GDI+. A máscara da janela exclui o fundo claro e a franja do JPEG conectados ao exterior de cada recorte; olhos brancos continuam opacos. O JPEG não é regravado, os pixels coloridos não são retocados e nenhum sprite é gerado por IA. A implementação não oferece mascote nativo em Linux/macOS; nesses sistemas use `--cli`.

O personagem respira por deslocamentos sutis, pisca em intervalos variados e faz transições suaves entre as seis expressões. Sob o cursor e durante o arraste, a translação autônoma pausa, mas as piscadas continuam. Clique direito → Reduzir movimento desativa as animações. A barra de rolagem do terminal acompanha o tema preto e verde.

Sem interação ou tarefa por dois minutos, ele dorme com a pose oficial levemente abaixada e pequenas bolhas, preservando os olhos originais. O primeiro clique esquerdo/tentativa de arraste apenas acorda, sem abrir o terminal ou mover o personagem. Comandos, nova pesquisa e clique direito aguardam os 700 ms de despertar. Pesquisa em andamento impede sono. **Clique direito → Dormir após** permite Nunca, 1, 2 ou 5 minutos. Terminal ou menu aberto também impedem sono. Os tempos detalhados ficam em `assets/sazabi/animation.json`; reinicie após editar esse arquivo. Nenhuma animação requer chave de API.

A arte plana não contém camadas separadas de cabeça e torso. Os movimentos do conjunto preservam o personagem. Pousar usa uma redução uniforme e temporária de até 2%, preservando proporções e o JPEG. Piscadas normais continuam como composição; no sono, nenhuma pálpebra é desenhada sobre a imagem.

Repouso usa a pose superior central; trabalho e arraste usam a superior esquerda. Ao soltar, a pose inferior esquerda pousa e retorna à tarefa atual ou repouso. Clique direito ativa a pose inferior central enquanto o popup permanece aberto. Passar sobre **Encerrar SAZABI** usa exclusivamente a pose inferior direita; sair da opção restaura a pose do menu. Apenas clicar ou confirmar com Enter encerra. O popup local aceita setas, Enter, Escape e fechamento por perda de foco, sem bloquear as animações.

Posição e preferências são guardadas em `companion.json` ao lado do banco. Se um monitor for removido, a posição é limitada à área útil disponível na próxima abertura. Coordenadas de monitores negativos são tratadas por Win32; combinações de escalas DPI e monitores físicos precisam de validação no equipamento de destino.

## Monitor do computador

Use **Clique direito → Monitor do sistema**. Não exige chave de API nem Ollama. CPU, RAM, disco e tempo ligado são coletados localmente com `psutil`, a cada segundo, em uma thread separada da pesquisa e da interface. O disco é a raiz da unidade corrente. Informações de máquina são mostradas apenas nessa janela, sem envio ou persistência no SQLite.

Fechar ou minimizar pausa novas leituras. Reabrir aguarda uma amostra nova e não cria outra thread. Sempre no topo também se aplica ao monitor. Ao encerrar SAZABI, o coletor recebe sinal de encerramento. Se faltar `psutil`, instale com `python -m pip install -r requirements.txt` usando o Python que inicia o aplicativo e reinicie. O restante do SAZABI continua acessível.

## Banco e recuperação

SQLite usa WAL e chaves estrangeiras. Ao iniciar com banco em arquivo, é criado backup verificado em `data/backups/`. `python main.py --backup` cria outro backup. Não há exclusão automática.

Para recuperação, pare o aplicativo, preserve uma cópia do backup e execute `python main.py --db caminho/do/backup.db`. O schema é atualizado ao abrir bases anteriores, sem apagar as empresas existentes.

Dados de demonstração das versões antigas continuam apenas no antigo `data/sazabi_mock.db`, caso ele exista; esse arquivo não é aberto por padrão. Os testes atuais injetam dados sintéticos explicitamente e usam bases isoladas. Nunca aponte testes para seu banco real.

## Recursos opcionais

Terminal: `python main.py --cli`. Execução única: `python main.py -c "/status"`.

Telegram: configure `TELEGRAM_BOT_TOKEN` e `TELEGRAM_ALLOWED_USER_IDS`, depois execute `python main.py --telegram`. Somente chats privados autorizados acessam o agente. A base é compartilhada entre autorizados; o contexto e as confirmações são separados por usuário. Não envia mensagens comerciais automaticamente.

IA local: configure `AI_PROVIDER=ollama`, `OLLAMA_MODEL` e disponibilize Ollama em `127.0.0.1:11434`. `/ai Nome` interpreta trechos, sem alterar evidências ou score. IA em nuvem não faz parte desta versão.

Também pode configurar pelo menu do mascote **Configuração**, seção Ollama: clique em Atualizar, selecione e ative. O SAZABI consulta `/api/tags` e `/api/show` antes de ativar; modelos remotos e modelos sem capacidade de geração de texto são recusados. Ativação não baixa nem carrega um modelo. `/api/chat` executa a interpretação somente quando você pede `/ai` e existem evidências com fonte.

Respostas incompletas, vazias, excessivas ou com chamadas de ferramentas são rejeitadas. O texto gerado é apresentado como interpretação não validada e não é incorporado ao histórico de evidências. Em falha, os relatórios determinísticos continuam disponíveis. Referências: [modelos instalados](https://docs.ollama.com/api/tags) e [chat](https://docs.ollama.com/api/chat).

## Verificação

`python -m pytest -q` executa os testes offline depois de instalar `requirements.txt`. Como alternativa de ambiente, instale em `.test-deps` e rode `python run_tests.py`.

O runner cria diretórios únicos de teste em `data/test-runs/`, sem reutilizar nem apagar bases anteriores. `SAZABI_TEST_DEPS` permite indicar outra pasta de dependências de teste quando a pasta antiga estiver inacessível no Windows.

`python tests/native_desktop_check.py` verifica inicialização só com mascote, seis poses, região transparente e olhos, arraste versus clique, limite do terminal, fechamento ao perder foco, conclusão sem roubar foco, configuração e encerramento. Usa banco em memória e respostas controladas. `--screenshots` captura somente as próprias janelas de teste em `data/desktop-previews/`; capturas com prefixo `fixture-` usam dados sintéticos exclusivos dos testes.

`python tests/public_network_check.py` realiza GETs públicos sem credenciais e sem gravar empresas. Busca Tavily autenticada, Telegram e Ollama precisam de validação com sua conta/serviço. Não confunda teste offline com validação em produção.

Contratos: [Tavily Search](https://docs.tavily.com/documentation/api-reference/endpoint/search), [Tavily Usage](https://docs.tavily.com/documentation/api-reference/endpoint/usage), [robots.txt](https://www.rfc-editor.org/rfc/rfc9309.html).
