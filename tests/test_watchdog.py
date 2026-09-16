"""
Unit tests for tbottest/tc/watchdog.py.

What a run on hardware proves is the happy path: the service is stopped,
the board resets, the reason is the one expected. What it does not reach
are the paths where the testcase has to say no, and those are the ones that
matter, because a watchdog testcase that quietly passes is worse than none
at all.

So the machines are faked here, down to the channel, and what is checked is
what the testcase decides and what it sends: that it refuses to stop
anything when nothing is feeding the watchdog, that it really sends the
stop on the happy path, that it asks for a bounded wait rather than an
endless one, and that it puts the nopoweroff flag back the way it found it.
"""

import os
import sys

from conftest import load_module

# No install_tbot_stubs() here: conftest calls it once when it is loaded,
# and calling it again builds fresh stub modules while the test modules
# imported before this one still point at the old ones. Their "nopoweroff"
# checks would then read a different tbot.flags than the tests setting it.
watchdog = load_module(
    "tbottest_tc_watchdog",
    os.path.join(os.path.dirname(__file__), "..", "tbottest", "tc", "watchdog.py"),
)

tbot = sys.modules["tbot"]

SERVICE = "feeder"
DEVICE = "/dev/watchdog"

# what "systemctl show -p MainPID --value <service>" and the readlink loop
# are asked, spelled the way the module spells them
PID_CMD = ("systemctl", "show", "-p", "MainPID", "--value", SERVICE)


def fd_cmd(pid):
    return ("sh", "-c", f"for f in /proc/{pid}/fd/*; do readlink $f; done")


class FakeExecMachine:
    """records every exec() and answers from a table keyed by the argv tuple"""

    def __init__(self, answers=None):
        self.calls = []
        self.answers = answers or {}

    def exec(self, *args):
        self.calls.append(args)
        return self.answers.get(args, (0, ""))

    def exec0(self, *args):
        rc, out = self.exec(*args)
        assert rc == 0, f"{args} failed"
        return out


class FakeChannel:
    def __init__(self):
        self.lines = []

    def sendline(self, line):
        self.lines.append(line)


class FakeLinux(FakeExecMachine):
    instances = []

    def __init__(self, ub):
        super().__init__(self.answers_for_next.pop(0) if self.answers_for_next else {})
        self.ub = ub
        self.ch = FakeChannel()
        FakeLinux.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeUBoot:
    boot_timeout = None
    instances = []
    bootlog = "Reset reason: ESM\n"

    def __init__(self, board):
        self.board = board
        FakeUBoot.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeCtx:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def request(self, role):
        return f"requested:{role}"

    def get_machine_class(self, role):
        if role is tbot.role.BoardUBoot:
            return FakeUBoot
        if role is tbot.role.BoardLinux:
            return FakeLinux
        raise AssertionError(f"unexpected role {role}")


def run(monkeypatch, linux_answers, check=None, **kwargs):
    """
    call the testcase with faked machines

    :param linux_answers: one answer table per linux machine the testcase
        builds, in the order it builds them
    """
    FakeLinux.instances = []
    FakeUBoot.instances = []
    FakeLinux.answers_for_next = list(linux_answers)
    monkeypatch.setattr(tbot, "ctx", lambda: FakeCtx())

    return watchdog.board_lnx_watchdog_bites(
        service=SERVICE, device=DEVICE, check=check, **kwargs
    )


def running(pid="173", holds=DEVICE):
    """answer table for a linux where the service runs and holds the device"""
    return {
        PID_CMD: (0, f"{pid}\n"),
        fd_cmd(pid): (0, f"/dev/null\nsocket:[6489]\n{holds}\n"),
    }


class TestServiceMainPid:
    def test_reports_the_pid(self):
        lnx = FakeExecMachine({PID_CMD: (0, "173\n")})
        assert watchdog.lnx_service_main_pid(lnx, SERVICE) == "173"

    def test_zero_means_not_running(self):
        # systemd answers 0 rather than failing for a stopped unit
        lnx = FakeExecMachine({PID_CMD: (0, "0\n")})
        assert watchdog.lnx_service_main_pid(lnx, SERVICE) == ""

    def test_failed_command_means_not_running(self):
        lnx = FakeExecMachine({PID_CMD: (1, "Unit not found\n")})
        assert watchdog.lnx_service_main_pid(lnx, SERVICE) == ""


class TestPidHolds:
    def test_finds_the_device(self):
        lnx = FakeExecMachine({fd_cmd("7"): (0, "/dev/null\n/dev/watchdog\n")})
        assert watchdog.lnx_pid_holds(lnx, "7", DEVICE) is True

    def test_missing_device_is_not_found(self):
        lnx = FakeExecMachine({fd_cmd("7"): (0, "/dev/null\nsocket:[1]\n")})
        assert watchdog.lnx_pid_holds(lnx, "7", DEVICE) is False

    def test_another_watchdog_does_not_count(self):
        # a second watchdog would be a different device, and holding it
        # says nothing about the one under test
        lnx = FakeExecMachine({fd_cmd("7"): (0, "/dev/watchdog0\n")})
        assert watchdog.lnx_pid_holds(lnx, "7", DEVICE) is False

    def test_failed_command_is_not_found(self):
        lnx = FakeExecMachine({fd_cmd("7"): (1, "")})
        assert watchdog.lnx_pid_holds(lnx, "7", DEVICE) is False


class TestWatchdogBites:
    def test_needs_a_service(self):
        try:
            watchdog.board_lnx_watchdog_bites()
        except RuntimeError:
            return
        raise AssertionError("a missing service name has to be refused")

    def test_passes_when_the_board_comes_back(self, monkeypatch):
        seen = []
        assert run(
            monkeypatch,
            [running(), running(pid="175")],
            check=lambda ub: seen.append(ub) or True,
        ) is True

        # the stop went out, and to the right service
        assert FakeLinux.instances[0].ch.lines == [f"systemctl stop {SERVICE}"]
        # check() got the machine that came up after the reset
        assert seen == [FakeUBoot.instances[1]]

    def test_refuses_when_nothing_feeds_the_watchdog(self, monkeypatch):
        lnx_stopped = {PID_CMD: (0, "0\n")}

        assert run(monkeypatch, [lnx_stopped]) is False

        # and above all it did not stop anything or wait for a reset that
        # was never going to come
        assert FakeLinux.instances[0].ch.lines == []
        assert len(FakeUBoot.instances) == 1

    def test_refuses_when_the_service_does_not_hold_the_device(self, monkeypatch):
        # the service runs, but something else owns the watchdog, so
        # stopping it would prove nothing
        assert run(monkeypatch, [running(holds="/dev/null")]) is False
        assert FakeLinux.instances[0].ch.lines == []
        assert len(FakeUBoot.instances) == 1

    def test_a_failing_check_fails_the_run(self, monkeypatch):
        assert run(
            monkeypatch, [running(), running()], check=lambda ub: False
        ) is False

    def test_fails_when_the_service_does_not_come_back(self, monkeypatch):
        assert run(monkeypatch, [running(), {PID_CMD: (0, "0\n")}]) is False

    def test_waits_with_a_deadline(self, monkeypatch):
        run(monkeypatch, [running(), running()], boot_timeout=42)

        # the first machine catches the boot that is already happening, the
        # second one waits for a reset that may never come and must give up
        assert FakeUBoot.instances[0].boot_timeout is None
        assert FakeUBoot.instances[1].boot_timeout == 42

    def test_holds_the_power_and_puts_the_flag_back(self, monkeypatch):
        tbot.flags.discard("nopoweroff")
        flags_during = []

        run(
            monkeypatch,
            [running(), running()],
            check=lambda ub: flags_during.append("nopoweroff" in tbot.flags) or True,
        )

        assert flags_during == [True]
        assert "nopoweroff" not in tbot.flags

    def test_leaves_a_flag_it_did_not_set(self, monkeypatch):
        tbot.flags.add("nopoweroff")
        try:
            run(monkeypatch, [running(), running()])
            assert "nopoweroff" in tbot.flags
        finally:
            tbot.flags.discard("nopoweroff")
