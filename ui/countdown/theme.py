"""Sistema de design do SAZABI COUNTDOWN HUD: cores, fontes e geometria.

Sem dependência do Qt, para poder ser importado por qualquer módulo.
A geometria usa um espaço lógico de 700 x 340 unidades, recortado da imagem de
referência (origem em x=30, y=10 da imagem); a HUD inteira é escalada a partir dele.
"""

# ----------------------------------------------------------------- paleta
BG = "#000000"            # preto profundo
GREEN = "#39FF6B"         # verde neon: números, linhas e elementos funcionais
GREEN_LUM = "#9BFFB6"     # verde luminoso: estados ativos e destaques
GREEN_MID = "#1FA84A"     # verde intermediário: itens inativos
GREEN_DIM = "#0E5A27"     # verde escuro: áreas secundárias
GREEN_DARK = "#07290F"    # verde muito escuro
PLATE_A = "#041A0A"       # placa traseira (degradê discreto)
PLATE_B = "#0A3A1B"
PLATE_C = "#062A18"
GRAY_LINE = "#2B3A2F"     # contornos e separadores discretos
RED = "#FF2A2A"           # vermelho intenso: SOMENTE o estado COMPLETE
RED_DARK = "#5E0B10"

# ----------------------------------------------------------------- fontes
MONO_FAMILIES = ["Consolas", "Lucida Console", "Courier New", "DejaVu Sans Mono", "monospace"]
JP_FAMILIES = [
    "Yu Gothic UI", "Yu Gothic", "MS Gothic", "Meiryo",
    "Noto Sans CJK JP", "Noto Sans JP", "IPAGothic", "WenQuanYi Zen Hei",
]

# ----------------------------------------------------------------- janela
LOGICAL_W = 700
LOGICAL_H = 340
DEFAULT_WIDTH = 400       # altura = largura * 340 / 700  (400 x 194)
MIN_WIDTH = 280
MAX_WIDTH = 1100
TERMINAL_HEIGHT = 104
SCREEN_MARGIN = 24

# ----------------------------------------------------------------- tempos
TICK_INTERVAL_MS = 10     # atualização da HUD (centésimos de segundo)
BLINK_INTERVAL_MS = 250   # 2 piscadas completas por segundo no estado COMPLETE
