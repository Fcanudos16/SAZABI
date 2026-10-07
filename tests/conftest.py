import pytest

from tests.factories import build_agent
from core.config import Config
from notifications.notifier import Notifier


class RecordingNotifier(Notifier):
    channel = "test"

    def __init__(self):
        self.messages = []

    def send(self, message):
        self.messages.append(message)


@pytest.fixture
def notifier():
    return RecordingNotifier()


@pytest.fixture
def agent(notifier):
    config = Config(database_path=":memory:", mock=True)
    return build_agent(config, notifier=notifier)
