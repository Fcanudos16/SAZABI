"""Motor do timer regressivo do SAZABI COUNTDOWN HUD.

Lógica pura, sem dependência de interface gráfica.

A contagem NÃO subtrai valores fixos a cada atualização. O motor guarda um
instante-alvo (deadline) em nanossegundos de um relógio monotônico e calcula o
tempo restante real a cada consulta. Assim, atrasos da interface ou do sistema
operacional nunca acumulam erro.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Callable

NS_PER_CS = 10_000_000          # 1 centésimo de segundo = 10 ms
CS_PER_SECOND = 100
CS_PER_MINUTE = 6000
MAX_MINUTES = 9999
MAX_CS = (MAX_MINUTES * 60 + 59) * CS_PER_SECOND + 99


class State(Enum):
    STANDBY = "STANDBY"
    CONFIGURED = "CONFIGURED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETE = "COMPLETE"


class EngineError(Exception):
    """Operação inválida para o estado atual. `message` já vem pronta para o terminal."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def split_cs(cs: int) -> tuple[int, int, int]:
    """Converte centésimos em (minutos, segundos, centésimos)."""
    minutes, rest = divmod(cs, CS_PER_MINUTE)
    seconds, hundredths = divmod(rest, CS_PER_SECOND)
    return minutes, seconds, hundredths


def format_time(cs: int) -> str:
    """Formata no padrão da HUD: M:SS:CC."""
    m, s, c = split_cs(cs)
    return f"{m}:{s:02d}:{c:02d}"


class TimerEngine:
    def __init__(self, clock_ns: Callable[[], int] = time.monotonic_ns):
        self._clock = clock_ns
        self._state = State.STANDBY
        self._configured_cs = 0
        self._remaining_ns = 0      # válido quando o timer NÃO está em RUNNING
        self._deadline_ns = 0       # válido somente em RUNNING

    # ------------------------------------------------------------ consulta
    @property
    def state(self) -> State:
        return self._state

    @property
    def configured_cs(self) -> int:
        return self._configured_cs

    def remaining_ns(self) -> int:
        if self._state is State.RUNNING:
            return max(0, self._deadline_ns - self._clock())
        return self._remaining_ns

    def remaining_cs(self) -> int:
        """Tempo restante em centésimos, arredondado para cima.

        O arredondamento para cima garante que a HUD só exiba 0:00:00 quando a
        contagem realmente terminou.
        """
        return -(-self.remaining_ns() // NS_PER_CS)

    # --------------------------------------------------------------- tick
    def tick(self) -> bool:
        """Verifica o fim da contagem. Retorna True se o estado mudou para COMPLETE."""
        if self._state is State.RUNNING and self._clock() >= self._deadline_ns:
            self._remaining_ns = 0
            self._state = State.COMPLETE
            return True
        return False

    # ------------------------------------------------------------ comandos
    def set_time(self, cs: int) -> None:
        if self._state is State.RUNNING:
            raise EngineError("TIMER RUNNING - PAUSE OR STOP FIRST")
        if cs <= 0:
            raise EngineError("TIME MUST BE GREATER THAN ZERO")
        if cs > MAX_CS:
            raise EngineError("TIME TOO LARGE")
        self._configured_cs = cs
        self._remaining_ns = cs * NS_PER_CS
        self._state = State.CONFIGURED

    def start(self) -> None:
        self.tick()
        if self._state is State.STANDBY:
            raise EngineError("NO TIME SET - USE: SET M:SS")
        if self._state is State.RUNNING:
            raise EngineError("ALREADY RUNNING")
        if self._state is State.PAUSED:
            raise EngineError("COUNTDOWN PAUSED - USE RESUME")
        # CONFIGURED ou COMPLETE (reinicia a partir do tempo configurado)
        self._remaining_ns = self._configured_cs * NS_PER_CS
        self._begin_run()

    def pause(self) -> None:
        self.tick()
        if self._state is not State.RUNNING:
            raise EngineError("NOT RUNNING")
        self._remaining_ns = max(0, self._deadline_ns - self._clock())
        self._state = State.PAUSED

    def resume(self) -> None:
        if self._state is not State.PAUSED:
            raise EngineError("NOT PAUSED")
        self._begin_run()

    def reset(self) -> None:
        """Restaura o tempo configurado, sem iniciar a contagem."""
        if self._configured_cs <= 0:
            raise EngineError("NO TIME SET")
        self._remaining_ns = self._configured_cs * NS_PER_CS
        self._state = State.CONFIGURED

    def stop(self) -> None:
        """Interrompe tudo e volta ao STANDBY (0:00:00), pronto para nova configuração."""
        self._configured_cs = 0
        self._remaining_ns = 0
        self._state = State.STANDBY

    def dismiss(self) -> bool:
        """Dispensa o alerta de COMPLETE e volta ao tempo configurado (CONFIGURED)."""
        if self._state is not State.COMPLETE:
            return False
        self._remaining_ns = self._configured_cs * NS_PER_CS
        self._state = State.CONFIGURED
        return True

    # ------------------------------------------------------------ interno
    def _begin_run(self) -> None:
        self._deadline_ns = self._clock() + self._remaining_ns
        self._state = State.RUNNING
