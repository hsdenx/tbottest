"""
Unit tests for tbottest/bdi2000.py: the BDI2000 shell waits for the BDI>
prompt on start, and exec() sends one command and returns what the BDI
printed before its next prompt.

FakeChannel stands in for the telnet channel: it records what was sent
and answers read_until_prompt() with prepared output. The bits of tbot
the module needs beyond conftest's stubs (tbot.machine.shell, tbot.Re,
tbot.role.Role, log_event.command with ev.data) are set up here.
"""

import contextlib
import os
import re
import sys
import types

from conftest import load_module

tbot = sys.modules["tbot"]
tbot.Re = lambda pat, flags=0: re.compile(pat.encode() if isinstance(pat, str) else pat, flags)
tbot.role.Role = type("Role", (), {})


class _Event:
    def __init__(self):
        self.data = {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


tbot.log_event = types.SimpleNamespace(command=lambda *a, **kw: _Event())

shell_mod = types.ModuleType("tbot.machine.shell")
shell_mod.Shell = type("Shell", (), {})
sys.modules["tbot.machine.shell"] = shell_mod
sys.modules["tbot.machine"].shell = shell_mod

bdi2000 = load_module(
    "tbottest_bdi2000",
    os.path.join(os.path.dirname(__file__), "..", "tbottest", "bdi2000.py"),
)


class FakeChannel:
    def __init__(self, answers=()):
        self.sent = []
        self.answers = list(answers)
        self.prompt = None
        self.timeouts = []

    def sendline(self, s=""):
        self.sent.append(s)

    @contextlib.contextmanager
    def with_prompt(self, prompt):
        old, self.prompt = self.prompt, prompt
        try:
            yield
        finally:
            self.prompt = old

    @contextlib.contextmanager
    def with_stream(self, ev, show_prompt=True):
        yield

    def read_until_prompt(self, timeout=None):
        assert self.prompt is not None, "read without a prompt set"
        self.timeouts.append(timeout)
        return self.answers.pop(0) if self.answers else ""


class FakeBDI(bdi2000.BDI2000Shell):
    name = "bdi2000"

    def __init__(self, ch):
        self.ch = ch


def test_init_shell_waits_for_the_prompt():
    ch = FakeChannel()
    bdi = FakeBDI(ch)
    with bdi._init_shell():
        assert ch.sent == [""]
        assert ch.prompt is bdi2000.BDI2000_PROMPT
        assert ch.timeouts == [10]
    assert ch.prompt is None


def test_exec_sends_one_command_and_returns_its_output():
    ch = FakeChannel(answers=["", "- TARGET: processing reset request\n"])
    bdi = FakeBDI(ch)
    with bdi._init_shell():
        out = bdi.exec("reset", "run")

    assert ch.sent == ["", "reset run"]
    assert out == "- TARGET: processing reset request\n"


def test_prompt_matches_with_and_without_blank():
    for text in (b"\nBDI>", b"\nBDI> "):
        m = bdi2000.BDI2000_PROMPT.search(text)
        assert m is not None and m.end() == len(text)
    assert bdi2000.BDI2000_PROMPT.search(b"telnet> ") is None


INFO_WAITING = "- TARGET: waiting for target Vcc\n"
INFO_DEBUG = "Target state      : debug mode\nDebug entry cause : HRESET\n"


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, s):
        self.now += s


def _bdi_with_info(answers, monkeypatch):
    ch = FakeChannel()
    bdi = FakeBDI(ch)
    replies = list(answers)

    def fake_exec(*args):
        ch.sent.append(" ".join(args))
        return replies.pop(0) if replies else replies_last[0]

    replies_last = [answers[-1]]
    monkeypatch.setattr(bdi, "exec", fake_exec)
    clock = FakeClock()
    monkeypatch.setattr(bdi2000.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(bdi2000.time, "sleep", clock.sleep)
    return bdi, ch, clock


def test_target_state_is_read_from_info(monkeypatch):
    bdi, ch, _ = _bdi_with_info([INFO_DEBUG], monkeypatch)
    assert bdi.target_state() == "debug mode"
    assert ch.sent == ["info"]


def test_target_state_is_empty_while_waiting_for_vcc(monkeypatch):
    bdi, _, _ = _bdi_with_info([INFO_WAITING], monkeypatch)
    assert bdi.target_state() == ""


def test_wait_target_state_polls_until_reached(monkeypatch):
    bdi, ch, clock = _bdi_with_info([INFO_WAITING, INFO_WAITING, INFO_DEBUG], monkeypatch)
    bdi.wait_target_state("debug mode", timeout=10, interval=0.5)
    assert ch.sent == ["info", "info", "info"]
    assert clock.now == 1.0


def test_wait_target_state_times_out(monkeypatch):
    bdi, ch, clock = _bdi_with_info([INFO_WAITING], monkeypatch)
    import pytest

    with pytest.raises(TimeoutError):
        bdi.wait_target_state("debug mode", timeout=2, interval=0.5)
    assert clock.now >= 2
    assert len(ch.sent) == 5
