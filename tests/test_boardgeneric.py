"""
Unit tests for lnx_set_ethdevice() in tbottest/boardgeneric.py.

boardgeneric.py cannot be imported here (its module body resolves a real
board environment), so the function's current source is taken out of it
with conftest.load_definition and run against a fake board shell and a
fake board ini.
"""

import os

import pytest

from conftest import load_definition

BOARDGENERIC_PATH = os.path.join(
    os.path.dirname(__file__), "..", "tbottest", "boardgeneric.py"
)

ETHCFG = {"ipaddr": "192.168.3.20", "netmask": "255.255.255.0"}


class FakeIni:
    def __init__(self, values):
        self.values = values

    def get_config(self, name, default):
        return self.values.get(name, default)


def load_set_ethdevice(ini=None):
    mod = load_definition(
        "tbottest_boardgeneric_lnx_set_ethdevice_only",
        BOARDGENERIC_PATH,
        "lnx_set_ethdevice",
        extra_src="import tbot\nLNX_NETCMD = None\ncfg = None",
    )
    mod.cfg = FakeIni(ini or {})
    return mod


class FakeShell:
    """board shell that has the commands in `commands` (for command -v)"""

    def __init__(self, commands):
        self.commands = commands
        self.calls = []

    def test(self, *args):
        self.calls.append(("test",) + args)
        return args[:2] == ("command", "-v") and args[2] in self.commands

    def exec0(self, *args):
        self.calls.append(("exec0",) + args)
        return ""


CHECK = [("test", "command", "-v", "ip")]

IP_CALLS = [
    ("exec0", "ip", "link", "set", "eth0", "down"),
    ("exec0", "ip", "addr", "add", "192.168.3.20/255.255.255.0", "dev", "eth0"),
    ("exec0", "ip", "link", "set", "eth0", "up"),
]

IFCONFIG_CALLS = [
    ("exec0", "ifconfig", "eth0", "down", "192.168.3.20", "netmask", "255.255.255.0", "up"),
]


class TestLnxSetEthdevice:
    def test_auto_ip_when_the_board_has_it(self):
        lnx = FakeShell({"ip", "ifconfig"})
        load_set_ethdevice().lnx_set_ethdevice(lnx, "eth0", ETHCFG)
        assert lnx.calls == CHECK + IP_CALLS

    def test_auto_ifconfig_without_ip(self):
        lnx = FakeShell({"ifconfig"})
        load_set_ethdevice().lnx_set_ethdevice(lnx, "eth0", ETHCFG)
        assert lnx.calls == CHECK + IFCONFIG_CALLS

    def test_explicit_auto(self):
        lnx = FakeShell({"ip"})
        mod = load_set_ethdevice({"linux_netcmd": "auto"})
        mod.lnx_set_ethdevice(lnx, "eth0", ETHCFG)
        assert lnx.calls == CHECK + IP_CALLS

    def test_ini_ip_without_check(self):
        lnx = FakeShell(set())
        mod = load_set_ethdevice({"linux_netcmd": "ip"})
        mod.lnx_set_ethdevice(lnx, "eth0", ETHCFG)
        assert lnx.calls == IP_CALLS

    def test_ini_ifconfig_without_check(self):
        lnx = FakeShell({"ip", "ifconfig"})
        mod = load_set_ethdevice({"linux_netcmd": "ifconfig"})
        mod.lnx_set_ethdevice(lnx, "eth0", ETHCFG)
        assert lnx.calls == IFCONFIG_CALLS

    def test_ini_invalid(self):
        mod = load_set_ethdevice({"linux_netcmd": "route"})
        with pytest.raises(RuntimeError, match="must be auto, ip or ifconfig"):
            mod.lnx_set_ethdevice(FakeShell({"ip"}), "eth0", ETHCFG)

    def test_useifconfig_flag_wins_over_ini(self):
        import tbot

        tbot.flags = {"useifconfig"}
        lnx = FakeShell({"ip", "ifconfig"})
        mod = load_set_ethdevice({"linux_netcmd": "ip"})
        mod.lnx_set_ethdevice(lnx, "eth0", ETHCFG)
        assert lnx.calls == IFCONFIG_CALLS

    def test_checked_once(self):
        mod = load_set_ethdevice()
        lnx = FakeShell({"ip"})
        mod.lnx_set_ethdevice(lnx, "eth0", ETHCFG)
        mod.lnx_set_ethdevice(lnx, "eth1", ETHCFG)
        assert [c for c in lnx.calls if c[0] == "test"] == CHECK
        assert [c[1] for c in lnx.calls if c[0] == "exec0"] == ["ip"] * 6

    def test_result_kept_for_a_new_shell(self):
        mod = load_set_ethdevice()
        mod.lnx_set_ethdevice(FakeShell({"ifconfig"}), "eth0", ETHCFG)
        lnx = FakeShell({"ip"})
        mod.lnx_set_ethdevice(lnx, "eth0", ETHCFG)
        assert lnx.calls == IFCONFIG_CALLS


def load_set_ethdevices(ini=None):
    mod = load_set_ethdevice(ini)
    for name in ("lnx_root_on_nfs", "lnx_set_ethdevices"):
        part = load_definition(
            f"tbottest_boardgeneric_{name}_only",
            BOARDGENERIC_PATH,
            name,
            extra_src="import tbot",
        )
        setattr(mod, name, getattr(part, name))
    # lnx_set_ethdevices() calls the other two by their global names
    mod.lnx_set_ethdevices.__globals__.update(
        lnx_root_on_nfs=mod.lnx_root_on_nfs, lnx_set_ethdevice=mod.lnx_set_ethdevice
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
            ("ip", "addr", "add", "192.168.3.20/255.255.255.0", "dev", "eth0"),
            ("ip", "link", "set", "eth0", "up"),
            ("ip", "link", "set", "eth1", "down"),
            ("ip", "addr", "add", "192.168.3.20/255.255.255.0", "dev", "eth1"),
            ("ip", "link", "set", "eth1", "up"),
        ]

    def test_nfs4_root(self):
        mounts = MOUNTS_NFS.replace(" nfs ", " nfs4 ")
        lnx = MountsShell({"ip"}, mounts)
        assert load_set_ethdevices().lnx_root_on_nfs(lnx) is True
