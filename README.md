# SAZABI — inteligência comercial local

Mascote de desktop que pesquisa páginas públicas pela **Tavily**, identifica empresas a partir dos próprios sites e organiza evidências e possíveis oportunidades em SQLite. Ao iniciar, aparece somente o personagem 2D da arte original do usuário. Não abre dashboard, navegador, servidor ou porta web.

**O uso normal não carrega empresas fictícias.** A base começa vazia. Dados sintéticos existem apenas em `tests/`, para testes isolados; o antigo comando `--mock` foi removido.

## Abrir e configurar

O mascote requer **Windows e Python 3.9+ com Tcl/Tk**. Usa GDI+ e regiões nativas do Windows, sem bibliotecas extras de runtime. CLI e backend continuam independentes da camada visual.

```powershell
git clone https://github.com/Fcanudos16/SAZABI.git
cd SAZABI
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
- **Clique direito** dá acesso a nova pesquisa, configuração, Sempre no topo, Reduzir movimento e Encerrar SAZABI.
- Ao terminar, a pose muda e um pequeno aviso aparece por 5,5 segundos. Os resultados não são abertos automaticamente e o foco de outro aplicativo é preservado.
- A posição e as preferências do mascote ficam em `data/companion.json`, junto à pasta do banco configurado.

As seis poses são vistas da mesma prancha JPEG, sem redimensionamento, recoloração, redesenho ou geração por IA. O arquivo original permanece intacto em `assets/sazabi/original.jpg`, verificado por SHA-256. O mapeamento das poses está em `assets/sazabi/states.json`. A transparência é aplicada à região da janela, preservando o branco dos olhos. Consulte [DESIGN.md](DESIGN.md).

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
| `AI_PROVIDER` / `OLLAMA_MODEL` | `none` por padrão; `ollama` habilita `/ai Nome` |

`services.yaml` define os serviços oferecidos pela sua software house. IA não é necessária para a pesquisa e a análise por regras. Telegram e Ollama são opcionais; veja [OPERACAO.md](OPERACAO.md).

### Interpretação com Ollama local

Instale e abra o [Ollama](https://ollama.com/download), com um modelo de conversação baixado para seu computador. Clique direito no mascote → **Configuração**, e na seção Ollama clique em **Atualizar**, selecione um modelo e clique em **Ativar**. A escolha é salva no `.env` e passa a valer sem reiniciar. **Desativar** mantém a pesquisa e os relatórios por regras disponíveis.

Depois de investigar uma empresa, envie `/ai Nome da empresa`, ou `/ai` para a empresa selecionada anteriormente. O modelo recebe até oito trechos com URL e data, e produz uma interpretação separada em fatos, hipóteses e limitações. A resposta não é salva como evidência e não altera cadastro, score ou oportunidades. Não há acesso a ferramentas ou envio automático de contatos.

A conexão é fixa em `127.0.0.1:11434`. Modelos de nuvem são recusados; não exige chave de API para a IA local. Se o serviço não estiver disponível, a configuração orienta a abrir o Ollama ou executar `ollama serve`. A geração aguarda até 120 segundos por operação de rede; o primeiro carregamento depende do hardware e do modelo.

Diagnóstico sem baixar modelos: `python tests/ollama_local_check.py`. A validação da configuração verifica a presença e o tipo do modelo; a primeira execução de `/ai` verifica a geração efetiva.

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
