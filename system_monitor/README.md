# Origem e integração

Os módulos `cpu.py`, `memory.py`, `disk.py`, `uptime.py`, `system_info.py` e `formatter.py` foram incorporados do projeto **Python System Monitor**, fornecido pelo usuário na pasta `System monitor`.

A pasta original permanece intacta. Ambientes virtuais, caches e o loop que limpa o terminal não foram copiados. O namespace próprio evita conflito com `utils` do SAZABI.

Adaptações: unidades binárias explícitas; correção de porcentagem negativa e padding do uptime; tratamento de frequência indisponível. `service.py` agrega os sensores e executa a coleta em uma única thread pausável, com uma fila de tamanho um. `ui/system_monitor.py` apresenta as leituras em Tkinter. Não há acesso ao banco, chamadas de rede, encerramento de processos ou ações administrativas.

Os dados são somente do computador local. O disco exibido é a raiz da unidade corrente, como no projeto original; não é uma soma de todos os discos. Frequência e número de núcleos físicos podem estar indisponíveis conforme o sistema. Minimizar/fechar interrompe novas amostras; uma leitura em andamento pode terminar, mas seu resultado é descartado. Ao reabrir, a linha de base de CPU é refeita na mesma thread.
