"""
Unit tests for tbottest/tc/can.py.

get_lines/_default_can_devices/board_setup_can are pure
exec0()-driven logic, tested via a FakeLinuxShell that just records
calls. lnx_can_write_dump_compare()'s candump-output comparison logic
is tested against canned "cat"/"wc" output through the same kind of
fake, routed by command name (since tbot_start_thread() generates a
real random tid, exact command strings can't be pre-registered).

check_cangen_log() checks the candump log of board_lnx_cangen() in
Python, board_lnx_cangen() itself runs against a fake board that
answers wc and cat with a canned log.
"""

import inspect
import itertools
import os
import types

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


# a name of its own for every fake machine
FAKE_NAMES = itertools.count()


class FakeLinuxShell:
    """records the commands, logged in as root unless uid says otherwise"""

    def __init__(self, uid=0, versions=None):
        # lnx_sudo() caches its answer per machine name
        self.name = f"fake-linux-{next(FAKE_NAMES)}"
        self.commands = []
        self.dump_log = ""
        self.uid = uid
        # cmd_get_version(): command -> "impl:version", "notfound" or
        # missing for full:unknown
        self.versions = versions or {}

    def cmd_get_version(self, cmd):
        impl = self.versions.get(cmd, "full:unknown").split(":")[0]
        return types.SimpleNamespace(impl=impl, found=impl != "notfound")

    def test(self, *args):
        return self.exec(*args)[0] == 0

    def exec0(self, *args):
        return self.exec(*args)[1]

    def exec(self, *args):
        key = tuple(str(a) for a in args)
        self.commands.append(key)
        cmd = key[0] if key else ""
        if key == ("id", "-u"):
            return (0, f"{self.uid}\n")
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
        downs = [c for c in lnx.commands if c[:4] == ("ip", "link", "set", "can0") and c[-1] == "down"]
        assert len(downs) == 1

    def test_sequence_is_down_then_configure_then_up(self):
        lnx = FakeLinuxShell()
        can.board_setup_can(lnx, candev=["can0"], br="250000", tql="100")
        assert lnx.commands == [
            ("id", "-u"),
            ("ip", "link", "set", "can0", "down"),
            ("ip", "link", "set", "can0", "type", "can", "bitrate", "250000"),
            ("ip", "link", "set", "can0", "txqueuelen", "100"),
            ("ip", "link", "set", "can0", "up"),
        ]

    def test_not_root_prefixes_every_command_with_sudo(self):
        lnx = FakeLinuxShell(uid=1000)
        can.board_setup_can(lnx, candev=["can0"])
        assert lnx.commands[0] == ("id", "-u")
        assert len(lnx.commands) == 5
        assert all(c[0] == "sudo" for c in lnx.commands[1:])

    def test_root_without_sudo(self):
        lnx = FakeLinuxShell(uid=0)
        can.board_setup_can(lnx, candev=["can0"])
        assert not [c for c in lnx.commands if c[0] == "sudo"]


class TestLnxCanWriteDumpCompare:
    DATA = [
        {"dev": "can0", "data": "123#DEADBEEF", "res": "can0  123   [4]  DE AD BE EF"},
        {"dev": "can0", "data": "124#CAFE", "res": "can0  124   [2]  CA FE"},
    ]

    def test_matching_dump_does_not_raise(self):
        lnxread = FakeLinuxShell()
        lnxread.dump_log = "\n".join(d["res"] for d in self.DATA)
        lnxsend = FakeLinuxShell()

        can.lnx_can_write_dump_compare(
            lnxsend, ["can0"], lnxread, ["can0"], "500000", "500", self.DATA
        )
        sent = [c for c in lnxsend.commands if c[0] == "cansend"]
        assert sent == [("cansend", "can0", "123#DEADBEEF"), ("cansend", "can0", "124#CAFE")]

    def test_interface_line_is_skipped_not_compared(self):
        lnxread = FakeLinuxShell()
        lnxread.dump_log = "\n".join(
            ["interface can0", self.DATA[0]["res"], self.DATA[1]["res"]]
        )
        lnxsend = FakeLinuxShell()

        can.lnx_can_write_dump_compare(
            lnxsend, ["can0"], lnxread, ["can0"], "500000", "500", self.DATA
        )  # must not raise

    def test_mismatch_raises(self):
        lnxread = FakeLinuxShell()
        lnxread.dump_log = "\n".join(["wrong line", self.DATA[1]["res"]])
        lnxsend = FakeLinuxShell()

        with pytest.raises(RuntimeError, match="candump errors"):
            can.lnx_can_write_dump_compare(
                lnxsend, ["can0"], lnxread, ["can0"], "500000", "500", self.DATA
            )

    def test_not_root_uses_sudo_for_both(self):
        lab = FakeLinuxShell(uid=1000)
        lab.dump_log = "\n".join(d["res"] for d in self.DATA)

        can.lnx_can_write_dump_compare(
            lab, ["can0"], lab, ["can0"], "500000", "500", self.DATA
        )
        sudo_setup_calls = [
            c for c in lab.commands if c[:3] == ("sudo", "ip", "link") and c[-1] in ("down", "up")
        ]
        # 2 calls (down, up) per board_setup_can(), once for senddev and
        # once for readdev
        assert len(sudo_setup_calls) == 4


def cangen_log(frames, dllength, dev="can0", t0=1000.0, step=0.01):
    """the candump -L log of cangen -I i -L <dllength> -D i -n <frames>"""
    lines = []
    for n in range(frames):
        data = (n % 256**dllength).to_bytes(dllength, "little").hex().upper()
        lines.append(f"({t0 + n * step:.6f}) {dev} {n % 0x800:03X}#{data}")
    return "\n".join(lines) + "\n"


class TestCheckCangenLog:
    def test_matching_log(self):
        assert can.check_cangen_log(cangen_log(10, 8), 10, 8, "can0") == []

    def test_can_id_wraps_after_7ff(self):
        log = cangen_log(0x802, 2)
        assert "can0 7FF#" in log.splitlines()[0x7FF]
        assert "can0 000#" in log.splitlines()[0x800]
        assert can.check_cangen_log(log, 0x802, 2, "can0") == []

    def test_data_wraps_with_one_byte(self):
        # the counter of one data byte wraps after 255
        log = cangen_log(300, 1)
        assert log.splitlines()[256].endswith("#00")
        assert can.check_cangen_log(log, 300, 1, "can0") == []

    def test_missing_frame(self):
        lines = cangen_log(10, 8).splitlines()
        del lines[4]
        errors = can.check_cangen_log("\n".join(lines), 10, 8, "can0")
        assert errors[0] == "9 frames in the candump log, 10 sent"
        assert any("line 5 has CAN ID 0x5, expected 0x4" in e for e in errors)

    def test_wrong_data_length(self):
        errors = can.check_cangen_log(cangen_log(3, 4), 3, 8, "can0")
        assert errors == [f"line {n} has 4 data bytes, expected 8" for n in (1, 2, 3)]

    def test_wrong_interface(self):
        errors = can.check_cangen_log(cangen_log(2, 8, dev="can1"), 2, 8, "can0")
        assert len(errors) == 2
        assert "from can1, not can0" in errors[0]

    def test_wrong_data(self):
        log = cangen_log(3, 2).replace("002#0200", "002#0300")
        errors = can.check_cangen_log(log, 3, 2, "can0")
        assert errors == ["line 3 has data 3, expected 2"]

    def test_error_message_in_log(self):
        log = cangen_log(2, 8) + "read: Network is down\n"
        errors = can.check_cangen_log(log, 2, 8, "can0")
        assert errors[0] == "3 frames in the candump log, 2 sent"
        assert "line 3 is no candump -L frame" in errors[1]


class TestCandumpLogDuration:
    def test_first_to_last_frame(self):
        assert can.candump_log_duration(cangen_log(101, 8, step=0.01)) == pytest.approx(1.0)

    def test_one_frame(self):
        assert can.candump_log_duration(cangen_log(1, 8)) == 0.0


class FakeCanBoard(FakeLinuxShell):
    """answers wc -l and cat of the candump log with a canned log; candump
    keeps running after SIGTERM for `alive` checks with kill -0"""

    def __init__(self, log, versions=None, alive=0):
        super().__init__(versions=versions)
        self.log = log
        self.alive = alive

    def exec(self, *args):
        key = tuple(str(a) for a in args)
        if key[:2] == ("wc", "-l"):
            self.commands.append(key)
            return (0, f"{len(self.log.splitlines())} {key[2]}")
        if key[0] == "cat" and key[1].endswith("candump.log"):
            self.commands.append(key)
            return (0, self.log)
        if key[:2] == ("kill", "-0"):
            self.commands.append(key)
            if self.alive > 0:
                self.alive -= 1
                return (0, "")
            return (1, "")
        return super().exec(*args)


def canutils_log(frames, dllength, dev="can0"):
    """the log of candump of canutils for cangen -I i -L <dllength> -D i -n <frames>"""
    lines = [f"interface = {dev}, family = 29, type = 3, proto = 1"]
    for n in range(frames):
        data = (n % 256**dllength).to_bytes(dllength, "little")
        lines.append(f"<0x{n % 0x800:03x}> [{dllength}] " + "".join(f"{b:02x} " for b in data))
    return "\n".join(lines) + "\n"


class TestCheckCangenLogCanutils:
    def test_matching_log(self):
        assert can.check_cangen_log(canutils_log(10, 8), 10, 8, "can0", canutils=True) == []

    def test_no_data(self):
        assert can.check_cangen_log(canutils_log(3, 0), 3, 0, "can0", canutils=True) == []

    def test_lost_frame(self):
        lines = canutils_log(10, 8).splitlines()
        del lines[5]
        errors = can.check_cangen_log("\n".join(lines), 10, 8, "can0", canutils=True)
        # lines[5] is frame 4, so line 5 holds frame 5
        assert errors[:2] == [
            "9 frames in the candump log, 10 sent",
            "line 5 has CAN ID 0x5, expected 0x4",
        ]

    def test_wrong_data(self):
        log = canutils_log(3, 2).replace("<0x002> [2] 02 00", "<0x002> [2] 03 00")
        assert can.check_cangen_log(log, 3, 2, "can0", canutils=True) == [
            "line 3 has data 3, expected 2"
        ]

    def test_length_does_not_match_bytes(self):
        log = canutils_log(2, 2).replace("<0x001> [2]", "<0x001> [3]")
        assert can.check_cangen_log(log, 2, 2, "can0", canutils=True) == [
            "line 2 has length 3 for 2 bytes"
        ]

    def test_error_line(self):
        log = "candump: invalid option -- 'L'\n" + canutils_log(2, 8)
        errors = can.check_cangen_log(log, 2, 8, "can0", canutils=True)
        assert "line 1 is no candump frame: \"candump: invalid option -- 'L'\"" in errors

    def test_header_only_skipped_for_canutils(self):
        errors = can.check_cangen_log(canutils_log(2, 8), 2, 8, "can0")
        assert errors[0] == "3 frames in the candump log, 2 sent"


class TestCandumpIsCanutils:
    def test_canutils(self):
        assert can.candump_is_canutils(FakeLinuxShell(versions={"candump": "canutils:4.0.6"}))

    def test_can_utils(self):
        assert not can.candump_is_canutils(FakeLinuxShell())


class TestStopCandump:
    @pytest.fixture
    def clock(self, monkeypatch):
        now = [0.0]

        def sleep(s):
            now[0] += s

        monkeypatch.setattr(can.time, "sleep", sleep)
        monkeypatch.setattr(can.time, "monotonic", lambda: now[0])
        return now

    def test_ends_on_sigterm(self, clock):
        board = FakeCanBoard("")
        can.stop_candump(board, "269")
        assert board.commands == [("kill", "269"), ("kill", "-0", "269"), ("wait", "269")]

    def test_ends_a_bit_later(self, clock):
        board = FakeCanBoard("", alive=3)
        can.stop_candump(board, "269")
        assert ("kill", "-9", "269") not in board.commands
        assert board.commands[-1] == ("wait", "269")

    def test_killed_after_timeout(self, clock):
        board = FakeCanBoard("", alive=100)
        can.stop_candump(board, "269", timeout=2.0)
        assert board.commands[-2:] == [("kill", "-9", "269"), ("wait", "269")]
        assert 2.0 <= clock[0] < 2.5


class TestBoardLnxCangen:
    def run(self, monkeypatch, log, versions=None, **kwargs):
        monkeypatch.setattr(can.time, "sleep", lambda s: None)
        board = FakeCanBoard(log, versions=versions)
        can.board_lnx_cangen(
            lnx=board, candev=["can0"], candevsend=["can1"], frames="20", dllength="8", **kwargs
        )
        return board

    def candump_started(self, board):
        return [c for c in board.commands if c[0] == "candump"]

    def test_can_utils_candump_with_log_format(self, monkeypatch):
        board = self.run(monkeypatch, cangen_log(20, 8))
        assert self.candump_started(board)[0][:3] == ("candump", "can0", "-L")

    def test_canutils_candump(self, monkeypatch):
        messages = []
        log = types.SimpleNamespace(
            message=messages.append, c=lambda s: types.SimpleNamespace(green=s, red=s)
        )
        monkeypatch.setattr(can.tbot, "log", log)
        board = self.run(monkeypatch, canutils_log(20, 8), versions={"candump": "canutils:4.0.6"})
        [started] = self.candump_started(board)
        assert "-L" not in started
        assert any("no timestamps, no bitrate" in m for m in messages)

    def test_canutils_lost_frames_raise(self, monkeypatch):
        with pytest.raises(RuntimeError, match="differences in the candump log"):
            self.run(monkeypatch, canutils_log(15, 8), versions={"candump": "canutils:4.0.6"})

    def test_no_cangen_on_the_sender(self, monkeypatch):
        with pytest.raises(RuntimeError, match="cangen not found on fake-linux-"):
            self.run(monkeypatch, cangen_log(20, 8), versions={"cangen": "notfound"})

    def test_good_log(self, monkeypatch):
        board = self.run(monkeypatch, cangen_log(20, 8), tmpdir="/run/can")
        assert ("cat", "/run/can/candump.log") in board.commands
        # nothing is copied to another machine
        assert not any(c[0] == "scp" for c in board.commands)

    def test_lost_frames_raise(self, monkeypatch):
        with pytest.raises(RuntimeError, match="differences in the candump log of can1 -> can0"):
            self.run(monkeypatch, cangen_log(15, 8))


class TestCangenConfigCalls:
    def test_both_directions(self):
        calls = can.cangen_config_calls(
            {"boarddev": ["can0", "can1"], "labdev": "can2", "frames": 500, "dllength": 2}
        )
        assert calls == [
            (
                "lab2board",
                {
                    "candev": ["can0", "can1"],
                    "candevsend": ["can2"],
                    "candevdump": "can0",
                    "frames": "500",
                    "dllength": "2",
                },
            ),
            (
                "board2lab",
                {
                    "candev": ["can2"],
                    "candevsend": ["can0", "can1"],
                    "candevdump": "can2",
                    "frames": "500",
                    "dllength": "2",
                },
            ),
        ]

    def test_one_direction(self):
        calls = can.cangen_config_calls(
            {"boarddev": "can0", "labdev": "can1", "directions": "board2lab"}
        )
        assert calls == [
            ("board2lab", {"candev": ["can1"], "candevsend": ["can0"], "candevdump": "can1"})
        ]

    def test_no_direction(self):
        assert can.cangen_config_calls({"boarddev": "can0", "labdev": "can1", "directions": []}) == []

    def test_unknown_direction(self):
        with pytest.raises(ValueError, match="unknown directions \\['lab2lab'\\] in cangen"):
            can.cangen_config_calls(
                {"boarddev": "can0", "labdev": "can1", "directions": ["lab2board", "lab2lab"]}
            )

    @pytest.mark.parametrize(
        "run, missing",
        [({}, "boarddev, labdev"), ({"boarddev": "can0"}, "labdev"), ({"labdev": "can0"}, "boarddev")],
    )
    def test_interfaces_are_needed(self, run, missing):
        with pytest.raises(ValueError, match=f"cangen needs {missing}$"):
            can.cangen_config_calls(run)

    def test_unknown_key(self):
        with pytest.raises(ValueError, match="unknown keys \\['candev'\\] in cangen"):
            can.cangen_config_calls({"boarddev": "can0", "labdev": "can1", "candev": "can0"})

    def test_kwargs_are_parameters_of_board_lnx_cangen(self):
        params = set(inspect.signature(can.board_lnx_cangen).parameters)
        run = {key: "1" for key in can.CANGEN_CONFIG_KEYS}
        run["directions"] = list(can.CANGEN_DIRECTIONS)
        for _, kwargs in can.cangen_config_calls(run):
            assert set(kwargs) <= params
            # the machines come from the testcase, not from the configuration
            assert not {"lnx", "lnxsend"} & set(kwargs)

    def test_runs_board_lnx_cangen(self, monkeypatch):
        monkeypatch.setattr(can.time, "sleep", lambda s: None)
        board = FakeCanBoard(cangen_log(5, 1, dev="can1"))
        [(_, kwargs)] = can.cangen_config_calls(
            {"boarddev": "can1", "labdev": "can1", "directions": ["lab2board"], "frames": 5, "dllength": 1}
        )
        can.board_lnx_cangen(lnx=board, **kwargs)
        assert any(c[:2] == ("cangen", "-g") and "5" in c for c in board.commands)
