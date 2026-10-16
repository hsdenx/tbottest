"""
Unit tests for methods of GenericLab in tbottest/labgeneric.py.

labgeneric.py cannot be imported here (its module body resolves a real
lab and board environment), so the method's current source is taken out
of the class GenericLab with ast and run against stubs for
tbottest.boardgeneric and tbot's linux module.
"""

import ast
import configparser
import os
import sys
import textwrap
import types

import pytest

from conftest import FakeIniTBotConfig

LABGENERIC_PATH = os.path.join(
    os.path.dirname(__file__), "..", "tbottest", "labgeneric.py"
)


CFGT = FakeIniTBotConfig(configparser.RawConfigParser())


def tbot_ini(sections):
    """tbot.ini for CFGT, {section: {key: value}}"""
    CFGT.config_parser = configparser.RawConfigParser()
    CFGT.config_parser.read_dict(sections)


def load_method(classname, methodname):
    src = open(LABGENERIC_PATH).read()
    for node in ast.parse(src).body:
        if isinstance(node, ast.ClassDef) and node.name == classname:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == methodname:
                    def_src = textwrap.dedent(ast.get_source_segment(src, item, padded=True))
                    break
            else:
                continue
            break
    else:
        raise AssertionError(f"{classname}.{methodname} not found in {LABGENERIC_PATH}")

    linux = types.SimpleNamespace(
        Workdir=types.SimpleNamespace(static=lambda host, path: ("workdir", path))
    )
    ini = types.SimpleNamespace(generic_get_boardname=lambda: "BOARDNAME")
    ns = {"linux": linux, "LABSECTIONNAME": "LABHOST", "cfgt": CFGT, "ini": ini}
    exec(compile(def_src, LABGENERIC_PATH, "exec"), ns)
    return ns[methodname]


class BoardConfig:
    def __init__(self, values):
        self.values = values

    def get_default_config(self, name, default):
        return self.values.get(name, default)


@pytest.fixture
def boardgeneric(monkeypatch):
    mod = types.ModuleType("tbottest.boardgeneric")
    monkeypatch.setitem(sys.modules, "tbottest.boardgeneric", mod)
    return mod


class Lab:
    # in GenericLab the method shadows the class attribute of the same
    # name, so self.nfsboardbasedir is the (true) bound method
    nfsboardbasedir = True


class TestNfsboardbasedir:
    def test_nfs_path_from_default_section(self, boardgeneric):
        boardgeneric.cfggeneric = BoardConfig({"nfs_path": "/srv/nfs/abb/amc-tqm855m"})
        nfsboardbasedir = load_method("GenericLab", "nfsboardbasedir")
        assert nfsboardbasedir(Lab()) == ("workdir", "/srv/nfs/abb/amc-tqm855m")

    def test_nfs_path_missing(self, boardgeneric):
        boardgeneric.cfggeneric = BoardConfig({})
        nfsboardbasedir = load_method("GenericLab", "nfsboardbasedir")
        with pytest.raises(RuntimeError, match="nfs_path missing"):
            nfsboardbasedir(Lab())


class _LocalPath(str):
    def _local_str(self):
        return str(self)


class LabWithWorkdir:
    def workdir(self):
        return _LocalPath("/work/hs/tbot-workdir/amc")


class TestLabTestdir:
    def setup_method(self):
        tbot_ini({"LABHOST": {}})

    def test_default_below_workdir(self):
        testdir = load_method("GenericLab", "testdir")
        assert testdir(LabWithWorkdir()) == (
            "workdir",
            "/work/hs/tbot-workdir/amc/tbottests",
        )

    def test_from_lab_section(self):
        tbot_ini({"LABHOST": {"testdir": "/srv/tbottests"}})
        testdir = load_method("GenericLab", "testdir")
        assert testdir(LabWithWorkdir()) == ("workdir", "/srv/tbottests")


class LabExec:
    """records exec0() calls"""

    def __init__(self):
        self.calls = []

    def exec0(self, *args):
        self.calls.append(tuple(str(a) for a in args))
        return ""


@pytest.fixture
def lnx_sudo(monkeypatch):
    """tbottest.tc.common with an lnx_sudo() that returns the prefix set in
    the fixture's value (default: root, no sudo)"""
    prefix = []
    mod = types.ModuleType("tbottest.tc.common")
    mod.lnx_sudo = lambda lnx: list(prefix)
    monkeypatch.setitem(sys.modules, "tbottest.tc.common", mod)
    tbot_ini({"SDWIRE": {"serial": "da23"}})
    yield prefix
    tbot_ini({})


class TestSdMuxMode:
    def test_dut_runs_sd_mux_ctrl_from_path(self, lnx_sudo):
        lab = LabExec()
        load_method("GenericLab", "lab_set_sd_mux_mode")(lab, "dut")
        # sd-mux-ctrl without a fixed path: it is found in PATH, wherever
        # the lab host installed it (/usr/bin on a Yocto built lab host)
        assert lab.calls == [("sd-mux-ctrl", "--device-serial=da23", "--dut")]

    def test_lab_mode(self, lnx_sudo):
        lab = LabExec()
        load_method("GenericLab", "lab_set_sd_mux_mode")(lab, "lab")
        assert lab.calls == [("sd-mux-ctrl", "--device-serial=da23", "--ts")]

    def test_with_sudo(self, lnx_sudo):
        lnx_sudo.append("sudo")
        lab = LabExec()
        load_method("GenericLab", "lab_set_sd_mux_mode")(lab, "dut")
        assert lab.calls == [("sudo", "sd-mux-ctrl", "--device-serial=da23", "--dut")]

    def test_unknown_mode_raises(self, lnx_sudo):
        with pytest.raises(RuntimeError):
            load_method("GenericLab", "lab_set_sd_mux_mode")(LabExec(), "off")


class SSHBoard:
    IP_BOARD_SSH_INTERFACE = "eth1"


class TestBoardSSHHostname:
    def test_ipaddr_of_the_interface(self):
        tbot_ini(
            {"IPSETUP_BOARDNAME_eth0": {"ipaddr": "1.1.1.1"}, "IPSETUP_BOARDNAME_eth1": {"ipaddr": "2.2.2.2"}}
        )
        hostname = load_method("boardSSHConnector", "hostname")
        assert hostname(SSHBoard()) == "2.2.2.2"

    def test_missing_ipaddr_raises(self):
        tbot_ini({"IPSETUP_BOARDNAME_eth0": {"ipaddr": "1.1.1.1"}})
        hostname = load_method("boardSSHConnector", "hostname")
        with pytest.raises(RuntimeError, match="Expect section IPSETUP_BOARDNAME_eth1 with key ipaddr"):
            hostname(SSHBoard())
