# SAZABI — mascote primeiro, interface depois

A experiência principal é um personagem 2D de desktop. A antiga interface de dashboard foi removida. Na inicialização aparecem somente a arte original e sua região de janela; não há home, navegador, terminal, menu ou balão permanente.

## Arte original

`assets/sazabi/original.jpg` é uma cópia byte a byte da arte enviada pelo usuário (`download.jpg`). SHA-256:

`099f5270e553adf574061792cf5f3974318e97f00e9d489520f1fd1f7120cf57`

A prancha contém as seis poses. `states.json` define seis **recortes de exibição**, sem gerar arquivos derivados. GDI+ decodifica o JPEG na memória uma vez e o Tk recebe os mesmos valores RGB, sem escala, interpolação, filtros, tintas, espelhamento ou alteração de proporções. Todas as poses são pré-carregadas. Nenhuma IA participa do desenho ou da animação.

O canvas mede 190 × 220 px. A janela recebe uma região Win32 que exclui o fundo quase branco conectado às bordas do recorte, conservando regiões brancas fechadas, como os olhos. Isso é uma máscara da janela, não uma modificação do arquivo ou uma recoloração de pixels. A região também limita o recebimento de cliques. O antialias e as pequenas bordas da compressão original são preservados.

## Poses e eventos

| Estado | Posição na prancha | Evento real |
|---|---|---|
| IDLE | superior esquerda | aguardando, ou retorno após entrega |
| ANALYZING | superior central | comando enviado ao agente |
| RESEARCHING | superior direita | busca ou coleta de evidências |
| WORKING | inferior esquerda | processamento, análise ou configuração |
| FOUND | inferior central | empresas ou páginas realmente encontradas |
| RESPONDING | inferior direita | resultado pronto para entrega |

O mapeamento é configurável em `assets/sazabi/states.json`. O agente emite eventos; a interface não usa cronômetros para fingir etapas de pesquisa. FOUND permanece brevemente visível depois do resultado real, seguido de RESPONDING e retorno a IDLE. Sem resultado não há FOUND. Mensagens distinguem empresas identificadas de páginas pendentes e falhas.

As trocas podem usar um fade discreto de 80 ms da janela inteira. O menu Reduzir movimento o desativa. Não há deformações, resampling, caminhada artificial ou animação contínua em repouso.

## Interação

- Clique esquerdo: alterna o terminal próximo ao personagem.
- Movimento superior a seis pixels durante o clique: arrasta; não abre o terminal.
- Clique direito: terminal, nova pesquisa, configuração, sempre no topo, reduzir movimento e encerrar.
- A posição é mantida em memória e salva localmente. Os limites são calculados pela área útil do monitor.
- Mascote e balões usam NOACTIVATE; não disputam foco com outros aplicativos.

## Terminal secundário

Janela sem moldura de até 620 × 440 px, nunca maximizada automaticamente. Abre à direita ou esquerda do mascote conforme o espaço disponível; junto à borda inferior, sobe. É limitada à área útil do monitor.

Preto `#080d0a`, texto verde `#8fdfa7`, borda `#254331`, informação secundária `#72937b`, fonte Consolas monoespaçada. Sem efeitos Matrix, neon animado ou indicadores fictícios. Mostra os eventos reais, respostas, fontes e controles de resultados/histórico/ajuda. Comando em uma linha inferior, Enter para enviar.

Clique novamente no mascote, Escape, × ou perda de foco ocultam o terminal. Pesquisa e memória continuam ativas. A conclusão não abre o terminal: apenas atualiza a pose e mostra um balão de até 240 px de texto por 5,5 segundos. Clicar no balão o dispensa.

Configuração é uma janela opcional separada, acessível pelo menu do mascote. Mantém chave Tavily mascarada e seleção de Ollama local. Não substitui a experiência principal.

## Camadas

| Módulo | Responsabilidade |
|---|---|
| `core/agent.py` | pipeline existente e eventos de trabalho real |
| `core/worker.py` | fila de comandos/eventos e thread proprietária do SQLite |
| `ui/companion.py` | estados, interação, notificações e ciclo de vida do mascote |
| `ui/sprites.py` | leitura original, recortes e máscaras, sem regravar a arte |
| `ui/native.py` | regiões, não ativação, posição e área útil no Windows |
| `ui/terminal.py` | terminal secundário e histórico visual limitado |
| `ui/preferences.py` | conexões Tavily/Ollama sob demanda |

O terminal mantém até 2.500 linhas em memória para limitar consumo; as pesquisas completas continuam no SQLite e podem ser consultadas com `/results`. A thread gráfica não acessa o banco. Nenhum texto do terminal é executado como comando do sistema operacional.

## Verificação e limites

`tests/native_desktop_check.py` cobre a janela real do Windows, máscaras e olhos, seis poses, arraste/clique, foco, terminal limitado, pesquisa em segundo plano, configuração e encerramento. Os testes sintéticos não usam o banco de produção. A suíte verifica também o hash da arte, preservação dos pixels, posição em coordenadas negativas e eventos sem resultados inventados.

O mascote requer Windows. O backend/CLI permanece portátil. O posicionamento foi testado matematicamente em áreas de múltiplos monitores, mas escalas DPI mistas e monitores físicos adicionais exigem teste no equipamento correspondente. Não houve certificação de acessibilidade por leitor de tela.
