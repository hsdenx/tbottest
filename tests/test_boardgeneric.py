"""
Unit tests for tbottest/boardgeneric.py: lnx_set_ethdevices(),
lnx_root_on_nfs() and board_testdir().

boardgeneric.py cannot be imported here (its module body resolves a real
board environment), so the functions' current source is taken out of it
with conftest.load_definition and run against a fake board shell and a
fake board ini. lnx_set_ethdevice() comes from tbottest/tc/network.py,
see test_network.py.
"""

import os

import pytest

from conftest import load_definition, load_module

BOARDGENERIC_PATH = os.path.join(
    os.path.dirname(__file__), "..", "tbottest", "boardgeneric.py"
)

network = load_module(
    "tbottest_tc_network_for_boardgeneric",
    os.path.join(os.path.dirname(__file__), "..", "tbottest", "tc", "network.py"),
)

ETHCFG = {"ipaddr": "192.168.3.20", "netmask": "255.255.255.0"}


@pytest.fixture(autouse=True)
def fresh_netcmd_cache():
    network._NETCMD.clear()
    yield
    network._NETCMD.clear()


class FakeIni:
    def __init__(self, values):
        self.values = values

    def get_config(self, name, default):
        return self.values.get(name, default)


class FakeShell:
    """board shell that has the commands in `commands` (for command -v)"""

    name = "board"

    def __init__(self, commands):
        self.commands = commands
        self.calls = []

    def test(self, *args):
        self.calls.append(("test",) + args)
        return args[:2] == ("command", "-v") and args[2] in self.commands

    def exec0(self, *args):
        self.calls.append(("exec0",) + args)
        return ""


class Funcs:
    pass


def load_set_ethdevices(ini=None):
    mod = Funcs()
    for name in ("lnx_root_on_nfs", "lnx_set_ethdevices"):
        part = load_definition(
            f"tbottest_boardgeneric_{name}_only",
            BOARDGENERIC_PATH,
            name,
            extra_src="import tbot",
        )
        setattr(mod, name, getattr(part, name))
    # lnx_set_ethdevices() calls these by their global names
    mod.lnx_set_ethdevices.__globals__.update(
        lnx_root_on_nfs=mod.lnx_root_on_nfs,
        lnx_set_ethdevice=network.lnx_set_ethdevice,
        cfg=FakeIni(ini or {}),
    )
    return mod


MOUNTS_NFS = """rootfs / rootfs rw 0 0
192.168.3.1:/srv/nfs/abb/amc-tqm855m/nfs / nfs rw,relatime,vers=3 0 0
proc /proc proc rw,relatime 0 0
"""

MOUNTS_FLASH = """/dev/root / jffs2 rw,relatime 0 0
192.168.3.1:/srv/nfs/data /mnt nfs rw,relatime,vers=3 0 0
proc /proc proc rw,relatime 0 0
"""


class MountsShell(FakeShell):
    def __init__(self, commands, mounts):
        super().__init__(commands)
        self.mounts = mounts

    def exec0(self, *args):
        if args == ("cat", "/proc/mounts"):
            return self.mounts
        return super().exec0(*args)


class TestLnxSetEthdevices:
    def test_root_on_nfs_skips_the_setup(self):
        lnx = MountsShell({"ip"}, MOUNTS_NFS)
        load_set_ethdevices().lnx_set_ethdevices(lnx, {"eth0": ETHCFG})
        assert lnx.calls == []

    def test_root_on_flash_sets_up_every_device(self):
        lnx = MountsShell({"ip"}, MOUNTS_FLASH)
        load_set_ethdevices().lnx_set_ethdevices(lnx, {"eth0": ETHCFG, "eth1": ETHCFG})
        assert [c[1:] for c in lnx.calls if c[0] == "exec0"] == [
            ("ip", "link", "set", "eth0", "down"),
            ("ip", "-4", "addr", "flush", "dev", "eth0"),
            ("ip", "addr", "add", "192.168.3.20/24", "dev", "eth0"),
            ("ip", "link", "set", "eth0", "up"),
            ("ip", "link", "set", "eth1", "down"),
            ("ip", "-4", "addr", "flush", "dev", "eth1"),
            ("ip", "addr", "add", "192.168.3.20/24", "dev", "eth1"),
            ("ip", "link", "set", "eth1", "up"),
        ]

    def test_linux_netcmd_from_board_ini(self):
        lnx = MountsShell({"ip"}, MOUNTS_FLASH)
        mod = load_set_ethdevices({"linux_netcmd": "ifconfig"})
        mod.lnx_set_ethdevices(lnx, {"eth0": ETHCFG})
        assert [c[1:] for c in lnx.calls if c[0] == "exec0" and c[1] != "cat"] == [
            ("ifconfig", "eth0", "down", "192.168.3.20", "netmask", "255.255.255.0", "up"),
        ]

    def test_nfs4_root(self):
        mounts = MOUNTS_NFS.replace(" nfs ", " nfs4 ")
        lnx = MountsShell({"ip"}, mounts)
        assert load_set_ethdevices().lnx_root_on_nfs(lnx) is True


def load_board_testdir(values):
    mod = load_definition(
        "tbottest_boardgeneric_board_testdir_only",
        BOARDGENERIC_PATH,
        "board_testdir",
        extra_src="cfg = None",
    )
    mod.cfg = FakeIni(values)
    return mod


class TestBoardTestdir:
    def test_default(self):
        assert load_board_testdir({}).board_testdir() == "/run/tbot-testdata/tbottests"

    def test_from_board_ini(self):
        mod = load_board_testdir({"testdir": "/home/root/tbottests"})
        assert mod.board_testdir() == "/home/root/tbottests"
