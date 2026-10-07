import logging

from core.config import DEFAULT_SERVICES, load_config, read_env_file, read_services
from notifications.notifier import ConsoleNotifier, NullNotifier
from research.mock_source import MockSource
from database.models import SearchCriteria
from utils.logger import RedactFilter


def test_config_reads_env_file_and_services(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# c\nSAZABI_ENV=test\nDATABASE_PATH=x/y.db\nCACHE_TTL_HOURS=6\n")
    svc = tmp_path / "services.yaml"
    svc.write_text("services:\n  - sistemas web   # comentário\n  - \"automação\"\n", encoding='utf-8')
    for k in ("SAZABI_ENV", "DATABASE_PATH", "CACHE_TTL_HOURS"):
        monkeypatch.delenv(k, raising=False)
    cfg = load_config(str(env), str(svc))
    assert (cfg.env, cfg.database_path, cfg.cache_ttl_hours) == ("test", "x/y.db", 6.0)
    assert cfg.services == ["sistemas web", "automação"]


def test_config_defaults_and_mock_uses_separate_db(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_PATH", raising=False)
    cfg = load_config(str(tmp_path / "nope.env"), str(tmp_path / "nope.yaml"), mock=True)
    assert cfg.database_path.endswith("sazabi_mock.db") and cfg.services == DEFAULT_SERVICES
    assert read_env_file(str(tmp_path / "nope.env")) == {} and read_services(str(tmp_path / "x")) == DEFAULT_SERVICES


def test_log_filter_redacts_secrets():
    record = logging.LogRecord("x", logging.INFO, "f", 1, "token=abc123 e 123456789:ABCdefGhIJKlmNoPQRsTUVwxyz0123456789", (), None)
    RedactFilter().filter(record)
    assert "abc123" not in record.msg and "ABCdef" not in record.msg and "[REDACTED]" in record.msg


def test_console_and_null_notifiers(capsys):
    ConsoleNotifier().send("olá")
    assert "olá" in capsys.readouterr().out
    NullNotifier().send("nada")
    assert capsys.readouterr().out == ""


def test_mock_source_filters():
    src = MockSource()
    assert {r.city for r in src.search(SearchCriteria(city="campinas"))} == {"Campinas"}
    names = [r.name for r in src.search(SearchCriteria(city="São Paulo", segment="oficina"))]
    assert "Oficina Silva" in names and "Restaurante Beta" not in names
    assert all(r.estimated_size == "micro" for r in src.search(SearchCriteria(city="São Paulo", size="micro")))
    assert src.lookup("oficina silva").name == "Oficina Silva" and src.lookup("inexistente") is None
