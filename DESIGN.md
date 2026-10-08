# SAZABI — mascote primeiro, interface depois

A experiência principal é um personagem 2D de desktop. A antiga interface de dashboard foi removida. Na inicialização aparecem somente a arte original e sua região de janela; não há home, navegador, terminal, menu ou balão permanente.

## Arte original

`assets/sazabi/original.jpg` é uma cópia byte a byte da arte enviada pelo usuário (`download.jpg`). SHA-256:

`099f5270e553adf574061792cf5f3974318e97f00e9d489520f1fd1f7120cf57`

A prancha contém as seis poses. `states.json` define seis **recortes de exibição**, sem gerar arquivos derivados. GDI+ decodifica o JPEG na memória uma vez e o Tk recebe os mesmos valores RGB, sem escala, interpolação, filtros, tintas, espelhamento ou alteração de proporções. Todas as poses são pré-carregadas. Nenhuma IA participa do desenho ou da animação.

O canvas mede 190 × 220 px. A janela recebe uma região Win32 que exclui o fundo claro e a franja do JPEG conectados às bordas do recorte, conservando regiões brancas fechadas, como os olhos. O limiar é específico para a paleta escura desta arte. Isso é uma máscara da janela, não uma modificação do arquivo ou uma recoloração de pixels. A região também limita o recebimento de cliques.

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

As expressões usam crossfade com easing entre a janela principal e uma única camada anterior, sem ciclar a prancha como frames. A transição normal dura 350 ms; FOUND/RESPONDING usam 500 ms. Um evento novo substitui a transição em andamento e descarta a camada anterior. Não existe fila de animações que atrase uma tarefa real.

O repouso combina respiração sugerida por deslocamento de até três pixels, oscilação lateral e variação controlada de duração, amplitude e direção. Resultados recebem uma pequena reação vertical. A posição salva permanece fixa; os deslocamentos temporários respeitam a área útil do monitor. Sob o cursor e durante o arraste, a translação autônoma pausa para facilitar a interação, mas o relógio de comportamento e as piscadas continuam.

As piscadas duram aproximadamente 220 ms, em intervalos variáveis. O renderer encontra as duas ilhas claras fechadas de cada pose e aplica máscaras temporárias de pálpebra na composição, usando uma cor escura amostrada do rosto adjacente. O JPEG e os PhotoImages originais não são modificados. Olhos sem detecção segura não recebem uma máscara inventada.

**Limite da arte plana:** não há camada independente de cabeça, pescoço ou corpo. Por isso não há inclinação isolada da cabeça nem expansão do torso. O movimento do conjunto sugere respiração e postura, preservando proporções, contornos e pixels da arte. Separar ou redesenhar essas partes exigiria novos assets do autor.

## Sono e autonomia

Após 120 segundos sem interação, sem terminal aberto e sem tarefa, IDLE entra em FALLING_ASLEEP (1.200 ms), depois SLEEPING. As pálpebras fecham gradualmente; a respiração fica lenta e surgem no máximo duas bolhas independentes, com tamanhos, velocidades, trajetórias e intervalos variados. As bolhas crescem, sobem e desaparecem por opacidade. São janelas passivas que deixam os cliques passar.

Clique, arraste, abertura do terminal/configuração e comandos acordam o mascote. WAKE_UP dura 700 ms. O clique abre o terminal imediatamente, sem esperar a animação. Erros e tarefas têm prioridade sobre autonomia; os eventos sucessivos do pipeline continuam autoritativos, para que WORKING não bloqueie FOUND/RESPONDING. Dormir nunca suspende o agente nem o worker.

O menu **Dormir após** oferece Nunca, 1, 2 e 5 minutos; a preferência é salva em `companion.json`. `assets/sazabi/animation.json` controla os tempos, piscadas e reação opcional ao hover. Zero desativa o sono. Por padrão, apenas passar o cursor não acorda o mascote.

Reduzir movimento desativa piscadas, transições, translação e bolhas. O timer leve de comportamento continua, sem efeitos visuais. A apresentação usa um timer de 50 ms, atualiza pálpebras apenas quando o nível muda e suspende os efeitos quando a janela não está visível. Não há geração contínua de imagens nem IA em runtime.

## Interação

- Clique esquerdo: alterna o terminal próximo ao personagem.
- Movimento superior a seis pixels durante o clique: arrasta; não abre o terminal.
- Clique direito: terminal, nova pesquisa, configuração, sempre no topo, reduzir movimento e encerrar.
- A posição é mantida em memória e salva localmente. Os limites são calculados pela área útil do monitor.
- Mascote e balões usam NOACTIVATE; não disputam foco com outros aplicativos.

## Terminal secundário

Janela sem moldura de até 620 × 440 px, nunca maximizada automaticamente. Abre à direita ou esquerda do mascote conforme o espaço disponível; junto à borda inferior, sobe. É limitada à área útil do monitor.

Preto `#080d0a`, texto verde `#8fdfa7`, borda `#254331`, informação secundária `#72937b`, fonte Consolas monoespaçada. Sem efeitos Matrix, neon animado ou indicadores fictícios. Mostra os eventos reais, respostas, fontes e controles de resultados/histórico/ajuda. Comando em uma linha inferior, Enter para enviar.

A barra lateral de rolagem usa trilho preto e controle verde escuro, com realce verde ao passar o cursor e pressionar.

Clique novamente no mascote, Escape, × ou perda de foco ocultam o terminal. Pesquisa e memória continuam ativas. A conclusão não abre o terminal: apenas atualiza a pose e mostra um balão de até 240 px de texto por 5,5 segundos. Entrada com fade e deslocamento de cinco pixels em 250 ms; saída com fade. Clicar no balão o dispensa.

Configuração é uma janela opcional separada, acessível pelo menu do mascote. Mantém chave Tavily mascarada e seleção de Ollama local. Não substitui a experiência principal.

## Camadas

| Módulo | Responsabilidade |
|---|---|
| `core/agent.py` | pipeline existente e eventos de trabalho real |
| `core/worker.py` | fila de comandos/eventos e thread proprietária do SQLite |
| `ui/companion.py` | estados, interação, notificações e ciclo de vida do mascote |
| `ui/behavior.py` | SazabiStateManager, SazabiAnimationController, SazabiIdleController e SazabiSleepController, testáveis sem Tk |
| `ui/renderer.py` | SazabiRenderer, pálpebras por composição e SazabiTransitionController com no máximo duas expressões |
| `ui/effects.py` | bolhas de sono e SazabiNotificationController com timers canceláveis |
| `ui/sprites.py` | leitura original, recortes e máscaras, sem regravar a arte |
| `ui/native.py` | regiões, não ativação, posição e área útil no Windows |
| `ui/terminal.py` | terminal secundário e histórico visual limitado |
| `ui/preferences.py` | conexões Tavily/Ollama sob demanda |

O terminal mantém até 2.500 linhas em memória para limitar consumo; as pesquisas completas continuam no SQLite e podem ser consultadas com `/results`. A thread gráfica não acessa o banco. Nenhum texto do terminal é executado como comando do sistema operacional.

## Verificação e limites

`tests/native_desktop_check.py` cobre a janela real do Windows, máscaras e olhos, seis poses, arraste/clique, foco, terminal limitado, pesquisa em segundo plano, configuração e encerramento. Os testes sintéticos não usam o banco de produção. A suíte verifica também o hash da arte, preservação dos pixels, posição em coordenadas negativas e eventos sem resultados inventados.

Também verifica crossfade, pálpebras, sono/despertar, limite de bolhas, animação durante arraste, notificação, opção Nunca e prioridade de tarefas. A suíte pura simula 12 horas de relógio de comportamento; isso não equivale a um teste de 12 horas de CPU/GPU, memória ou renderização no desktop. Não foi realizado benchmark prolongado no equipamento do usuário.

O mascote requer Windows. O backend/CLI permanece portátil. O posicionamento foi testado matematicamente em áreas de múltiplos monitores, mas escalas DPI mistas e monitores físicos adicionais exigem teste no equipamento correspondente. Não houve certificação de acessibilidade por leitor de tela.
