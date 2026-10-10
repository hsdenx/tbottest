"""
Unit tests for lnx_sudo() in tbottest/tc/common.py and the code that uses
it: sudo only when the machine is not logged in as root.

A lab host built with Yocto is logged in to as root and may have no sudo;
a lab host with a normal user needs it. lnx_sudo() asks "id -u" once per
machine name.
"""

import os
import sys

import pytest

from conftest import install_fake_initconfig, install_real_submodule, load_module

install_fake_initconfig()
# one module object for the tests, network.py and can.py (which import
# lnx_sudo from tbottest.tc.common), so they share the _UID cache
install_real_submodule(
    "tbottest.tc.common",
    os.path.join(os.path.dirname(__file__), "..", "tbottest", "tc", "common.py"),
)
common = sys.modules["tbottest.tc.common"]
network = load_module(
    "tbottest_tc_network_sudo",
    os.path.join(os.path.dirname(__file__), "..", "tbottest", "tc", "network.py"),
)
can = load_module(
    "tbottest_tc_can_sudo",
    os.path.join(os.path.dirname(__file__), "..", "tbottest", "tc", "can.py"),
)

ID = ("id", "-u")


class FakeShell:
    """records the commands, answers "id -u" with uid"""

    def __init__(self, uid, name="lab"):
        self.uid = uid
        self.name = name
        self.calls = []

    def exec0(self, *args):
        args = tuple(str(a) for a in args)
        self.calls.append(args)
        return f"{self.uid}\n" if args == ID else ""

    def exec(self, *args):
        return 0, self.exec0(*args)

    def test(self, *args):
        # lnx_netcmd(): "command -v ip" finds ip
        return True

    def commands(self):
        return [c for c in self.calls if c != ID]


@pytest.fixture(autouse=True)
def fresh_caches():
    common._UID.clear()
    network._NETCMD.clear()
    yield
    common._UID.clear()
    network._NETCMD.clear()


class TestLnxSudo:
    def test_root_needs_no_sudo(self):
        assert common.lnx_sudo(FakeShell(0)) == []

    def test_user_needs_sudo(self):
        assert common.lnx_sudo(FakeShell(1000)) == ["sudo"]

    def test_asks_once_per_machine_name(self):
        lab = FakeShell(0)
        common.lnx_sudo(lab)
        common.lnx_sudo(lab)
        assert lab.calls.count(ID) == 1

    def test_machines_are_kept_apart_by_name(self):
        assert common.lnx_sudo(FakeShell(0, name="lab")) == []
        assert common.lnx_sudo(FakeShell(1000, name="build")) == ["sudo"]

    def test_machine_without_name_is_asked_every_time(self):
        lab = FakeShell(0, name=None)
        common.lnx_sudo(lab)
        common.lnx_sudo(lab)
        assert lab.calls.count(ID) == 2
        assert common._UID == {}


class TestSudoSubshell:
    def test_root_runs_the_commands_directly(self):
        lab = FakeShell(0)

        def no_subshell(*args):
            raise AssertionError("no sudo subshell for root")

        lab.subshell = no_subshell
        common.sudo_subshell(lab, ["mkdir -p /srv/x", "touch /srv/x/y"])
        assert lab.commands() == [("mkdir -p /srv/x",), ("touch /srv/x/y",)]


class TestCommonCommands:
    def test_install_debian_as_root(self):
        lab = FakeShell(0)
        common.common_install_debian(lab, "xz-utils")
        assert lab.commands() == [("apt-get", "-y", "install", "xz-utils")]

    def test_install_fedora_as_user(self):
        lab = FakeShell(1000)
        common.common_install_fedora(lab, "xz")
        assert lab.commands() == [("sudo", "dnf", "-y", "install", "xz")]


class TestNetworkSudo:
    def test_set_ipaddr_with_sudo_as_root(self):
        lab = FakeShell(0)
        network.lnx_set_ipaddr(lab, "eth1", "192.168.3.1", sudo=True)
        cmds = lab.commands()
        assert cmds
        assert not [c for c in cmds if c[0] == "sudo"]

    def test_set_ipaddr_with_sudo_as_user(self):
        lab = FakeShell(1000)
        network.lnx_set_ipaddr(lab, "eth1", "192.168.3.1", sudo=True)
        assert all(c[0] == "sudo" for c in lab.commands())

    def test_without_sudo_the_user_id_is_not_asked(self):
        lab = FakeShell(1000)
        network.lnx_ifup(lab, "eth1")
        assert ID not in lab.calls
        assert lab.calls == [("ip", "link", "set", "eth1", "up")]


class TestCanSudo:
    def test_usesudo_as_root(self):
        lab = FakeShell(0)
        can.sudo_exec0(lab, True, "ip", "link", "set", "can0", "up")
        assert lab.commands() == [("ip", "link", "set", "can0", "up")]

    def test_usesudo_as_user(self):
        lab = FakeShell(1000)
        can.sudo_exec0(lab, True, "ip", "link", "set", "can0", "up")
        assert lab.commands() == [("sudo", "ip", "link", "set", "can0", "up")]
