"""
Unit tests for tbottest/tc/generic_board.py.

The generic testcases read a key of the board configuration and call a
helper for each entry. These tests load the module with fakes for its
imports: the board configuration (cfggeneric) is a dictionary of ini
strings, the helpers of tc/common.py, tc/network.py, tc/leds.py and
tc/cpu.py only record their calls. generictestdef.py is the real one, so
require_cfg() really skips a testcase whose key is not set.

tc/can.py is the real one as well, for cangen_config_kwargs(). The kas
testcases are not covered, they need the KAS class.
"""

import ast
import contextlib
import json
import os
import sys
import types

import pytest

from conftest import install_real_submodule, load_module

HERE = os.path.dirname(__file__)
GENERIC_BOARD_PATH = os.path.join(HERE, "..", "tbottest", "tc", "generic_board.py")
GENERICTESTDEF_PATH = os.path.join(HERE, "..", "tbottest", "tc", "generictestdef.py")
CAN_PATH = os.path.join(HERE, "..", "tbottest", "tc", "can.py")

# the board configuration of a test, key -> ini string
CONFIG = {}
DEFAULTS = {"serverip": "192.168.3.1", "ipaddr": "192.168.3.45"}
# calls of the fake helpers, (name, args, kwargs)
CALLS = []


def recorder(name, result=None):
    def f(*args, **kwargs):
        CALLS.append((name, args, kwargs))
        return result() if callable(result) else result

    return f


class FakeCfg:
    """cfggeneric with the board configuration in CONFIG"""

    def __init__(self):
        self.cfgp = types.SimpleNamespace(config_parser="board-config-parser")

    def get_config(self, key, default=None):
        return CONFIG.get(key, default)

    def get_config_literal(self, key, default):
        return ast.literal_eval(CONFIG.get(key, default))

    def get_default_config(self, key, default=None):
        return DEFAULTS.get(key, default)

    def get_lnx_dump_files(self):
        return ast.literal_eval(CONFIG.get("lnx_dump_files", "[]"))


class FakeIniConfig:
    def get_config(self, key, default=None):
        return CONFIG.get(key, default)


TESTCASES_RUN = []


@contextlib.contextmanager
def fake_init_testcase(name):
    TESTCASES_RUN.append(name)
    yield


def install_fakes():
    ini = types.ModuleType("tbottest.initconfig")
    ini.init_testcase = fake_init_testcase
    ini.IniConfig = FakeIniConfig
    ini.generic_get_boardname = lambda: "BOARDNAME"
    ini.init_config_to_json_dict = lambda cfgp, resolved: {"from": cfgp, "resolved": resolved}
    sys.modules.setdefault("tbottest", types.ModuleType("tbottest"))
    sys.modules["tbottest.initconfig"] = ini

    boardgeneric = types.ModuleType("tbottest.boardgeneric")
    boardgeneric.cfggeneric = FakeCfg()
    sys.modules["tbottest.boardgeneric"] = boardgeneric

    labgeneric = types.ModuleType("tbottest.labgeneric")
    labgeneric.cfgt = types.SimpleNamespace(
        config_parser="lab-config-parser", find_sections=lambda name: CONFIG.get("_sections", [])
    )
    sys.modules["tbottest.labgeneric"] = labgeneric

    sys.modules.setdefault("tbottest.tc", types.ModuleType("tbottest.tc"))
    common = types.ModuleType("tbottest.tc.common")
    for name in (
        "lnx_check_beeper",
        "lnx_check_revfile",
        "lnx_cmd_versions",
        "lnx_create_revfile",
    ):
        setattr(common, name, recorder(name))
    common.lnx_check_cmd = recorder("lnx_check_cmd", lambda: CONFIG.get("_ret", True))
    common.lnx_check_dmesg = recorder("lnx_check_dmesg", lambda: CONFIG.get("_ret", True))
    common.lx_devmem2_get = recorder("lx_devmem2_get", "0x1234")
    # for the real tc/can.py
    common.lnx_sudo = lambda lnx: []
    common.tbot_start_thread = recorder("tbot_start_thread")
    common.tbot_stop_thread = recorder("tbot_stop_thread")
    sys.modules["tbottest.tc.common"] = common

    cpu = types.ModuleType("tbottest.tc.cpu")
    cpu.generic_get_socname = recorder("generic_get_socname", lambda: CONFIG.get("_soc", "imx8mp"))
    sys.modules["tbottest.tc.cpu"] = cpu

    network = types.ModuleType("tbottest.tc.network")
    network.lnx_network_ping = recorder("lnx_network_ping")
    network.network_linux_iperf = recorder("network_linux_iperf")
    sys.modules["tbottest.tc.network"] = network

    leds = types.ModuleType("tbottest.tc.leds")
    leds.lnx_test_led_simple = recorder("lnx_test_led_simple")
    sys.modules["tbottest.tc.leds"] = leds

    kas = types.ModuleType("tbottest.tc.kas")
    kas.KAS = object
    sys.modules["tbottest.tc.kas"] = kas

    class FakeRegisterMap:
        def __init__(self, path):
            CALLS.append(("REGISTERMAP", (path,), {}))

        def registermap_dump_register_file(self, *args):
            CALLS.append(("registermap_dump_register_file", args, {}))

    registermap = types.ModuleType("tbottest.tc.registermap")
    registermap.REGISTERMAP = FakeRegisterMap
    sys.modules["tbottest.tc.registermap"] = registermap

    install_real_submodule("tbottest.tc.generictestdef", GENERICTESTDEF_PATH)
    install_real_submodule("tbottest.tc.can", CAN_PATH)


install_fakes()
gb = load_module("tbottest_tc_generic_board", GENERIC_BOARD_PATH)
gtd = sys.modules["tbottest.tc.generictestdef"]


@pytest.fixture(autouse=True)
def clean():
    CONFIG.clear()
    CALLS.clear()
    TESTCASES_RUN.clear()
    yield


def calls(name):
    return [(args, kwargs) for n, args, kwargs in CALLS if n == name]


LNX = object()
LAB = object()


@pytest.mark.parametrize(
    "testcase,key",
    [
        ("generic_lx_dump_register", "regdump"),
        ("generic_lnx_network_ping", "ping"),
        ("generic_lnx_test_beep", "beep"),
        ("generic_lnx_commands", "lnx_commands"),
        ("generic_lnx_test_dmesg", "dmesg"),
        ("generic_lnx_test_led", "leds"),
        ("generic_lnx_test_cangen", "cangen"),
    ],
)
def test_skipped_without_its_key(testcase, key):
    assert getattr(gb, testcase)(lnx=LNX) == gtd.TC_SKIP
    assert CALLS == []
    assert TESTCASES_RUN == [testcase]


def test_iperf_skipped_without_its_key():
    assert gb.generic_lnx_network_iperf(lab=LAB, lnx=LNX) == gtd.TC_SKIP
    assert CALLS == []


def test_empty_list_counts_as_not_set():
    CONFIG["ping"] = "[]"
    assert gb.generic_lnx_network_ping(lnx=LNX) == gtd.TC_SKIP


def test_ping():
    CONFIG["ping"] = '[{"ip": "192.168.3.1", "retry": "10"}, {"ip": "10.0.0.1", "retry": "2"}]'
    gb.generic_lnx_network_ping(lnx=LNX)
    assert calls("lnx_network_ping") == [((LNX, "192.168.3.1", 10), {}), ((LNX, "10.0.0.1", 2), {})]


def test_iperf_both_directions():
    CONFIG["iperf"] = '[{"intervall": "1", "cycles": "30", "minval": "290000000"}]'
    gb.generic_lnx_network_iperf(lab=LAB, lnx=LNX)
    assert calls("network_linux_iperf") == [
        # server on the lab host, then server on the board
        ((LNX, LAB, "192.168.3.1", "1", "30", "290000000"), {}),
        ((LAB, LNX, "192.168.3.45", "1", "30", "290000000"), {}),
    ]


def test_beep():
    CONFIG["beep"] = '[{"freq": "440", "length": "1000"}]'
    gb.generic_lnx_test_beep(lnx=LNX)
    assert calls("lnx_check_beeper") == [((LNX, [{"freq": "440", "length": "1000"}]), {})]


def test_lnx_commands():
    CONFIG["lnx_commands"] = '[{"cmd": "uname -a", "val": "Linux"}]'
    gb.generic_lnx_commands(lnx=LNX)
    assert calls("lnx_check_cmd") == [((LNX, [{"cmd": "uname -a", "val": "Linux"}]), {})]


def test_lnx_commands_fail():
    CONFIG["lnx_commands"] = '[{"cmd": "uname -a", "val": "Linux"}]'
    CONFIG["_ret"] = False
    with pytest.raises(RuntimeError):
        gb.generic_lnx_commands(lnx=LNX)


def test_dmesg_passes_both_lists():
    CONFIG["dmesg"] = '["Machine model"]'
    CONFIG["dmesg_false"] = '["crash"]'
    assert gb.generic_lnx_test_dmesg(lnx=LNX) == gtd.TC_OKAY
    assert calls("lnx_check_dmesg") == [((LNX, ["Machine model"], ["crash"]), {})]


def test_dmesg_fail():
    CONFIG["dmesg"] = '["Machine model"]'
    CONFIG["_ret"] = False
    with pytest.raises(RuntimeError, match="dmesg"):
        gb.generic_lnx_test_dmesg(lnx=LNX)


def test_leds():
    CONFIG["leds"] = '[{"path": "/sys/class/leds/led-orange", "bootval": "0", "onval": "1"}]'
    assert gb.generic_lnx_test_led(lnx=LNX) == gtd.TC_OKAY
    assert calls("lnx_test_led_simple") == [
        ((LNX, [{"path": "/sys/class/leds/led-orange", "bootval": "0", "onval": "1"}]), {})
    ]


def test_cangen_runs_board_lnx_cangen_per_entry(monkeypatch):
    monkeypatch.setattr(gb, "board_lnx_cangen", recorder("board_lnx_cangen"))
    CONFIG["cangen"] = repr(
        [
            {"candev": ["can0", "can1"], "candevsend": "can1", "frames": 500},
            {"dllength": 1, "bitrate": "250000"},
        ]
    )
    assert gb.generic_lnx_test_cangen(lnx=LNX) == gtd.TC_OKAY
    assert calls("board_lnx_cangen") == [
        ((), {"lnx": LNX, "candev": ["can0", "can1"], "candevsend": ["can1"], "frames": "500"}),
        ((), {"lnx": LNX, "dllength": "1", "bitrate": "250000"}),
    ]


def test_cangen_unknown_key(monkeypatch):
    monkeypatch.setattr(gb, "board_lnx_cangen", recorder("board_lnx_cangen"))
    CONFIG["cangen"] = '[{"frame": "1000"}]'
    with pytest.raises(ValueError, match="unknown keys"):
        gb.generic_lnx_test_cangen(lnx=LNX)
    assert calls("board_lnx_cangen") == []


DUMP = {
    "revfile": "pinmux.reg",
    "startaddr": "0x44e10800",
    "endaddr": "0x44e10808",
    "mask": "0xffffffff",
    "readtype": "w",
    "difffile": "None",
    "timeout": "None",
}


def test_check_dump_files():
    CONFIG["lnx_dump_files"] = repr([DUMP])
    gb.generic_lnx_check_dump_files(lnx=LNX)
    assert calls("lnx_check_revfile") == [((LNX, "pinmux.reg", "None", "None"), {})]


def test_create_dump_files():
    CONFIG["lnx_dump_files"] = repr([DUMP])
    gb.generic_lnx_create_dump_files(lnx=LNX)
    assert calls("lnx_create_revfile") == [
        ((LNX, "pinmux.reg", "0x44e10800", "0x44e10808", "0xffffffff", "w"), {})
    ]


def test_dump_files_without_config():
    gb.generic_lnx_check_dump_files(lnx=LNX)
    gb.generic_lnx_create_dump_files(lnx=LNX)
    assert CALLS == []


class FakeLocalPath(str):
    def _local_str(self):
        return str(self)


class FakeLocal:
    def __init__(self):
        self.commands = []

    def sourcedir(self):
        return FakeLocalPath("/src")

    def workdir(self):
        return FakeLocalPath("/work")

    def exec0(self, *args):
        self.commands.append(args)
        return ""


class FakeCx:
    def __init__(self, machines):
        self.machines = machines

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def request(self, role):
        return self.machines[role]


@pytest.fixture
def local(monkeypatch):
    local = FakeLocal()
    monkeypatch.setattr(gb.tbot, "ctx", lambda: FakeCx({gb.tbot.role.LocalHost: local}))
    return local


def test_dump_register(local):
    CONFIG["regdump"] = '[{"address": "0x30340004"}, {"address": "0x30330070"}]'
    gb.generic_lx_dump_register(lnx=LNX)
    assert calls("REGISTERMAP") == [(("/src/scripts/registermap/imx8mp_registers.json",), {})]
    assert local.commands == [("rm", "-rf", "/work/generic_registerdump.txt")]
    assert calls("lx_devmem2_get") == [((LNX, "0x30340004", "w"), {}), ((LNX, "0x30330070", "w"), {})]
    assert calls("registermap_dump_register_file") == [
        (("/work/generic_registerdump.txt", "0x30340004", "0x1234"), {}),
        (("/work/generic_registerdump.txt", "0x30330070", "0x1234"), {}),
    ]


def test_dump_register_unknown_soc(local):
    CONFIG["regdump"] = '[{"address": "0x30340004"}]'
    CONFIG["_soc"] = "SoC not detected"
    assert gb.generic_lx_dump_register(lnx=LNX) == gtd.TC_SKIP
    assert calls("lx_devmem2_get") == []


def test_cmd_versions_without_build_host(monkeypatch):
    gb.generic_cmd_versions(lab=LAB, lnx=LNX)
    assert calls("lnx_cmd_versions") == [
        ((LAB,), {"autoinstall": False}),
        ((LNX,), {"autoinstall": False, "keyindent": "    "}),
    ]


def test_cmd_versions_with_build_host_and_install(monkeypatch):
    bh = types.SimpleNamespace(sn="BUILDHOST")
    # the tbot stub of conftest has no build host role
    monkeypatch.setattr(gb.tbot.role, "BuildHost", object(), raising=False)
    monkeypatch.setattr(gb.tbot, "ctx", lambda: FakeCx({gb.tbot.role.BuildHost: bh}))
    monkeypatch.setattr(gb.tbot, "flags", {"cmd_versions_install"})
    CONFIG["_sections"] = ["BUILDHOST"]
    gb.generic_cmd_versions(lab=LAB, lnx=LNX)
    assert [args[0] for args, _ in calls("lnx_cmd_versions")] == [LAB, bh, LNX]
    assert all(kwargs["autoinstall"] for _, kwargs in calls("lnx_cmd_versions"))


def test_config_to_json(tmp_path):
    gb.generic_config_to_json(outdir=str(tmp_path))
    assert json.loads((tmp_path / "tbot.json").read_text()) == {
        "from": "lab-config-parser",
        "resolved": False,
    }
    assert json.loads((tmp_path / "BOARDNAME.json").read_text()) == {
        "from": "board-config-parser",
        "resolved": False,
    }


def test_config_to_json_dir_from_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(gb.tbot, "flags", {f"config_json_dir:{tmp_path}/out", "config_json_resolved"})
    gb.generic_config_to_json()
    assert json.loads((tmp_path / "out" / "tbot.json").read_text())["resolved"] is True


class LogText(str):
    """tbot.log.c() that keeps the text, any colour returns it"""

    def __getattr__(self, name):
        return self


def test_lnx_all_counts(monkeypatch):
    messages = []
    monkeypatch.setattr(gb.tbot.log, "c", LogText)
    monkeypatch.setattr(gb.tbot.log, "message", lambda text: messages.append(str(text)))

    def fail():
        raise RuntimeError("broken")

    monkeypatch.setattr(gb, "lnxtestcases", ["tc_ok", "tc_skip", "tc_fail"])
    monkeypatch.setattr(gb, "tc_ok", lambda: gtd.TC_OKAY, raising=False)
    monkeypatch.setattr(gb, "tc_skip", lambda: gtd.TC_SKIP, raising=False)
    monkeypatch.setattr(gb, "tc_fail", fail, raising=False)
    gb.generic_lnx_all()  # does not raise for a failed testcase
    assert "tc count 3 success 1 skipped 1 failed 1" in messages
    assert "skipped ['tc_skip']" in messages
    assert "failed ['tc_fail']" in messages


def test_lnx_all_list_names_testcases_of_the_module():
    for name in gb.lnxtestcases:
        assert callable(getattr(gb, name))
