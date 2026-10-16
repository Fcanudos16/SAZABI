import pytest
from ui.countdown.commands import parse_duration, CommandProcessor, TimeFormatError
from ui.countdown.timer_engine import TimerEngine, State


@pytest.mark.parametrize('text,cs', [
    ('cinco minutos',30000), ('5:00:00',30000), ('5:00',30000),
    ('três minutos',18000), ('vinte e cinco minutos',150000),
    ('um minuto e trinta segundos',9000), ('1 hora e 5 minutos',390000),
    ('meia hora',180000), ('um minuto e meio',9000),
    ('duas horas e meia',900000), ('timer de cinco minutos',30000),
    ('90 segundos',9000),
])
def test_duration(text, cs):
    assert parse_duration(text) == cs


@pytest.mark.parametrize('text', ['cinco', '-5 minutos', 'cinco minutos banana',
                                  'um minuto e', 'vinte cinco minutos', '5:60:00',
                                  'dois minutos dois minutos', 'minutos'])
def test_invalid_duration(text):
    with pytest.raises(TimeFormatError):
        parse_duration(text)


def test_portuguese_commands_and_running_guard():
    engine = TimerEngine()
    commands = CommandProcessor(engine)
    assert commands.execute('cinco minutos').ok
    assert engine.configured_cs == 30000 and engine.state is State.CONFIGURED
    assert commands.execute('iniciar').ok
    assert not commands.execute('5:00:00').ok
    assert commands.execute('pausar').ok
    assert commands.execute('retomar').ok
    assert commands.execute('parar').ok
    assert commands.execute('iniciar cinco minutos').ok
    assert engine.state is State.RUNNING
    assert commands.execute('zerar').ok
    assert commands.execute('set cinco minutos').ok
