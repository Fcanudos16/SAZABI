"""Processamento dos comandos do mini terminal (sem dependência de interface)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional
import re
import unicodedata

from .timer_engine import (
    CS_PER_MINUTE,
    CS_PER_SECOND,
    MAX_MINUTES,
    EngineError,
    TimerEngine,
    format_time,
)

HELP_LINES = [
    "SET M:SS[:CC] | START | PAUSE | RESUME",
    "RESET | STOP | TOP [ON|OFF] | CLEAR | EXIT",
    "cinco minutos | 5:00:00 | iniciar | pausar | retomar",
    "M:SS:CC = minutos:segundos:centesimos",
]


class TimeFormatError(ValueError):
    def __init__(self, message: str = "INVALID TIME FORMAT"):
        super().__init__(message)
        self.message = message


def parse_time(text: str) -> int:
    """Converte 'M:SS' ou 'M:SS:CC' em centésimos de segundo.

    - M: 1 a 4 dígitos (aceita mais de 59 minutos)
    - SS: exatamente 2 dígitos, 00 a 59
    - CC: exatamente 2 dígitos, 00 a 99 (centésimos de segundo)
    """
    text = text.strip()
    if text.startswith("-"):
        raise TimeFormatError("NEGATIVE VALUES NOT ALLOWED")
    parts = text.split(":")
    if len(parts) not in (2, 3):
        raise TimeFormatError()
    if not all(p.isascii() and p.isdigit() for p in parts):
        raise TimeFormatError()
    minutes_s, seconds_s = parts[0], parts[1]
    cs_s = parts[2] if len(parts) == 3 else "00"
    if not (1 <= len(minutes_s) <= len(str(MAX_MINUTES))):
        raise TimeFormatError()
    if len(seconds_s) != 2 or len(cs_s) != 2:
        raise TimeFormatError()
    minutes, seconds, hundredths = int(minutes_s), int(seconds_s), int(cs_s)
    if seconds > 59:
        raise TimeFormatError("SECONDS MUST BE 00-59")
    return minutes * CS_PER_MINUTE + seconds * CS_PER_SECOND + hundredths


def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower())
                   if unicodedata.category(c) != 'Mn').strip()


def number(text):
    text = text.strip()
    if re.fullmatch(r'[0-9]{1,4}', text):
        return int(text)
    small = {'zero':0, 'um':1, 'uma':1, 'dois':2, 'duas':2, 'tres':3, 'quatro':4,
             'cinco':5, 'seis':6, 'sete':7, 'oito':8, 'nove':9, 'dez':10,
             'onze':11, 'doze':12, 'treze':13, 'catorze':14, 'quatorze':14,
             'quinze':15, 'dezesseis':16, 'dezasseis':16, 'dezessete':17,
             'dezoito':18, 'dezenove':19}
    tens = {'vinte':20,'trinta':30,'quarenta':40,'cinquenta':50,'sessenta':60,
            'setenta':70,'oitenta':80,'noventa':90}
    if text in small:
        return small[text]
    if text in tens:
        return tens[text]
    parts = text.split(' e ')
    if len(parts) == 2 and parts[0] in tens and 0 < small.get(parts[1], 0) < 10:
        return tens[parts[0]] + small[parts[1]]
    if text == 'cem':
        return 100
    raise TimeFormatError()


def parse_duration(text):
    """Strict local parsing: numeric HUD notation or Portuguese time units."""
    text = normalize(text)
    if ':' in text:
        return parse_time(text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'^(?:timer|temporizador|contagem) (?:de|para) ', '', text)
    if text == 'meia hora':
        return 30 * CS_PER_MINUTE
    total = 0
    seen = set()
    while text:
        match = re.match(r'(.+?)\s+(horas?|minutos?|segundos?)(?=\s|$)', text)
        if not match:
            raise TimeFormatError()
        unit = match[2].rstrip('s')
        if unit in seen:
            raise TimeFormatError()
        seen.add(unit)
        factor = {'hora':360000, 'minuto':6000, 'segundo':100}[unit]
        total += number(match[1]) * factor
        text = text[match.end():].strip()
        if text in ('e meio', 'e meia'):
            total += factor // 2
            text = ''
        elif text.startswith('e '):
            text = text[2:]
            if not text:
                raise TimeFormatError()
    if not seen:
        raise TimeFormatError()
    return total


@dataclass
class CommandResult:
    ok: bool = True
    lines: list[str] = field(default_factory=list)
    clear: bool = False


class CommandProcessor:
    """Interpreta comandos de texto e aplica ao TimerEngine.

    `on_top`: callback opcional (valor|None) -> bool para alternar "sempre visível".
    `on_exit`: callback opcional para encerrar o programa.
    Qualquer entrada, por mais estranha, resulta em um CommandResult; nunca levanta.
    """

    def __init__(
        self,
        engine: TimerEngine,
        on_top: Optional[Callable[[Optional[bool]], bool]] = None,
        on_exit: Optional[Callable[[], None]] = None,
    ):
        self.engine = engine
        self._on_top = on_top
        self._on_exit = on_exit

    def execute(self, text: str) -> CommandResult:
        try:
            return self._execute(text)
        except EngineError as exc:
            return CommandResult(False, [exc.message])
        except TimeFormatError as exc:
            return CommandResult(False, [exc.message])
        except Exception:  # defesa final: comando inválido nunca derruba o programa
            return CommandResult(False, ["INTERNAL ERROR"])

    # ------------------------------------------------------------------
    def _execute(self, text: str) -> CommandResult:
        tokens = text.strip().split()
        if not tokens:
            return CommandResult()
        cmd, args = tokens[0].lower(), tokens[1:]
        eng = self.engine
        cmd = {'definir':'set', 'ajustar':'set', 'iniciar':'start', 'comecar':'start',
               'pausar':'pause', 'retomar':'resume', 'continuar':'resume',
               'parar':'stop', 'zerar':'stop', 'reiniciar':'reset',
               'ajuda':'help', 'limpar':'clear', 'sair':'exit'}.get(normalize(cmd), cmd)

        if cmd == "set":
            if not args:
                raise TimeFormatError("USE: SET M:SS OU CINCO MINUTOS")
            cs = parse_duration(' '.join(args))
            eng.set_time(cs)
            return CommandResult(lines=[f"TIMER CONFIGURED {format_time(cs)}"])

        if cmd == 'start' and args:
            cs = parse_duration(' '.join(args))
            eng.set_time(cs)
            eng.start()
            return CommandResult(lines=[f"COUNTDOWN STARTED {format_time(cs)}"])

        if cmd in ("start", "pause", "resume", "reset", "stop", "help", "clear", "exit", "quit"):
            if args and cmd != "top":
                return CommandResult(False, [f"{cmd.upper()} TAKES NO ARGUMENTS"])

        if cmd == "start":
            eng.start()
            return CommandResult(lines=["COUNTDOWN STARTED"])
        if cmd == "pause":
            eng.pause()
            return CommandResult(lines=["COUNTDOWN PAUSED"])
        if cmd == "resume":
            eng.resume()
            return CommandResult(lines=["COUNTDOWN RESUMED"])
        if cmd == "reset":
            eng.reset()
            return CommandResult(lines=["TIMER RESET"])
        if cmd == "stop":
            eng.stop()
            return CommandResult(lines=["COUNTDOWN STOPPED"])
        if cmd == "help":
            return CommandResult(lines=list(HELP_LINES))
        if cmd == "clear":
            return CommandResult(clear=True)
        if cmd == "top":
            return self._top(args)
        if cmd in ("exit", "quit"):
            if self._on_exit is None:
                return CommandResult(False, ["NOT AVAILABLE"])
            self._on_exit()
            return CommandResult(lines=["SHUTTING DOWN"])
        try:
            cs = parse_duration(text)
        except TimeFormatError:
            return CommandResult(False, [f"UNKNOWN COMMAND: {cmd.upper()[:16]}", "TYPE HELP"])
        eng.set_time(cs)
        return CommandResult(lines=[f"TIMER CONFIGURED {format_time(cs)}", 'Digite iniciar para começar.'])

    def _top(self, args: list[str]) -> CommandResult:
        if self._on_top is None:
            return CommandResult(False, ["NOT AVAILABLE"])
        if len(args) > 1:
            return CommandResult(False, ["USE: TOP [ON|OFF]"])
        value: Optional[bool] = None
        if args:
            a = args[0].lower()
            if a not in ("on", "off"):
                return CommandResult(False, ["USE: TOP [ON|OFF]"])
            value = a == "on"
        state = self._on_top(value)
        return CommandResult(lines=[f"ALWAYS ON TOP: {'ON' if state else 'OFF'}"])
