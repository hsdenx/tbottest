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

if not hasattr(tbot, "error"):
    tbot.error = types.SimpleNamespace()
if not hasattr(tbot.error, "ChannelClosedError"):
    tbot.error.ChannelClosedError = type("ChannelClosedError", (Exception,), {})

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
        self.log = []
        self.expect_text = ""

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
        self.log.append(("prompt", self.sent[-1] if self.sent else None))
        return self.answers.pop(0) if self.answers else ""

    def expect(self, patterns, timeout=None):
        self.log.append(("expect", tuple(patterns)))
        text = self.expect_text
        for i, pat in enumerate(patterns):
            idx = text.find(pat)
            if idx != -1:
                return types.SimpleNamespace(
                    i=i, match=pat, before=text[:idx], after=text[idx + len(pat):]
                )
        raise TimeoutError("pattern not in expect_text")

    def read(self, n=-1, timeout=None):
        self.log.append(("read",))
        raise TimeoutError()


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


RESET_STARTED = (
    "reset\n- TARGET: processing user reset request\n"
    "- TARGET: resetting target passed\n"
    "- TARGET: processing target init list ...."
)


def test_reset_waits_for_the_end_of_the_init_list():
    ch = FakeChannel(answers=[RESET_STARTED, "", "Breakpoint identification is 0"])
    ch.expect_text = "\n- TARGET: processing target init list passed\n"
    bdi = FakeBDI(ch)
    with ch.with_prompt(bdi2000.BDI2000_PROMPT):
        out = bdi.exec("reset")
        assert "init list passed" in out
        bdi.exec("bi", "0xc0600980")
    # the next command goes out only after the wait and a fresh prompt
    assert ch.sent == ["reset", "", "bi 0xc0600980"]
    wait = ch.log.index(("expect", ("init list passed", "init list failed")))
    fresh = ch.log.index(("prompt", ""))
    bi = ch.log.index(("prompt", "bi 0xc0600980"))
    assert wait < fresh < bi


def test_no_wait_when_the_init_list_already_passed():
    ch = FakeChannel(answers=[RESET_STARTED + "\n- TARGET: processing target init list passed"])
    bdi = FakeBDI(ch)
    with ch.with_prompt(bdi2000.BDI2000_PROMPT):
        bdi.exec("reset")
    assert not [e for e in ch.log if e[0] == "expect"]
    assert ch.sent == ["reset"]


def test_failed_init_list_raises():
    ch = FakeChannel(answers=[RESET_STARTED, ""])
    ch.expect_text = "\n- TARGET: processing target init list failed\n"
    bdi = FakeBDI(ch)
    with ch.with_prompt(bdi2000.BDI2000_PROMPT):
        try:
            bdi.exec("reset")
        except RuntimeError as e:
            assert "init list failed" in str(e)
        else:
            raise AssertionError("no RuntimeError on a failed init list")


LOAD_CMD = "load 0x00100000 amc/20261001/musl/u-boot-ram.bin bin"
LOAD_STARTED = "Loading amc/20261001/musl/u-boot-ram.bin , please wait ....\n"


def test_failed_load_raises_and_stops_the_command_list():
    ch = FakeChannel(answers=[LOAD_STARTED + "# Cannot open file on host\n", ""])
    bdi = FakeBDI(ch)
    with ch.with_prompt(bdi2000.BDI2000_PROMPT):
        try:
            for cmd in (LOAD_CMD, "go 0x00100100"):
                bdi.exec(cmd)
        except RuntimeError as e:
            assert "Cannot open file on host" in str(e)
            assert LOAD_CMD in str(e)
        else:
            raise AssertionError("no RuntimeError on a failed load")
    # go is never sent
    assert ch.sent == [LOAD_CMD]


def test_successful_load_returns_its_output():
    out = LOAD_STARTED + "Loading program file passed\n"
    ch = FakeChannel(answers=[out])
    bdi = FakeBDI(ch)
    with ch.with_prompt(bdi2000.BDI2000_PROMPT):
        assert bdi.exec(LOAD_CMD) == out


def test_load_without_passed_raises():
    # an error message not in BDI_ERRORS: the missing "passed" line counts
    ch = FakeChannel(answers=[LOAD_STARTED + "# some other error\n"])
    bdi = FakeBDI(ch)
    with ch.with_prompt(bdi2000.BDI2000_PROMPT):
        try:
            bdi.exec(LOAD_CMD)
        except RuntimeError as e:
            assert "some other error" in str(e)
        else:
            raise AssertionError("no RuntimeError on a load without passed")


def test_other_commands_need_no_passed_line():
    ch = FakeChannel(answers=["- TARGET: processing reset request\n"])
    bdi = FakeBDI(ch)
    with ch.with_prompt(bdi2000.BDI2000_PROMPT):
        bdi.exec("reset", "run")


def test_commands_without_init_list_do_not_wait():
    ch = FakeChannel(answers=["Breakpoint identification is 0"])
    bdi = FakeBDI(ch)
    with ch.with_prompt(bdi2000.BDI2000_PROMPT):
        bdi.exec("bi", "0xc0600980")
    assert not [e for e in ch.log if e[0] in ("expect", "read")]


CONFIG_OUT = (
    "    BDI Firmware: 1.18\n"
    "    BDI MAC     : 00-0c-01-93-19-70\n"
    "    BDI IP      : 192.168.3.101\n"
    "    BDI Subnet  : 255.255.255.255\n"
    "    BDI Gateway : 255.255.255.255\n"
    "    Config IP   : 192.168.3.1\n"
    "    Config File : {}\n"
)
CFG = "amc/bdi/tqm855-AMC.cfg"
CFG_NOWDT = "amc/bdi/tqm855-AMC-nowdt.cfg"


def test_split_configname_takes_the_entry_out():
    cfg, cmds = bdi2000.split_configname(["reset", "configname:" + CFG_NOWDT, "go 0x40000100"])
    assert cfg == CFG_NOWDT
    assert cmds == ["reset", "go 0x40000100"]


def test_split_configname_without_entry():
    assert bdi2000.split_configname(["reset run"]) == (None, ["reset run"])


def test_split_configname_rejects_two_entries_and_an_empty_one():
    import pytest

    with pytest.raises(RuntimeError):
        bdi2000.split_configname(["configname:" + CFG, "configname:" + CFG_NOWDT])
    with pytest.raises(RuntimeError):
        bdi2000.split_configname(["configname:", "reset"])


def test_config_reads_file_and_host(monkeypatch):
    bdi, ch, _ = _bdi_with_info([CONFIG_OUT.format(CFG)], monkeypatch)
    assert bdi.config() == (CFG, "192.168.3.1")
    assert ch.sent == ["config"]


def test_config_without_file_raises(monkeypatch):
    import pytest

    bdi, _, _ = _bdi_with_info(["unknown command\n"], monkeypatch)
    with pytest.raises(RuntimeError):
        bdi.config()


UPDATED = (
    b"config amc/bdi/tqm855-AMC.cfg 192.168.3.1\r\n"
    b"Updating configuration passed. Booting ....."
)


class BootChannel(FakeChannel):
    """
    after config <file> <host>: returns ``chunks`` one per read, then
    closes; with close=False it stays open and only times out
    """

    def __init__(self, chunks, close=True):
        super().__init__()
        self.chunks = list(chunks)
        self.close = close
        self.clock = None

    def read(self, n=-1, timeout=None):
        self.log.append(("read",))
        if self.chunks:
            return self.chunks.pop(0)
        if self.close:
            raise tbot.error.ChannelClosedError()
        # a read that times out takes its time
        if self.clock is not None and timeout is not None:
            self.clock.now += timeout
        raise TimeoutError()


def _boot_bdi(ch, monkeypatch, current=CFG):
    bdi = FakeBDI(ch)

    def fake_exec(*args):
        ch.sent.append(" ".join(args))
        return CONFIG_OUT.format(current) if args == ("config",) else ""

    monkeypatch.setattr(bdi, "exec", fake_exec)
    clock = FakeClock()
    monkeypatch.setattr(bdi2000.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(bdi2000.time, "sleep", clock.sleep)
    ch.clock = clock
    return bdi, clock


def test_boot_config_sets_the_file_with_the_current_host(monkeypatch):
    ch = BootChannel([UPDATED[:20], UPDATED[20:]])
    bdi, _ = _boot_bdi(ch, monkeypatch)
    bdi.boot_config(CFG_NOWDT)
    # no boot of its own: config makes the BDI boot
    assert ch.sent == ["config", "config " + CFG_NOWDT + " 192.168.3.1"]
    assert ch.log.count(("read",)) == 3


def test_boot_config_raises_if_the_bdi_shows_its_prompt_again(monkeypatch):
    import pytest

    ch = BootChannel([b"config foo.cfg 192.168.3.1\r\n# TFTP error\r\nBDI>"], close=False)
    bdi, _ = _boot_bdi(ch, monkeypatch)
    with pytest.raises(RuntimeError):
        bdi.boot_config("foo.cfg")


def test_boot_config_raises_if_closed_without_update(monkeypatch):
    import pytest

    ch = BootChannel([b"config foo.cfg 192.168.3.1\r\n"])
    bdi, _ = _boot_bdi(ch, monkeypatch)
    with pytest.raises(RuntimeError):
        bdi.boot_config("foo.cfg")


def test_boot_config_times_out_if_the_session_stays_open(monkeypatch):
    import pytest

    ch = BootChannel([], close=False)
    bdi, clock = _boot_bdi(ch, monkeypatch)
    with pytest.raises(TimeoutError):
        bdi.boot_config(CFG_NOWDT, timeout=5)
    assert clock.now >= 5


class FakeBDIConfig:
    """what ensure_config() needs from a BDI2000 machine"""

    def __init__(self, world):
        self.world = world

    def config(self):
        return self.world["cfg"], "192.168.3.1"

    def boot_config(self, cfgfile, timeout=30.0):
        self.world["booted"].append(cfgfile)
        self.world["cfg"] = self.world.get("cfg_after_boot", cfgfile)


def _ensure(monkeypatch, cfg, refused=0, cfg_after_boot=None, timeout=30.0):
    world = {"cfg": cfg, "booted": [], "requests": 0, "refused": refused}
    if cfg_after_boot is not None:
        world["cfg_after_boot"] = cfg_after_boot

    @contextlib.contextmanager
    def request():
        world["requests"] += 1
        if world["booted"] and world["refused"] > 0:
            world["refused"] -= 1
            raise RuntimeError("telnet connection refused")
        yield FakeBDIConfig(world)

    clock = FakeClock()
    monkeypatch.setattr(bdi2000.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(bdi2000.time, "sleep", clock.sleep)
    return world, clock, request


def test_ensure_config_keeps_the_bdi_with_the_right_file(monkeypatch):
    world, _, request = _ensure(monkeypatch, CFG_NOWDT)
    assert bdi2000.ensure_config(request, CFG_NOWDT) is False
    assert world["booted"] == []
    assert world["requests"] == 1


def test_ensure_config_boots_and_reconnects(monkeypatch):
    world, clock, request = _ensure(monkeypatch, CFG, refused=3)
    assert bdi2000.ensure_config(request, CFG_NOWDT, interval=2.0) is True
    assert world["booted"] == [CFG_NOWDT]
    # the first request, three refused ones, the one that answers
    assert world["requests"] == 5
    assert clock.now == 6.0


def test_ensure_config_times_out_if_the_bdi_does_not_come_back(monkeypatch):
    import pytest

    world, clock, request = _ensure(monkeypatch, CFG, refused=1000)
    with pytest.raises(TimeoutError):
        bdi2000.ensure_config(request, CFG_NOWDT, timeout=10, interval=2.0)
    assert clock.now >= 10


def test_ensure_config_raises_if_the_bdi_kept_the_old_file(monkeypatch):
    import pytest

    _, _, request = _ensure(monkeypatch, CFG, cfg_after_boot=CFG)
    with pytest.raises(RuntimeError):
        bdi2000.ensure_config(request, CFG_NOWDT)
