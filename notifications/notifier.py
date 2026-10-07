"""Notificações. A V1 só tem o canal de console; Telegram entra como outro Notifier."""
from __future__ import annotations

from abc import ABC, abstractmethod


class Notifier(ABC):
    channel = "console"

    @abstractmethod
    def send(self, message: str) -> None:
        ...


class ConsoleNotifier(Notifier):
    """Simula o envio imprimindo no terminal (útil no modo mock)."""
    channel = "console"

    def __init__(self, prefix: str = "[notificação simulada]"):
        self.prefix = prefix

    def send(self, message: str) -> None:
        print(f"\n{self.prefix}\n{message}\n")


class NullNotifier(Notifier):
    channel = "none"

    def send(self, message: str) -> None:
        return None
