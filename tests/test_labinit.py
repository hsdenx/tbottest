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

import pytest

from conftest import load_module

labinit = load_module(
    "tbottest_common_labinit",
    os.path.join(os.path.dirname(__file__), "..", "tbottest", "common", "labinit.py"),
)

MARKER = labinit.LABINIT_MARKER

ETHDEVICES = {
    "eth0": {"labdevice": "eth0", "serverip": "192.168.3.1"},
}


class CommandFailed(Exception):
    pass


class FakeLab:
    def __init__(self, files=(), interfaces=("eth0",), fail=None):
        self.files = set(files)
        self.interfaces = interfaces
        self.fail = fail
        self.log = []

    def exec(self, *args):
        self.log.append(args)
        if args[:2] == ("test", "-f"):
            return (0 if args[2] in self.files else 1, "")
        return (0, "")

    def exec0(self, *args):
        self.log.append(args)
        if args[0] == "date":
            self.files.add(args[2])
            return ""
        if args == ("ifconfig", "-a"):
            return "\n".join(f"{i}: flags=4163<UP>" for i in self.interfaces)
        if args[:3] == ("ip", "link", "show"):
            return "2: eth0: <BROADCAST,UP,LOWER_UP> state UP"
        if self.fail is not None and args == (self.fail,):
            raise CommandFailed(self.fail)
        return ""

    def ran(self, *args):
        return args in self.log

    def ifconfig_up(self):
        return [a for a in self.log if a[:2] == ("sudo", "ifconfig")]


def test_first_run_does_labinit_and_ethernet():
    lab = FakeLab()
    labinit.lab_init_once(lab, ["cmd1", "cmd2"], "board", ETHDEVICES)

    assert lab.ran("cmd1") and lab.ran("cmd2")
    assert lab.ifconfig_up() == [("sudo", "ifconfig", "eth0", "down", "192.168.3.1", "up")]
    assert lab.files == {MARKER, f"{MARKER}-board"}


def test_second_run_does_nothing():
    lab = FakeLab(files={MARKER, f"{MARKER}-board"})
    labinit.lab_init_once(lab, ["cmd1"], "board", ETHDEVICES)

    assert not lab.ran("cmd1")
    assert lab.ifconfig_up() == []


def test_second_board_gets_its_ethernet_setup():
    lab = FakeLab(files={MARKER, f"{MARKER}-board"})
    labinit.lab_init_once(lab, ["cmd1"], "other", ETHDEVICES)

    assert not lab.ran("cmd1")
    assert len(lab.ifconfig_up()) == 1
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
