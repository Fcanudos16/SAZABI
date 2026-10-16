> Migração para Groq: configure `AI_PROVIDER=groq`, `GROQ_API_KEY` e `GROQ_MODEL=llama-3.3-70b-versatile` no `.env` e reinicie. `/groq` envia evidências à API Groq. Consulte o README para a configuração atual.

> Atualização: o acesso à janela Configuração foi retirado do front. Configure APIs e Groq no `.env` e reinicie. O componente legado permanece interno, sem entrada no menu.

# Tema central e janelas desktop — 15/10/2026

## Implementação

A auditoria identificou uma aplicação Python/Tkinter, com worker separado para pesquisa, SQLite e renderização GDI/regiões Win32. O mascote já era a janela raiz independente; não havia HTML nem necessidade de recriar o sistema. As inconsistências eram cores espalhadas, configurações vermelhas com gradiente, barras nativas claras, seleção padrão e edição de chave pela interface.

- `ui/theme.py`: fonte única de cores, fontes base, botões, foco, seleção, hover, carregamento, barras superiores, opções Tk e estilos ttk. `install()` é chamado antes de criar componentes. A lista interna do Combobox recebe opções explícitas, inclusive quando aberta antes do terminal.
- `ui/terminal.py`, `autocomplete.py`, `preferences.py`, `ai_terminal.py`, `system_monitor.py`, `interaction.py` e `effects.py`: consomem o tema. Erros continuam identificados por texto, sem laranja; notificações e bolhas usam verdes. O magenta em `sprites.py` é uma chave invisível de transparência, não uma cor de interface.
- Configurações, LAYLA e monitor recebem barras sólidas com arraste, minimizar e fechar. O terminal mantém a barra compacta, agora arrastável. O tamanho fixo das janelas existentes foi preservado. Não há gradientes nem diálogos de credenciais. Não foram inventados seletores de arquivos ou novas telas.
- `ui/native.py`: minimizar/restaurar usa `ShowWindowAsync`, deixando o processamento dos eventos Map/Unmap a cargo do loop Tk. Chamadas síncronas de `ShowWindow` apresentaram falha fatal no Python 3.14 ao minimizar o monitor e foram substituídas.
- `core/agent.py`, `core/reports.py`, `core/worker.py` e `ui/companion.py`: orientações de configuração apontam para o `.env` privado.
- README, DESIGN e OPERACAO atualizados; FASE4_DESKTOP preservado como registro histórico, com aviso da atualização posterior.

## Arquitetura, sobreposição e foco

Um processo, um interpretador Tk, uma janela raiz do mascote. Terminal/resultados, preferências, monitor e LAYLA são Toplevels reutilizados ou recriados somente após destruição explícita. Terminal e resultados continuam na mesma janela compacta existente; abrir outra janela redundante não é necessário. Fechar resultados os oculta, sem interromper o worker; minimizar auxiliares mantém o mascote. Reabra pelo menu do personagem. **Encerrar SAZABI** cancela a execução e encerra as janelas e serviços do aplicativo.

O mascote usa `WS_EX_NOACTIVATE`, `WS_EX_TOOLWINDOW`, `SetWindowPos` com `HWND_TOPMOST`/`SWP_NOACTIVATE` e `SetWindowRgn` recortado pela máscara da arte. Somente a região visível intercepta o mouse; o personagem continua arrastável. A opção **Sempre no topo** continua disponível e ativada por padrão; uma preferência anterior desativada é respeitada. Janelas auxiliares recebem foco apenas por ações do usuário. Avisos não abrem resultados nem ativam a janela principal.

Coordenadas são globais e posicionadas por Win32, incluindo valores negativos. A área útil do monitor é consultada na inicialização, após arraste e periodicamente para recuperar posições fora da tela. Isso preserva o mecanismo anterior; não constitui validação física de vários monitores com DPI diferentes.

As artes, proporções, sprites e renderizador foram preservados. SHA-256 do original: `099f5270e553adf574061792cf5f3974318e97f00e9d489520f1fd1f7120cf57`.

## Credenciais e serviços

`core/config.py` permanece o único carregador de configuração. Use `.env.example` como referência e edite o `.env` privado existente, sem sobrescrevê-lo. Variáveis do ambiente têm prioridade. Reinicie após mudanças.

| Integração existente | Configuração privada |
| --- | --- |
| Tavily / pesquisa legada | `SEARCH_API_KEY` |
| LAYLA local | `LAYLA_URL`, `LAYLA_SESSION_COOKIE` quando necessário |
| Telegram opcional | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USER_IDS` |
| Groq | `AI_PROVIDER`, `GROQ_MODEL`, `GROQ_API_KEY`; requer chave do Groq |

Não há campo para inserir, editar ou revelar credenciais em nenhuma janela. A seleção de modelo Groq permanece funcional. Nenhuma credencial real foi lida, alterada ou incluída nesta entrega. O `.env` continua ignorado pelo Git. O backend mantém validação de configuração e tratamento de rejeições do provedor. A interface continua iniciando sem chave, com ajuda, histórico e dados locais disponíveis.

`/search` continua **unconfigured** sem adaptador gratuito autorizado. `/research` usa Tavily e pode consumir créditos. `/ai` mantém a ponte LAYLA existente e a revisão antes de enviar texto. Não houve nova integração, pesquisa simulada em produção ou substituição de resultados por demonstrações.

## Validação e limites

Os testes usam bases isoladas; os dados sintéticos permanecem exclusivamente em testes.

- `run_tests.py`: **257 passaram em 27,76 s**; regressão de backend, contratos, persistência, segurança, pesquisa e qualificação.
- `tests/native_phase4_check.py`: passou nas escalas Tk 1.333333, 2.0 e 2.666667; cancelamento, resultados, controles e configurações dentro da janela.
- `tests/native_theme_check.py`: passou com o tema normal e com `--probe`, que altera apenas o verde central antes da criação da UI. Verifica Combobox aberto, seleção, foco visual, ausência de campo de chave, minimizar/restaurar, identidade da janela do mascote e topmost sem tomar foco de outra janela nativa de teste. O teste não edita o tema em disco.
- `tests/native_desktop_check.py`: cenário sem credenciais e cenário com fixtures passaram, incluindo poses, transparência, arraste/pouso, sono, menu/teclado, configurações, métricas reais, minimizar/restaurar o monitor e encerramento. Uma execução conjunta encontrou perda de foco durante a seleção de submenu; o cenário com fixtures foi repetido isoladamente e passou. Isso não prova estabilidade diante de qualquer troca externa de foco.
- `tests/test_desktop.py` e `test_real_pipeline.py`: expectativas de orientação atualizadas para `.env`, preservando a verificação de que segredos não são salvos na conversa. O novo teste nativo é `tests/native_theme_check.py`.
- Capturas da janela de configurações foram inspecionadas: barra, controles e fundo preto/verde, sem campos de chave nem gradientes.

Não foi realizada validação manual com navegador, VS Code, Explorador e Alt+Tab, nem teste físico em múltiplos monitores. A evidência de sobreposição é o estado Win32 e a janela convencional independente do teste; não equivale à matriz manual de aplicativos solicitada. Tela segura, jogos em tela cheia exclusiva e aplicações que bloqueiam overlays não têm garantia de sobreposição.

Não foram usadas credenciais para pesquisa Tavily nem uma instância real da LAYLA nesta atualização; os testes dessas integrações usam transportes controlados. A validação autenticada e a matriz manual acima permanecem pendentes. O tema é carregado na inicialização, sem editor ou troca de tema em tempo real.
