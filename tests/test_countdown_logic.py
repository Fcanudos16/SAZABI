"""Testes da lógica (sem interface). Execute na raiz do projeto:

    python -m unittest discover -s tests -t . -v
"""

import random
import unittest

from ui.countdown.commands import CommandProcessor, TimeFormatError, parse_time
from ui.countdown.timer_engine import NS_PER_CS, EngineError, State, TimerEngine, format_time

SEC = 1_000_000_000


class FakeClock:
    def __init__(self):
        self.now = 123_456_789  # valor arbitrário: o relógio monotônico não tem origem fixa

    def __call__(self):
        return self.now

    def advance(self, seconds: float):
        self.now += int(round(seconds * SEC))


def make():
    clock = FakeClock()
    return clock, TimerEngine(clock)


class EngineTests(unittest.TestCase):
    # casos 2 e 3: começa zerado e não inicia sozinho
    def test_initial_state_is_zero_and_idle(self):
        clock, eng = make()
        self.assertEqual(eng.state, State.STANDBY)
        self.assertEqual(format_time(eng.remaining_cs()), "0:00:00")
        clock.advance(30)
        self.assertFalse(eng.tick())
        self.assertEqual(eng.state, State.STANDBY)
        self.assertEqual(eng.remaining_cs(), 0)

    def test_start_without_time_is_refused(self):
        _, eng = make()
        with self.assertRaises(EngineError):
            eng.start()
        self.assertEqual(eng.state, State.STANDBY)

    # caso 4
    def test_set_configures_without_starting(self):
        clock, eng = make()
        eng.set_time(parse_time("1:30"))
        self.assertEqual(eng.state, State.CONFIGURED)
        self.assertEqual(format_time(eng.remaining_cs()), "1:30:00")
        clock.advance(10)
        eng.tick()
        self.assertEqual(format_time(eng.remaining_cs()), "1:30:00")

    def test_zero_time_is_refused(self):
        _, eng = make()
        with self.assertRaises(EngineError):
            eng.set_time(0)

    # casos 5, 6, 7
    def test_start_pause_resume(self):
        clock, eng = make()
        eng.set_time(parse_time("1:30"))
        eng.start()
        self.assertEqual(eng.state, State.RUNNING)
        clock.advance(10)
        self.assertEqual(format_time(eng.remaining_cs()), "1:20:00")
        eng.pause()
        self.assertEqual(eng.state, State.PAUSED)
        frozen = eng.remaining_cs()
        clock.advance(500)
        self.assertEqual(eng.remaining_cs(), frozen)
        self.assertFalse(eng.tick())
        eng.resume()
        clock.advance(20)
        self.assertEqual(format_time(eng.remaining_cs()), "1:00:00")

    # caso 8
    def test_reset_restores_configured_time_without_starting(self):
        clock, eng = make()
        eng.set_time(parse_time("2:00"))
        eng.start()
        clock.advance(45.5)
        eng.reset()
        self.assertEqual(eng.state, State.CONFIGURED)
        self.assertEqual(format_time(eng.remaining_cs()), "2:00:00")
        clock.advance(10)
        eng.tick()
        self.assertEqual(format_time(eng.remaining_cs()), "2:00:00")

    # casos 9 e 11
    def test_complete_never_negative_and_stays_until_user_acts(self):
        clock, eng = make()
        eng.set_time(parse_time("0:05"))
        eng.start()
        clock.advance(4.99)
        self.assertFalse(eng.tick())
        self.assertEqual(eng.state, State.RUNNING)
        clock.advance(0.02)
        self.assertTrue(eng.tick())
        self.assertEqual(eng.state, State.COMPLETE)
        self.assertEqual(eng.remaining_cs(), 0)
        clock.advance(1000)
        self.assertFalse(eng.tick())
        self.assertEqual(eng.state, State.COMPLETE)   # alerta permanece
        self.assertEqual(eng.remaining_cs(), 0)       # nunca negativo

    def test_dismiss_and_restart_after_complete(self):
        clock, eng = make()
        eng.set_time(parse_time("0:02"))
        eng.start()
        clock.advance(3)
        eng.tick()
        self.assertTrue(eng.dismiss())
        self.assertEqual(eng.state, State.CONFIGURED)
        self.assertEqual(format_time(eng.remaining_cs()), "0:02:00")
        eng.start()
        clock.advance(3)
        self.assertTrue(eng.tick())

    def test_set_blocked_while_running_allowed_when_paused_or_stopped(self):
        clock, eng = make()
        eng.set_time(parse_time("1:00"))
        eng.start()
        with self.assertRaises(EngineError):
            eng.set_time(parse_time("2:00"))
        eng.pause()
        eng.set_time(parse_time("2:00"))
        self.assertEqual(eng.state, State.CONFIGURED)
        eng.start()
        eng.stop()
        self.assertEqual(eng.state, State.STANDBY)
        self.assertEqual(eng.remaining_cs(), 0)
        eng.set_time(parse_time("0:10:50"))
        self.assertEqual(format_time(eng.remaining_cs()), "0:10:50")

    def test_pause_after_deadline_completes_instead_of_going_negative(self):
        clock, eng = make()
        eng.set_time(parse_time("0:01"))
        eng.start()
        clock.advance(5)
        with self.assertRaises(EngineError):
            eng.pause()
        self.assertEqual(eng.state, State.COMPLETE)

    # caso 16: precisão independente da cadência da interface
    def test_precision_with_irregular_ticks(self):
        clock, eng = make()
        eng.set_time(parse_time("1:00"))
        eng.start()
        rng = random.Random(7)
        elapsed = 0.0
        for _ in range(500):                  # "frames" com atrasos irregulares (até 80 ms)
            dt = rng.uniform(0.001, 0.08)
            clock.advance(dt)
            elapsed += dt
            eng.tick()
        exact_ns = 60 * SEC - int(round(elapsed * SEC))
        # a diferença para o valor exato é só o arredondamento de 1 centésimo
        self.assertLess(abs(eng.remaining_cs() - exact_ns / NS_PER_CS), 1.01)
        # frame lento (500 ms de travamento) não deixa a contagem atrasada
        before = eng.remaining_ns()
        clock.advance(0.5)
        self.assertEqual(before - eng.remaining_ns(), int(0.5 * SEC))

    def test_pause_resume_cycles_do_not_drift(self):
        clock, eng = make()
        eng.set_time(parse_time("10:00"))
        eng.start()
        for _ in range(100):
            clock.advance(0.123)
            eng.pause()
            clock.advance(7)            # tempo parado não conta
            eng.resume()
        self.assertEqual(eng.remaining_ns(), 600 * SEC - 100 * int(0.123 * SEC))


class ParseTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(parse_time("5:30"), 33000)
        self.assertEqual(parse_time("1:25:50"), 8550)
        self.assertEqual(parse_time("0:10:50"), 1050)
        self.assertEqual(parse_time("120:00"), 720000)    # > 59 minutos
        self.assertEqual(parse_time("0:00:01"), 1)

    def test_invalid(self):
        for bad in ["", "abc", "5", "5:3", "5:75", "1:25:5", "1:25:100", "1:2:3:4",
                    ":30", "5:", "-1:30", "1:-30", "1.5:30", "１:30", "10000:00", "5:30:xx"]:
            with self.subTest(bad=bad), self.assertRaises(TimeFormatError):
                parse_time(bad)


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.clock, self.eng = make()
        self.exited = False
        self.top = True
        self.proc = CommandProcessor(self.eng, on_top=self._on_top, on_exit=self._exit)

    def _on_top(self, value):
        self.top = (not self.top) if value is None else value
        return self.top

    def _exit(self):
        self.exited = True

    def test_full_flow_and_messages(self):
        r = self.proc.execute("set 1:30")
        self.assertTrue(r.ok)
        self.assertIn("TIMER CONFIGURED", r.lines[0])
        self.assertEqual(self.proc.execute("start").lines, ["COUNTDOWN STARTED"])
        self.assertEqual(self.proc.execute("pause").lines, ["COUNTDOWN PAUSED"])
        self.assertEqual(self.proc.execute("resume").lines, ["COUNTDOWN RESUMED"])
        self.assertEqual(self.proc.execute("reset").lines, ["TIMER RESET"])
        self.assertEqual(self.eng.state, State.CONFIGURED)
        self.assertTrue(self.proc.execute("help").ok)

    def test_case_insensitive_and_whitespace(self):
        self.assertTrue(self.proc.execute("   SET   5:30  ").ok)
        self.assertTrue(self.proc.execute("StArT").ok)

    def test_invalid_time_message(self):
        r = self.proc.execute("set 5:75")
        self.assertFalse(r.ok)
        r = self.proc.execute("set banana")
        self.assertEqual(r.lines, ["INVALID TIME FORMAT"])
        self.assertEqual(self.eng.state, State.STANDBY)

    def test_start_with_zero_time_refused(self):
        r = self.proc.execute("start")
        self.assertFalse(r.ok)
        self.assertEqual(self.eng.state, State.STANDBY)

    def test_set_while_running_refused(self):
        self.proc.execute("set 1:00")
        self.proc.execute("start")
        r = self.proc.execute("set 2:00")
        self.assertFalse(r.ok)
        self.assertEqual(self.eng.configured_cs, 6000)

    # caso 12: comandos inválidos nunca derrubam o programa
    def test_garbage_never_raises(self):
        rng = random.Random(1)
        alphabet = "abcdefghijklmnopqrstuvwxyz0123456789:;-_ \t\x00\n!@#$%çãé日本"
        for _ in range(3000):
            text = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 24)))
            res = self.proc.execute(text)
            self.assertIsNotNone(res)
        for text in ["set", "set a b", "start now", "top maybe", "top on off", "💥"]:
            self.assertIsNotNone(self.proc.execute(text))

    def test_extras(self):
        self.assertEqual(self.proc.execute("top off").lines, ["ALWAYS ON TOP: OFF"])
        self.assertEqual(self.proc.execute("top").lines, ["ALWAYS ON TOP: ON"])
        self.assertTrue(self.proc.execute("clear").clear)
        self.proc.execute("exit")
        self.assertTrue(self.exited)


if __name__ == "__main__":
    unittest.main()
