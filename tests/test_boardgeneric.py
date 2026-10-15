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

from conftest import fake_cmd_get_version, load_definition, load_module

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

    cmd_get_version = fake_cmd_get_version

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


class FakeConfigParser:
    """sections -> ordered dict of key -> value, as configparser returns them"""

    def __init__(self, sections):
        self.sections = sections

    def has_section(self, section):
        return section in self.sections

    def options(self, section):
        return list(self.sections[section])

    def get(self, section, key):
        return self.sections[section][key]


def load_ub_env():
    mod = Funcs()
    for name in ("ub_env_groups", "ub_env_check_groups", "ub_env_select"):
        part = load_definition(
            f"tbottest_boardgeneric_{name}_only",
            BOARDGENERIC_PATH,
            name,
            extra_src="import ast",
        )
        setattr(mod, name, getattr(part, name))
    # ub_env_select() calls ub_env_check_groups() by its global name
    mod.ub_env_select.__globals__["ub_env_check_groups"] = mod.ub_env_check_groups
    return mod


def env(*names):
    return str([{"name": n, "val": n.upper()} for n in names])


GROUPS = {
    "setip": [{"name": "ipaddr", "val": "1"}],
    "uimageboot": [{"name": "load_uimage", "val": "2"}],
    "nfsboot": [{"name": "net_nfs", "val": "3"}],
    "fitboot": [{"name": "net_fit", "val": "4"}],
}
DEPENDS = {
    "uimageboot": ["setip"],
    "nfsboot": ["setip", "uimageboot"],
    "fitboot": ["setip"],
}


class TestUbEnvGroups:
    def test_groups_from_tc_in_ini_order(self):
        ub = load_ub_env()
        cp = FakeConfigParser(
            {
                "TC": {
                    "ub_env": env("console"),
                    "ub_env_setip": env("ipaddr"),
                    "ub_env_depends": "{}",
                    "ub_env_bootcmd": "{}",
                    "ub_env_fitboot": env("net_fit"),
                    "uboot_prompt": "=> ",
                }
            }
        )
        groups = ub.ub_env_groups(cp, "amc")
        assert list(groups) == ["setip", "fitboot"]
        assert groups["setip"] == [{"name": "ipaddr", "val": "IPADDR"}]

    def test_board_section_hides_tc(self):
        ub = load_ub_env()
        cp = FakeConfigParser(
            {
                "TC_amc": {"ub_env_setip": env("serverip")},
                "TC": {"ub_env_setip": env("ipaddr"), "ub_env_fitboot": env("net_fit")},
            }
        )
        groups = ub.ub_env_groups(cp, "amc")
        assert groups["setip"] == [{"name": "serverip", "val": "SERVERIP"}]
        assert "fitboot" in groups

    def test_no_groups(self):
        ub = load_ub_env()
        cp = FakeConfigParser({"TC": {"ub_env": env("console")}})
        assert ub.ub_env_groups(cp, "amc") == {}


class TestUbEnvSelect:
    def test_without_flag_all_groups_dependencies_first(self):
        ub = load_ub_env()
        order = ub.ub_env_select(GROUPS, DEPENDS, [])
        assert sorted(order) == sorted(GROUPS)
        assert order.index("setip") < order.index("uimageboot") < order.index("nfsboot")
        assert order.index("setip") < order.index("fitboot")

    def test_selection_adds_dependencies(self):
        ub = load_ub_env()
        assert ub.ub_env_select(GROUPS, DEPENDS, ["ub_env:fitboot"]) == ["setip", "fitboot"]

    def test_dependencies_over_two_levels(self):
        ub = load_ub_env()
        order = ub.ub_env_select(GROUPS, DEPENDS, ["ub_env:nfsboot"])
        assert order == ["setip", "uimageboot", "nfsboot"]

    def test_each_group_once_in_flag_order(self):
        ub = load_ub_env()
        order = ub.ub_env_select(GROUPS, DEPENDS, ["ub_env:fitboot,nfsboot"])
        assert order == ["setip", "fitboot", "uimageboot", "nfsboot"]

    def test_none(self):
        ub = load_ub_env()
        assert ub.ub_env_select(GROUPS, DEPENDS, ["ub_env:none"]) == []

    def test_unknown_group_in_flag(self):
        ub = load_ub_env()
        with pytest.raises(RuntimeError, match="ub_env:fitbot: unknown group"):
            ub.ub_env_select(GROUPS, DEPENDS, ["ub_env:fitbot"])

    def test_unknown_group_in_depends(self):
        ub = load_ub_env()
        with pytest.raises(RuntimeError, match="unknown group 'kernel'"):
            ub.ub_env_select(GROUPS, {"nfsboot": ["kernel"]}, [])

    def test_cycle(self):
        ub = load_ub_env()
        with pytest.raises(RuntimeError, match="cycle setip -> fitboot -> setip"):
            ub.ub_env_select(GROUPS, {"setip": ["fitboot"], "fitboot": ["setip"]}, ["ub_env:setip"])

    def test_no_groups_no_flag(self):
        ub = load_ub_env()
        assert ub.ub_env_select({}, {}, []) == []


BOOTCMDS = {"net_fit": ["fitboot"], "net_nfs": ["nfsboot"]}


class TestUbEnvBootcmd:
    def test_bootcmd_selects_its_groups(self):
        ub = load_ub_env()
        order = ub.ub_env_select(GROUPS, DEPENDS, ["bootcmd:net_fit"], BOOTCMDS)
        assert order == ["setip", "fitboot"]

    def test_bootcmd_with_dependencies(self):
        ub = load_ub_env()
        order = ub.ub_env_select(GROUPS, DEPENDS, ["bootcmd:net_nfs"], BOOTCMDS)
        assert order == ["setip", "uimageboot", "nfsboot"]

    def test_bootcmd_without_mapping_selects_all(self):
        ub = load_ub_env()
        order = ub.ub_env_select(GROUPS, DEPENDS, ["bootcmd:net_initramfs"], BOOTCMDS)
        assert sorted(order) == sorted(GROUPS)

    def test_union_with_ub_env_flag(self):
        ub = load_ub_env()
        flags = ["ub_env:uimageboot", "bootcmd:net_fit"]
        assert ub.ub_env_select(GROUPS, DEPENDS, flags, BOOTCMDS) == [
            "setip",
            "uimageboot",
            "fitboot",
        ]

    def test_none_wins_over_bootcmd(self):
        ub = load_ub_env()
        flags = ["ub_env:none", "bootcmd:net_fit"]
        assert ub.ub_env_select(GROUPS, DEPENDS, flags, BOOTCMDS) == []

    def test_unknown_group_in_bootcmd(self):
        ub = load_ub_env()
        with pytest.raises(RuntimeError, match="ub_env_bootcmd: unknown group 'fit'"):
            ub.ub_env_select(GROUPS, DEPENDS, [], {"net_fit": ["fit"]})

    def test_bootcmd_key_is_no_group(self):
        ub = load_ub_env()
        cp = FakeConfigParser({"TC": {"ub_env_bootcmd": str(BOOTCMDS)}})
        assert ub.ub_env_groups(cp, "amc") == {}
