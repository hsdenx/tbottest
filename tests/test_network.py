"""
Unit tests for the ip/ifconfig helpers in tbottest/tc/network.py:
choosing the command per machine, setting and reading addresses, and
the parsers for the output of ip and of ifconfig.
"""

import os

import pytest

from conftest import load_module

network = load_module(
    "tbottest_tc_network",
    os.path.join(os.path.dirname(__file__), "..", "tbottest", "tc", "network.py"),
)

ETHCFG = {"ipaddr": "192.168.3.20", "netmask": "255.255.255.0"}


class FakeShell:
    """linux shell that has the commands in `commands` (for command -v)
    and answers exec0/exec with `responses` (prefix of the command ->
    output)"""

    def __init__(self, commands=("ip",), responses=None, name="board", missing=()):
        self.commands = set(commands)
        self.responses = responses or {}
        self.name = name
        self.missing = set(missing)
        self.calls = []

    def test(self, *args):
        self.calls.append(("test",) + args)
        return args[:2] == ("command", "-v") and args[2] in self.commands

    def _respond(self, args):
        for prefix, out in self.responses.items():
            if args[: len(prefix)] == prefix:
                return out
        return ""

    def exec0(self, *args):
        args = tuple(str(a) for a in args)
        self.calls.append(("exec0",) + args)
        return self._respond(args)

    def exec(self, *args):
        args = tuple(str(a) for a in args)
        self.calls.append(("exec",) + args)
        ret = 1 if any(d in args for d in self.missing) else 0
        return (ret, self._respond(args))

    def commands_run(self):
        return [c[1:] for c in self.calls if c[0] in ("exec0", "exec")]


@pytest.fixture(autouse=True)
def fresh_cache():
    network._NETCMD.clear()
    yield
    network._NETCMD.clear()


CHECK = ("test", "command", "-v", "ip")


class TestNetcmd:
    def test_auto_takes_ip_if_there(self):
        lnx = FakeShell({"ip", "ifconfig"})
        assert network.lnx_netcmd(lnx) == "ip"
        assert lnx.calls == [CHECK]

    def test_auto_takes_ifconfig_without_ip(self):
        assert network.lnx_netcmd(FakeShell({"ifconfig"})) == "ifconfig"

    def test_explicit_choice_is_not_checked(self):
        lnx = FakeShell(set())
        assert network.lnx_netcmd(lnx, "ip") == "ip"
        assert network.lnx_netcmd(lnx, "ifconfig") == "ifconfig"
        assert lnx.calls == []

    def test_invalid_choice(self):
        with pytest.raises(RuntimeError, match="must be auto, ip or ifconfig"):
            network.lnx_netcmd(FakeShell(), "route")

    def test_useifconfig_flag_wins(self):
        import tbot

        tbot.flags = {"useifconfig"}
        lnx = FakeShell({"ip"})
        assert network.lnx_netcmd(lnx, "ip") == "ifconfig"
        assert lnx.calls == []

    def test_checked_once_per_machine(self):
        lnx = FakeShell({"ip"})
        network.lnx_netcmd(lnx)
        network.lnx_netcmd(lnx)
        assert lnx.calls == [CHECK]

    def test_kept_for_a_new_shell_of_the_same_machine(self):
        network.lnx_netcmd(FakeShell({"ifconfig"}, name="board"))
        assert network.lnx_netcmd(FakeShell({"ip"}, name="board")) == "ifconfig"

    def test_later_calls_come_from_the_cache(self):
        import tbot

        lnx = FakeShell({"ip"})
        assert network.lnx_netcmd(lnx) == "ip"
        # a flag set later does not change what was worked out
        tbot.flags = {"useifconfig"}
        assert network.lnx_netcmd(lnx) == "ip"
        assert lnx.calls == [CHECK]

    def test_explicit_choice_after_auto_is_kept_apart(self):
        lnx = FakeShell({"ip"})
        assert network.lnx_netcmd(lnx) == "ip"
        assert network.lnx_netcmd(lnx, "ifconfig") == "ifconfig"
        assert network.lnx_netcmd(lnx) == "ip"

    def test_invalid_choice_is_not_cached(self):
        lnx = FakeShell()
        for _ in range(2):
            with pytest.raises(RuntimeError, match="must be auto, ip or ifconfig"):
                network.lnx_netcmd(lnx, "route")
        assert network._NETCMD == {}

    def test_other_machine_checked_on_its_own(self):
        assert network.lnx_netcmd(FakeShell({"ifconfig"}, name="board")) == "ifconfig"
        assert network.lnx_netcmd(FakeShell({"ip"}, name="lab")) == "ip"


class TestPrefixes:
    @pytest.mark.parametrize(
        "mask,prefix",
        [("255.255.255.0", 24), ("255.255.0.0", 16), ("255.0.0.0", 8),
         ("255.255.255.252", 30), ("0.0.0.0", 0), ("255.255.255.255", 32)],
    )
    def test_netmask_to_prefix(self, mask, prefix):
        assert network.netmask_to_prefix(mask) == prefix

    @pytest.mark.parametrize("mask", ["255.0.255.0", "255.255.255", "255.255.255.x", "24"])
    def test_not_a_netmask(self, mask):
        with pytest.raises(RuntimeError, match="not an IPv4 netmask"):
            network.netmask_to_prefix(mask)

    @pytest.mark.parametrize(
        "ip,prefix", [("10.1.2.3", 8), ("172.16.0.1", 16), ("192.168.3.1", 24)]
    )
    def test_classful_prefix(self, ip, prefix):
        assert network.classful_prefix(ip) == prefix


class TestIpv4InNet:
    @pytest.mark.parametrize(
        "addr,net,prefix,inside",
        [("192.168.3.7", "192.168.3.1", 24, True),
         ("192.168.1.123", "192.168.3.1", 24, False),
         ("10.9.8.7", "10.0.0.1", 8, True),
         ("192.168.4.1", "192.168.3.1", 24, False)],
    )
    def test_ipv4_in_net(self, addr, net, prefix, inside):
        assert network.ipv4_in_net(addr, net, prefix) is inside


class TestSetIpaddr:
    def test_ip_with_netmask(self):
        lnx = FakeShell({"ip"})
        network.lnx_set_ipaddr(lnx, "eth0", "192.168.3.20", "255.255.255.0")
        assert lnx.commands_run() == [
            ("ip", "link", "set", "eth0", "down"),
            ("ip", "-4", "addr", "flush", "dev", "eth0"),
            ("ip", "addr", "add", "192.168.3.20/24", "dev", "eth0"),
            ("ip", "link", "set", "eth0", "up"),
        ]

    def test_ip_without_netmask_takes_the_class(self):
        lnx = FakeShell({"ip"})
        network.lnx_set_ipaddr(lnx, "eth1", "10.0.0.1")
        assert ("ip", "addr", "add", "10.0.0.1/8", "dev", "eth1") in lnx.commands_run()

    def test_ifconfig_with_and_without_netmask(self):
        lnx = FakeShell({"ifconfig"})
        network.lnx_set_ipaddr(lnx, "eth0", "192.168.3.20", "255.255.255.0")
        network.lnx_set_ipaddr(lnx, "eth0", "192.168.3.21")
        assert lnx.commands_run() == [
            ("ifconfig", "eth0", "down", "192.168.3.20", "netmask", "255.255.255.0", "up"),
            ("ifconfig", "eth0", "down", "192.168.3.21", "up"),
        ]

    def test_sudo_prefixes_every_command(self):
        lnx = FakeShell({"ip"})
        network.lnx_set_ipaddr(lnx, "eth0", "192.168.3.1", sudo=True)
        assert all(c[0] == "sudo" for c in lnx.commands_run())

    def test_set_ethdevice(self):
        lnx = FakeShell({"ifconfig"})
        network.lnx_set_ethdevice(lnx, "eth0", ETHCFG)
        assert lnx.commands_run() == [
            ("ifconfig", "eth0", "down", "192.168.3.20", "netmask", "255.255.255.0", "up"),
        ]

    def test_set_ethdevice_netcmd_from_board_ini(self):
        lnx = FakeShell(set())
        network.lnx_set_ethdevice(lnx, "eth0", ETHCFG, "ip")
        assert ("ip", "addr", "add", "192.168.3.20/24", "dev", "eth0") in lnx.commands_run()
        assert CHECK not in lnx.calls


class TestUpDown:
    def test_ip(self):
        lnx = FakeShell({"ip"})
        network.lnx_ifdown(lnx, "can0")
        network.lnx_ifup(lnx, "can0", sudo=True)
        assert lnx.commands_run() == [
            ("ip", "link", "set", "can0", "down"),
            ("sudo", "ip", "link", "set", "can0", "up"),
        ]

    def test_ifconfig(self):
        lnx = FakeShell({"ifconfig"})
        network.lnx_ifdown(lnx, "eth0")
        network.lnx_ifup(lnx, "eth0")
        assert lnx.commands_run() == [("ifconfig", "eth0", "down"), ("ifconfig", "eth0", "up")]


class TestHasNetdev:
    def test_ip(self):
        lnx = FakeShell({"ip"}, missing={"wlan0"})
        assert network.lnx_has_netdev(lnx, "eth0") is True
        assert network.lnx_has_netdev(lnx, "wlan0") is False
        assert ("ip", "link", "show", "dev", "eth0") in lnx.commands_run()

    def test_ifconfig(self):
        lnx = FakeShell({"ifconfig"}, missing={"wlan0"})
        assert network.lnx_has_netdev(lnx, "eth1") is True
        assert network.lnx_has_netdev(lnx, "wlan0") is False
        assert ("ifconfig", "eth1") in lnx.commands_run()


IP_LINK = """2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast qlen 1000
    link/ether 00:30:d6:0b:36:0c brd ff:ff:ff:ff:ff:ff"""

IP_ADDR4 = """2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast qlen 1000
    inet 192.168.3.20/24 brd 192.168.3.255 scope global eth0
       valid_lft forever preferred_lft forever"""

IP_ADDR6 = """2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast qlen 1000
    inet6 fe80::230:d6ff:fe0b:360c/64 scope link
       valid_lft forever preferred_lft forever"""


class TestHwaddr:
    def test_ip(self):
        lnx = FakeShell({"ip"}, {("ip", "link", "show"): IP_LINK})
        assert network.lnx_get_hwaddr(lnx, "eth0") == "00:30:d6:0b:36:0c"

    def test_ifconfig_old_net_tools(self):
        lnx = FakeShell(
            {"ifconfig"}, {("ifconfig",): "eth0 Link encap:Ethernet HWaddr 00:11:22:33:44:55"}
        )
        assert network.lnx_get_hwaddr(lnx, "eth0") == "00:11:22:33:44:55"

    def test_ifconfig_new_net_tools(self):
        out = "eth0: flags=4163<UP>  mtu 1500\n        ether 00:11:22:33:44:56  txqueuelen 1000"
        lnx = FakeShell({"ifconfig"}, {("ifconfig",): out})
        assert network.lnx_get_hwaddr(lnx, "eth0") == "00:11:22:33:44:56"

    def test_missing(self):
        lnx = FakeShell({"ifconfig"}, {("ifconfig",): "eth0 Link encap:Ethernet"})
        with pytest.raises(RuntimeError, match="Could not get hwaddr"):
            network.lnx_get_hwaddr(lnx, "eth0")


class TestGetIpaddr:
    def test_ip_v4(self):
        lnx = FakeShell({"ip"}, {("ip", "-4", "addr", "show"): IP_ADDR4})
        assert network._lnx_get_ipaddr(lnx, "eth0") == "192.168.3.20"

    def test_ip_v6(self):
        lnx = FakeShell({"ip"}, {("ip", "-6", "addr", "show"): IP_ADDR6})
        assert network._lnx_get_ipaddr(lnx, "eth0", ip6=True) == "fe80::230:d6ff:fe0b:360c"

    def test_ip_no_address(self):
        lnx = FakeShell({"ip"}, {("ip",): IP_LINK.split("\n")[0]})
        with pytest.raises(RuntimeError, match="Could not get ip"):
            network._lnx_get_ipaddr(lnx, "eth0")

    def test_ifconfig_v4(self):
        out = "eth0\n          inet addr:10.0.0.5  Bcast:10.0.0.255"
        lnx = FakeShell({"ifconfig"}, {("ifconfig",): out})
        assert network._lnx_get_ipaddr(lnx, "eth0") == "10.0.0.5"

    def test_ifconfig_v6_old_style_net_tools(self):
        """
        Regression test: the ip6 regex used to be "\\d+.\\d+.\\d+.\\d+"
        (decimal digits only), so it could never match a real IPv6
        address (hex letters, "::" compression, "/prefixlen" suffix
        with no space before it).
        """
        out = "eth0\n          inet6 addr: fe80::1234:5678:9abc:def0/64 Scope:Link"
        lnx = FakeShell({"ifconfig"}, {("ifconfig",): out})
        assert network._lnx_get_ipaddr(lnx, "eth0", ip6=True) == "fe80::1234:5678:9abc:def0"

    def test_ifconfig_v6_newer_style_net_tools(self):
        out = "eth0\n        inet6 fe80::1234:5678:9abc:def0  prefixlen 64  scopeid 0x20<link>"
        lnx = FakeShell({"ifconfig"}, {("ifconfig",): out})
        assert network._lnx_get_ipaddr(lnx, "eth0", ip6=True) == "fe80::1234:5678:9abc:def0"

    def test_ifconfig_v6_compressed_address(self):
        out = "eth0\n          inet6 addr: ::1/128 Scope:Host"
        lnx = FakeShell({"ifconfig"}, {("ifconfig",): out})
        assert network._lnx_get_ipaddr(lnx, "eth0", ip6=True) == "::1"

    def test_polls_until_ip_appears(self, monkeypatch):
        monkeypatch.setattr(network.time, "sleep", lambda s: None)
        calls = {"n": 0}

        class FlakyShell(FakeShell):
            def exec0(self, *args):
                calls["n"] += 1
                return IP_ADDR4 if calls["n"] >= 3 else ""

        assert network.lnx_get_ipaddr(FlakyShell({"ip"}), "eth0", poll=5, sleep=0) == (
            "192.168.3.20"
        )

    def test_gives_up_after_poll_attempts(self, monkeypatch):
        monkeypatch.setattr(network.time, "sleep", lambda s: None)
        lnx = FakeShell({"ip"})
        with pytest.raises(RuntimeError, match="Could not get ip"):
            network.lnx_get_ipaddr(lnx, "eth0", poll=2, sleep=0)
        assert len([c for c in lnx.calls if c[0] == "exec0"]) == 3


class TestNetworkUp:
    def test_sets_address_and_returns_after_ping(self):
        lnx = FakeShell({"ip"})
        network.lnx_network_up(lnx, "eth0", "192.168.3.20", "192.168.3.1", 3)
        run = lnx.commands_run()
        assert ("ip", "addr", "add", "192.168.3.20/24", "dev", "eth0") in run
        assert run[-1] == ("ping", "192.168.3.1", "-c", "1", "-W", "1")

    def test_failing_ping_raises_after_retry_pings(self):
        lnx = FakeShell({"ip"}, missing={"192.168.3.1"})
        with pytest.raises(RuntimeError, match="Could not bring up"):
            network.lnx_network_up(lnx, "eth0", "192.168.3.20", "192.168.3.1", 2)
        assert len([c for c in lnx.commands_run() if c[0] == "ping"]) == 2
