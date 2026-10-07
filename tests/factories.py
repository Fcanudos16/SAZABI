"""Synthetic data is explicitly injected only by automated tests."""
from core.bootstrap import build_agent as real_build_agent
from tests.mock_source import MockSource


def build_agent(config, notifier=None, sources=None):
    if sources is None and config.mock:
        sources = [MockSource()]
    return real_build_agent(config, notifier=notifier, sources=sources)
