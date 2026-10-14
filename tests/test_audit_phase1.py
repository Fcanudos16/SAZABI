"""Regressions reproduced during the phase-one audit; all data is synthetic."""
import logging
import pytest
from database.models import CompanyProfile
from utils.deduplication import is_same_company
from utils.logger import setup_logging


@pytest.mark.parametrize('command', ['/ai', '/ollama Oficina Silva'])
def test_new_command_cancels_stale_delete_confirmation(agent, command):
    agent.handle('investigue Oficina Silva')
    agent.handle('/forget Oficina Silva')
    agent.handle(command)
    agent.handle('sim')
    assert agent.companies.count() == 1


def test_unknown_cities_are_not_evidence_of_same_business():
    a = CompanyProfile(name='Oficina Silva', website='https://first.example')
    b = CompanyProfile(name='Oficina Silva', website='https://second.example')
    assert not is_same_company(a, b)


def test_log_redacts_exception_and_standalone_credential(tmp_path):
    path = tmp_path / 'audit.log'
    logger = setup_logging(log_file=str(path))
    try:
        logger.info('Credential %s', 'tvly-audit-fixture-123456')
        try:
            raise RuntimeError('token=audit-exception-secret')
        except RuntimeError:
            logger.exception('Synthetic error')
        for handler in logger.handlers:
            handler.flush()
        text = path.read_text(encoding='utf-8')
        assert 'tvly-audit-fixture-123456' not in text
        assert 'audit-exception-secret' not in text
        assert 'RuntimeError' in text and '[REDACTED]' in text
    finally:
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)
