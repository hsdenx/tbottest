"""
Unit tests for tbottest/tc/can.py.

sudo_exec0/get_lines/_default_can_devices/board_setup_can are pure
exec0()-driven logic, tested via a FakeLinuxShell that just records
calls. lnx_can_write_dump_compare()'s candump-output comparison logic
is tested against canned "cat"/"wc" output through the same kind of
fake, routed by command name (since tbot_start_thread() generates a
real random tid, exact command strings can't be pre-registered).

board_lnx_cangen() itself (the real hardware-timing loop, scp,
external check_cangen_output.py) is not covered here -- see
test_board_lnx_cangen_datetime_regression below for the one thing
that specifically needed a regression test out of it.
"""

import os

import pytest

from conftest import install_fake_initconfig, install_real_submodule, load_module

install_fake_initconfig()
install_real_submodule(
    "tbottest.tc.common",
    os.path.join(os.path.dirname(__file__), "..", "tbottest", "tc", "common.py"),
)

can = load_module(
    "tbottest_tc_can",
    os.path.join(os.path.dirname(__file__), "..", "tbottest", "tc", "can.py"),
)


class FakeLinuxShell:
    def __init__(self):
        self.commands = []
        self.dump_log = ""

    def exec0(self, *args):
        return self.exec(*args)[1]

    def exec(self, *args):
        key = tuple(str(a) for a in args)
        self.commands.append(key)
        cmd = key[0] if key else ""
        if cmd == "wc":
            return (0, "0")
        if cmd == "cat":
            path = key[1]
            if path.startswith("/tmp/thread_1_"):
                return (0, self.dump_log)
            return (0, "")
        return (0, "")

    def env(self, name):
        return "1234"


class TestSudoExec0:
    def test_without_sudo(self):
        lnx = FakeLinuxShell()
        can.sudo_exec0(lnx, False, "ifconfig", "can0", "up")
        assert lnx.commands == [("ifconfig", "can0", "up")]

    def test_with_sudo_prepends_sudo(self):
        lnx = FakeLinuxShell()
        can.sudo_exec0(lnx, True, "ifconfig", "can0", "up")
        assert lnx.commands == [("sudo", "ifconfig", "can0", "up")]


class TestGetLines:
    def test_parses_wc_output(self):
        class Lnx:
            def exec0(self, *args):
                return "42 /tmp/candump.log"

        assert can.get_lines(Lnx(), "/tmp/candump.log") == 42


class TestDefaultCanDevices:
    def test_both_none_use_defaults(self):
        candev, candevsend = can._default_can_devices(None, None)
        assert candev == ["can0", "can1"]
        assert candevsend == ["can0"]

    def test_explicit_values_kept(self):
        candev, candevsend = can._default_can_devices(["vcan0"], ["vcan0", "vcan1"])
        assert candev == ["vcan0"]
        assert candevsend == ["vcan0", "vcan1"]


class TestBoardSetupCan:
    def test_default_devices_used_when_none_given(self):
        lnx = FakeLinuxShell()
        can.board_setup_can(lnx)
        downs = [c for c in lnx.commands if c[:2] == ("ifconfig", "can0") and c[-1] == "down"]
        assert len(downs) == 1

    def test_sequence_is_down_then_configure_then_up(self):
        lnx = FakeLinuxShell()
        can.board_setup_can(lnx, candev=["can0"], br="250000", tql="100")
        assert lnx.commands == [
            ("ifconfig", "can0", "down"),
            ("ip", "link", "set", "can0", "type", "can", "bitrate", "250000"),
            ("ip", "link", "set", "can0", "txqueuelen", "100"),
            ("ifconfig", "can0", "up"),
        ]

    def test_usesudo_prefixes_every_command(self):
        lnx = FakeLinuxShell()
        can.board_setup_can(lnx, candev=["can0"], usesudo=True)
        assert all(c[0] == "sudo" for c in lnx.commands)


class TestLnxCanWriteDumpCompare:
    DATA = [
        {"dev": "can0", "data": "123#DEADBEEF", "res": "can0  123   [4]  DE AD BE EF"},
        {"dev": "can0", "data": "124#CAFE", "res": "can0  124   [2]  CA FE"},
    ]

    def test_matching_dump_does_not_raise(self):
        lab = FakeLinuxShell()
        lnxread = FakeLinuxShell()
        lnxread.dump_log = "\n".join(d["res"] for d in self.DATA)
        lnxsend = FakeLinuxShell()

        can.lnx_can_write_dump_compare(
            lab, lab, lnxsend, ["can0"], lnxread, ["can0"], "500000", "500", self.DATA
        )
        sent = [c for c in lnxsend.commands if c[0] == "cansend"]
        assert sent == [("cansend", "can0", "123#DEADBEEF"), ("cansend", "can0", "124#CAFE")]

    def test_interface_line_is_skipped_not_compared(self):
        lab = FakeLinuxShell()
        lnxread = FakeLinuxShell()
        lnxread.dump_log = "\n".join(
            ["interface can0", self.DATA[0]["res"], self.DATA[1]["res"]]
        )
        lnxsend = FakeLinuxShell()

        can.lnx_can_write_dump_compare(
            lab, lab, lnxsend, ["can0"], lnxread, ["can0"], "500000", "500", self.DATA
        )  # must not raise

    def test_mismatch_raises(self):
        lab = FakeLinuxShell()
        lnxread = FakeLinuxShell()
        lnxread.dump_log = "\n".join(["wrong line", self.DATA[1]["res"]])
        lnxsend = FakeLinuxShell()

        with pytest.raises(RuntimeError, match="candump errors"):
            can.lnx_can_write_dump_compare(
                lab, lab, lnxsend, ["can0"], lnxread, ["can0"], "500000", "500", self.DATA
            )

    def test_lab_equal_to_send_and_read_uses_sudo_for_both(self):
        lab = FakeLinuxShell()
        lab.dump_log = "\n".join(d["res"] for d in self.DATA)

        can.lnx_can_write_dump_compare(
            lab, lab, lab, ["can0"], lab, ["can0"], "500000", "500", self.DATA
        )
        sudo_setup_calls = [c for c in lab.commands if c[0] == "sudo" and c[1] == "ifconfig"]
        # 2 ifconfig calls (down, up) per board_setup_can(), once for
        # senddev and once for readdev
        assert len(sudo_setup_calls) == 4


class TestBoardLnxCangenDatetimeRegression:
    def test_datetime_now_does_not_raise_attributeerror(self):
        """
        Regression test: can.py used to `import datetime` and then
        call `datetime.now()` (the *module*, not the datetime.datetime
        class), which raises AttributeError on the very first call --
        board_lnx_cangen would never get past its first iteration.
        This only checks the import/usage is fixed, not the full
        hardware-timing workflow around it.
        """
        from datetime import datetime as real_datetime

        assert can.datetime is real_datetime
        can.datetime.now()  # must not raise AttributeError
