"""
Unit tests for tbottest/tc/rs485.py.

_configure_serial()/_rs485_send_and_compare() are exec0()/exec()-
driven logic, tested against a FakeHost that records calls and
returns a per-instance canned "cmp" exit status (lnx_create_random()/
tbot_copy_file_to_board() are the real tc/common.py functions, loaded
via install_real_submodule so rs485.py's own import resolves them --
tbot_copy_file_to_board() reads lab.ethdevices[boardname][ethdevice],
so FakeHost provides that too).

board_lnx_rs485()'s required-argument validation and its overall
lab<->board direction handling (_rs485_send_and_compare()'s `if src
is lab` branch) are covered end to end; the full byte-comparison
workflow was additionally verified by running the pre-refactor and
post-refactor rs485.py against the same fakes and diffing the exact
exec()/exec0() command sequences (see conversation history), since
this dedup only extracts existing per-direction logic rather than
changing it.
"""

import os

import pytest

from conftest import install_fake_initconfig, install_real_submodule, load_module

install_fake_initconfig(boardname="testboard")
install_real_submodule(
    "tbottest.tc.common",
    os.path.join(os.path.dirname(__file__), "..", "tbottest", "tc", "common.py"),
)

rs485 = load_module(
    "tbottest_tc_rs485",
    os.path.join(os.path.dirname(__file__), "..", "tbottest", "tc", "rs485.py"),
)


class FakePath(str):
    def __truediv__(self, other):
        return FakePath(f"{self}/{other}")

    def _local_str(self):
        return str(self)


class FakeHost:
    def __init__(self, name, cmp_ok=True):
        self.name = name
        self.commands = []
        self.cmp_ok = cmp_ok
        self.ethdevices = {"testboard": {"eth0": {"ipaddr": "1.2.3.4"}}}

    def tmpdir(self):
        return FakePath(f"/tmp/{self.name}")

    def exec0(self, *args):
        key = tuple(str(a) for a in args)
        self.commands.append(("exec0", key))
        if key and key[0] == "cmp" and not self.cmp_ok:
            raise RuntimeError("cmp: files differ")
        return ""

    def exec(self, *args):
        key = tuple(str(a) for a in args)
        self.commands.append(("exec", key))
        return (0, "")

    def env(self, name):
        return "999"


class TestConfigureSerial:
    def test_exports_and_configures_device(self):
        host = FakeHost("lab")
        rs485._configure_serial(host, "/dev/ttyUSB0", "115200")
        assert host.commands[0] == ("exec0", ("export", "SERIAL_DEV=/dev/ttyUSB0"))
        stty_calls = [c for c in host.commands if c[1][0] == "stty"]
        assert len(stty_calls) == 2
        assert "115200" in stty_calls[0][1]


class TestRs485SendAndCompare:
    def test_lab_to_board_compares_on_board(self):
        lab = FakeHost("lab")
        lnx = FakeHost("lnx")
        rs485._rs485_send_and_compare(lab, lnx, lab, lnx, "eth0", "10", 0, "receive error")

        # comparison must run on the board (lnx), not the lab
        cmp_calls = [c for c in lnx.commands if c[1][0] == "cmp"]
        assert len(cmp_calls) == 1
        assert [c for c in lab.commands if c[1][0] == "cmp"] == []

    def test_lab_to_board_mismatch_raises_receive_error(self):
        lab = FakeHost("lab")
        lnx = FakeHost("lnx", cmp_ok=False)
        with pytest.raises(RuntimeError, match="receive error"):
            rs485._rs485_send_and_compare(lab, lnx, lab, lnx, "eth0", "10", 0, "receive error")

    def test_board_to_lab_compares_on_board(self):
        lab = FakeHost("lab")
        lnx = FakeHost("lnx")
        rs485._rs485_send_and_compare(lab, lnx, lnx, lab, "eth0", "10", 0, "send error")

        # tbot_copy_file_to_board always deposits onto lnx, so the
        # comparison must run there too even though tar==lab here
        cmp_calls = [c for c in lnx.commands if c[1][0] == "cmp"]
        assert len(cmp_calls) == 1

    def test_board_to_lab_mismatch_raises_send_error(self):
        lab = FakeHost("lab")
        lnx = FakeHost("lnx", cmp_ok=False)
        with pytest.raises(RuntimeError, match="send error"):
            rs485._rs485_send_and_compare(lab, lnx, lnx, lab, "eth0", "10", 0, "send error")

    def test_debug_dumps_extra_cat_calls(self):
        lab = FakeHost("lab")
        lnx = FakeHost("lnx")
        rs485._rs485_send_and_compare(lab, lnx, lab, lnx, "eth0", "10", 0, "receive error")
        no_debug_cats = len([c for c in lab.commands if c[1][0] == "cat"])

        lab2 = FakeHost("lab")
        lnx2 = FakeHost("lnx")
        rs485._rs485_send_and_compare(lab2, lnx2, lab2, lnx2, "eth0", "10", 1, "receive error")
        debug_cats = len([c for c in lab2.commands if c[1][0] == "cat"])

        assert debug_cats > no_debug_cats


class TestBoardLnxRs485RequiredArgs:
    @pytest.mark.parametrize(
        "missing_key,message",
        [
            ("ethdevice", "please configure ethdevice"),
            ("rs485labdev", "please configure rs485labdev"),
            ("rs485baud", "please configure rs485baud"),
            ("rs485boarddev", "please configure rs485boarddev"),
            ("rs485lengths", "please configure rs485lengths"),
        ],
    )
    def test_missing_required_arg_raises(self, missing_key, message):
        kwargs = {
            "ethdevice": "eth0",
            "rs485labdev": "/dev/labdev",
            "rs485baud": "115200",
            "rs485boarddev": ["/dev/ttymxc2"],
            "rs485lengths": ["10"],
        }
        kwargs[missing_key] = None
        with pytest.raises(RuntimeError, match=message):
            rs485.board_lnx_rs485(FakeHost("lab"), FakeHost("lnx"), **kwargs)


class TestBoardLnxRs485EndToEnd:
    def test_runs_both_directions_for_each_boarddev_and_length(self):
        lab = FakeHost("lab")
        lnx = FakeHost("lnx")
        rs485.board_lnx_rs485(
            lab,
            lnx,
            ethdevice="eth0",
            rs485labdev="/dev/labdev",
            rs485baud="115200",
            rs485boarddev=["/dev/ttymxc2"],
            rs485lengths=["10", "20"],
        )
        # 2 lengths x 2 directions = 4 cmp comparisons, all on the board
        cmp_calls = [c for c in lnx.commands if c[1][0] == "cmp"]
        assert len(cmp_calls) == 4
