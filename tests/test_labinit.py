"""
Unit tests for tbottest/common/labinit.py: the labinit commands run once
per boot of the lab host, the ethernet setup once per board, and a marker
is only written after its part succeeded.

FakeLab simulates the lab host: a set of existing files for the
"test -f" checks and the "date > marker" writes, a log of every command,
and optionally one labinit command that fails like exec0() does.
"""

import configparser
import os
import sys

import pytest

from conftest import load_module

labinit = load_module(
    "tbottest_common_labinit",
    os.path.join(os.path.dirname(__file__), "..", "tbottest", "common", "labinit.py"),
)

# labinit imports the ip/ifconfig helpers from tbottest.tc.network when it
# sets up the lab's ethernet devices
network = load_module(
    "tbottest_tc_network_for_labinit",
    os.path.join(os.path.dirname(__file__), "..", "tbottest", "tc", "network.py"),
)


@pytest.fixture(autouse=True)
def network_module(monkeypatch):
    monkeypatch.setitem(sys.modules, "tbottest.tc.network", network)
    network._NETCMD.clear()
    yield
    network._NETCMD.clear()


MARKER = labinit.LABINIT_MARKER

ETHDEVICES = {
    "eth0": {"labdevice": "eth0", "serverip": "192.168.3.1"},
}


class CommandFailed(Exception):
    pass


class FakeLab:
    name = "lab"

    def __init__(self, files=(), interfaces=("eth0",), fail=None, netcmd="ip", addrs=None):
        self.files = set(files)
        self.interfaces = interfaces
        self.fail = fail
        self.netcmd = netcmd
        # IPv4 address per device, as "ip -4 addr show" / ifconfig report it
        self.addrs = addrs or {}
        self.log = []

    def test(self, *args):
        return args[:2] == ("command", "-v") and args[2] == self.netcmd

    def exec(self, *args):
        self.log.append(args)
        if args[:2] == ("test", "-f"):
            return (0 if args[2] in self.files else 1, "")
        if args[:4] == ("ip", "link", "show", "dev") or args[:1] == ("ifconfig",):
            return (0 if args[-1] in self.interfaces else 1, "")
        return (0, "")

    def exec0(self, *args):
        self.log.append(args)
        if args[0] == "date":
            self.files.add(args[2])
            return ""
        if args[:5] == ("ip", "-4", "addr", "show", "dev"):
            addr = self.addrs.get(args[5])
            return f"    inet {addr}/24 brd x scope global {args[5]}" if addr else ""
        if args[:1] == ("ifconfig",) and len(args) == 2:
            addr = self.addrs.get(args[1])
            return f"{args[1]}\n          inet addr:{addr}  Bcast:x" if addr else args[1]
        if args[:3] == ("ip", "link", "show"):
            return "2: eth0: <BROADCAST,UP,LOWER_UP> state UP"
        if self.fail is not None and args == (self.fail,):
            raise CommandFailed(self.fail)
        return ""

    def ran(self, *args):
        return args in self.log

    def ifconfig_up(self):
        """commands that set an address on a lab device"""
        return [a for a in self.log if a[:2] in (("sudo", "ifconfig"), ("sudo", "ip"))]


def test_first_run_does_labinit_and_ethernet():
    lab = FakeLab()
    labinit.lab_init_once(lab, ["cmd1", "cmd2"], "board", ETHDEVICES)

    assert lab.ran("cmd1") and lab.ran("cmd2")
    assert lab.ifconfig_up() == [
        ("sudo", "ip", "link", "set", "eth0", "down"),
        ("sudo", "ip", "-4", "addr", "flush", "dev", "eth0"),
        ("sudo", "ip", "addr", "add", "192.168.3.1/24", "dev", "eth0"),
        ("sudo", "ip", "link", "set", "eth0", "up"),
    ]
    assert lab.files == {MARKER, f"{MARKER}-board"}


def test_lab_without_ip_uses_ifconfig():
    lab = FakeLab(netcmd="ifconfig")
    labinit.lab_init_once(lab, [], "board", ETHDEVICES)

    assert lab.ifconfig_up() == [("sudo", "ifconfig", "eth0", "down", "192.168.3.1", "up")]


def test_second_run_does_nothing():
    lab = FakeLab(files={MARKER, f"{MARKER}-board"})
    labinit.lab_init_once(lab, ["cmd1"], "board", ETHDEVICES)

    assert not lab.ran("cmd1")
    assert lab.ifconfig_up() == []


def test_second_board_gets_its_ethernet_setup():
    lab = FakeLab(files={MARKER, f"{MARKER}-board"})
    labinit.lab_init_once(lab, ["cmd1"], "other", ETHDEVICES)

    assert not lab.ran("cmd1")
    assert len(lab.ifconfig_up()) == 4
    assert f"{MARKER}-other" in lab.files


def test_noethinit_skips_ethernet_and_its_marker():
    lab = FakeLab()
    labinit.lab_init_once(lab, ["cmd1"], "board", ETHDEVICES, ethinit=False)

    assert lab.ran("cmd1")
    assert lab.ifconfig_up() == []
    assert lab.files == {MARKER}


def test_failing_labinit_command_is_not_marked_done():
    lab = FakeLab(fail="cmd2")
    with pytest.raises(CommandFailed):
        labinit.lab_init_once(lab, ["cmd1", "cmd2", "cmd3"], "board", ETHDEVICES)

    assert not lab.ran("cmd3")
    assert MARKER not in lab.files
    assert lab.ifconfig_up() == []


def test_missing_lab_interface_is_skipped():
    lab = FakeLab(interfaces=("wlan0",))
    labinit.lab_init_once(lab, [], "board", ETHDEVICES)

    assert lab.ifconfig_up() == []
    assert f"{MARKER}-board" in lab.files


def test_device_in_another_network_is_refused():
    lab = FakeLab(addrs={"eth0": "192.168.1.123"})
    labinit.lab_init_once(lab, [], "board", ETHDEVICES)

    assert lab.ifconfig_up() == []
    # no marker: the setup runs again once labdevice is fixed
    assert f"{MARKER}-board" not in lab.files


def test_refused_device_does_not_stop_the_others():
    devices = dict(ETHDEVICES, eth1={"labdevice": "eth1", "serverip": "192.168.3.1"})
    lab = FakeLab(interfaces=("eth0", "eth1"), addrs={"eth0": "192.168.1.123"})
    labinit.lab_init_once(lab, [], "board", devices)

    assert ("sudo", "ip", "addr", "add", "192.168.3.1/24", "dev", "eth1") in lab.log
    assert not any("eth0" in a for a in lab.ifconfig_up())
    assert f"{MARKER}-board" not in lab.files


def test_device_already_in_the_network_is_set_up():
    lab = FakeLab(addrs={"eth0": "192.168.3.7"})
    labinit.lab_init_once(lab, [], "board", ETHDEVICES)

    assert ("sudo", "ip", "addr", "add", "192.168.3.1/24", "dev", "eth0") in lab.log
    assert f"{MARKER}-board" in lab.files


def test_device_in_another_network_is_refused_with_ifconfig():
    lab = FakeLab(netcmd="ifconfig", addrs={"eth0": "192.168.1.123"})
    labinit.lab_init_once(lab, [], "board", ETHDEVICES)

    assert lab.ifconfig_up() == []
    assert f"{MARKER}-board" not in lab.files


def _parser(text):
    cp = configparser.RawConfigParser()
    cp.read_string(text)
    return cp


def test_labinit_from_config_reads_the_list():
    cp = _parser('[LABHOST]\nlabinit = ["sudo true", "echo hi"]\n')
    assert labinit.labinit_from_config(cp, "LABHOST") == ["sudo true", "echo hi"]


@pytest.mark.parametrize(
    "text",
    ["[LABHOST]\nname = x\n", "[LABHOST]\nlabinit = [not python\n", "[OTHER]\nx = 1\n"],
)
def test_labinit_from_config_missing_or_malformed_is_empty(text):
    assert labinit.labinit_from_config(_parser(text), "LABHOST") == []
