import ipaddress
import re
import tbot
import time
from tbot.machine import linux
import math

# "ip" or "ifconfig" per (machine, prefer), see lnx_netcmd()
_NETCMD = {}
NETCMDS = ("ip", "ifconfig")


def lnx_netcmd(lnx: linux.LinuxShell, prefer: str = "auto") -> str:
    """
    command to configure the network of lnx with, "ip" or "ifconfig"

    :param lnx: linux machine
    :param prefer: auto (default): ip if lnx has it, else ifconfig, checked
        once per machine (by its name) with "command -v ip", not with the
        exit code of "ip --help", which iproute2 ends with 255 and busybox
        with 0. ip or ifconfig: that one, without a check.

    The tbot flag useifconfig takes ifconfig on every machine.

    The answer is worked out on the first call for a machine and prefer,
    and returned from _NETCMD on every later one.
    """
    key = (getattr(lnx, "name", None) or id(lnx), prefer)
    netcmd = _NETCMD.get(key)
    if netcmd is not None:
        return netcmd

    if "useifconfig" in tbot.flags:
        netcmd = "ifconfig"
    elif prefer in NETCMDS:
        netcmd = prefer
    elif prefer == "auto":
        netcmd = "ip" if lnx.test("command", "-v", "ip") else "ifconfig"
    else:
        raise RuntimeError(f"netcmd {prefer}: must be auto, ip or ifconfig")
    _NETCMD[key] = netcmd
    return netcmd


def netmask_to_prefix(netmask: str) -> int:
    """
    prefix length of a dotted IPv4 netmask, e.g. 24 for 255.255.255.0
    """
    parts = netmask.split(".")
    try:
        bits = "".join(f"{int(b):08b}" for b in parts)
    except ValueError:
        bits = ""
    if len(parts) != 4 or len(bits) != 32 or "01" in bits:
        raise RuntimeError(f"{netmask}: not an IPv4 netmask")
    return bits.count("1")


def classful_prefix(ipaddr: str) -> int:
    """
    prefix length the kernel gives an IPv4 address set without netmask
    (ifconfig <dev> <ipaddr>): by its class, 8 for A, 16 for B, 24 for C
    """
    first = int(ipaddr.split(".")[0])
    if first < 128:
        return 8
    if first < 192:
        return 16
    return 24


def ipv4_in_net(addr: str, netaddr: str, prefix: int) -> bool:
    """
    :returns: True if the IPv4 address addr is in the network of
        netaddr/prefix
    """
    net = ipaddress.ip_interface(f"{netaddr}/{prefix}").network
    return ipaddress.ip_address(addr) in net


def _sudo(lnx: linux.LinuxShell, sudo: bool) -> list:
    """
    prefix for the commands: sudo=True means "with root rights", which
    needs no sudo when lnx is logged in as root (lnx_sudo())
    """
    if not sudo:
        return []
    from tbottest.tc.common import lnx_sudo

    return lnx_sudo(lnx)


def lnx_ifdown(
    lnx: linux.LinuxShell, dev: str, sudo: bool = False, netcmd: str = "auto"
) -> None:
    """
    take the network device dev down, with ip or ifconfig (lnx_netcmd())
    """
    if lnx_netcmd(lnx, netcmd) == "ip":
        lnx.exec0(*_sudo(lnx, sudo), "ip", "link", "set", dev, "down")
    else:
        lnx.exec0(*_sudo(lnx, sudo), "ifconfig", dev, "down")


def lnx_ifup(
    lnx: linux.LinuxShell, dev: str, sudo: bool = False, netcmd: str = "auto"
) -> None:
    """
    bring the network device dev up, with ip or ifconfig (lnx_netcmd())
    """
    if lnx_netcmd(lnx, netcmd) == "ip":
        lnx.exec0(*_sudo(lnx, sudo), "ip", "link", "set", dev, "up")
    else:
        lnx.exec0(*_sudo(lnx, sudo), "ifconfig", dev, "up")


def lnx_set_ipaddr(
    lnx: linux.LinuxShell,
    dev: str,
    ipaddr: str,
    netmask: str = None,
    sudo: bool = False,
    netcmd: str = "auto",
) -> None:
    """
    set the IPv4 address of dev, taking it down and up again, as
    "ifconfig <dev> down <ipaddr> [netmask <netmask>] up" does

    With ip the old IPv4 addresses of dev are flushed first, as ifconfig
    replaces the address, and a second call does not fail on an address
    that is already there. Without netmask the prefix follows the address
    class, as with ifconfig (classful_prefix()).

    :param lnx: linux machine
    :param dev: network device, e.g. eth0
    :param ipaddr: IPv4 address
    :param netmask: dotted netmask, or None
    :param sudo: run the commands with root rights (sudo, unless lnx is
        logged in as root)
    :param netcmd: auto, ip or ifconfig, see lnx_netcmd()
    """
    s = _sudo(lnx, sudo)
    if lnx_netcmd(lnx, netcmd) == "ip":
        prefix = netmask_to_prefix(netmask) if netmask else classful_prefix(ipaddr)
        lnx.exec0(*s, "ip", "link", "set", dev, "down")
        lnx.exec0(*s, "ip", "-4", "addr", "flush", "dev", dev)
        lnx.exec0(*s, "ip", "addr", "add", f"{ipaddr}/{prefix}", "dev", dev)
        lnx.exec0(*s, "ip", "link", "set", dev, "up")
    else:
        mask = ["netmask", netmask] if netmask else []
        lnx.exec0(*s, "ifconfig", dev, "down", ipaddr, *mask, "up")


def lnx_set_ethdevice(
    lnx: linux.LinuxShell, dev: str, ethcfg: dict, netcmd: str = "auto"
) -> None:
    """
    set ipaddr and netmask from ethcfg on the ethernet device dev of the
    board, with ip or with ifconfig

    The board configuration sets netcmd with the key linux_netcmd in the
    [TC] section of the board ini (BOARDNAME.ini): auto (default), ip or
    ifconfig, see lnx_netcmd(). The flag useifconfig takes ifconfig,
    whatever linux_netcmd says.

    :param lnx: linux shell on the board
    :param dev: name of the ethernet device, e.g. eth0
    :param ethcfg: dictionary with the keys ipaddr and netmask
    :param netcmd: auto, ip or ifconfig
    """
    lnx_set_ipaddr(lnx, dev, ethcfg["ipaddr"], ethcfg["netmask"], netcmd=netcmd)


def lnx_has_netdev(lnx: linux.LinuxShell, dev: str, netcmd: str = "auto") -> bool:
    """
    :returns: True if lnx has the network device dev
    """
    if lnx_netcmd(lnx, netcmd) == "ip":
        ret, _ = lnx.exec("ip", "link", "show", "dev", dev)
    else:
        ret, _ = lnx.exec("ifconfig", dev)
    return ret == 0


@tbot.testcase
def lnx_get_hwaddr(lnx: linux.LinuxShell, name: str, netcmd: str = "auto") -> str:
    """
    get the MAC address of a network device

    :param lnx: linux machine from which we want to get the hwaddr
    :param name: name of the interface
    :param netcmd: auto, ip or ifconfig, see lnx_netcmd()
    """
    mac = r"(?P<hwaddr>[0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){5})"
    if lnx_netcmd(lnx, netcmd) == "ip":
        out = lnx.exec0("ip", "link", "show", "dev", name)
        # "    link/ether 00:11:22:33:44:55 brd ff:ff:ff:ff:ff:ff"
        patterns = [r"\s*link/ether\s+" + mac]
    else:
        out = lnx.exec0("ifconfig", name)
        # old net-tools and busybox: "... HWaddr 00:11:22:33:44:55"
        # newer net-tools: "        ether 00:11:22:33:44:55  txqueuelen ..."
        patterns = [r".*HWaddr\s+" + mac, r"\s+ether\s+" + mac]
    for line in out.split("\n"):
        for pattern in patterns:
            match = re.match(pattern, line)
            if match is not None:
                return match.group("hwaddr")

    raise RuntimeError(f"Could not get hwaddr for device {name}")


def _ipaddr_from_ip(out: str, ip6: bool):
    # "    inet 192.168.3.20/24 brd ...", "    inet6 fe80::1/64 scope link"
    if ip6:
        pattern = r"\s+inet6\s+(?P<ipaddr>[0-9a-fA-F:]+)/"
    else:
        pattern = r"\s+inet\s+(?P<ipaddr>\d+\.\d+\.\d+\.\d+)/"
    for line in out.split("\n"):
        match = re.match(pattern, line)
        if match is not None:
            return match.group("ipaddr")
    return None


def _ipaddr_from_ifconfig(out: str, ip6: bool):
    for line in out.split("\n"):
        if ip6:
            if "inet6" in line:
                # old-style net-tools: "inet6 addr: fe80::1/64  Scope:Link"
                match = re.match(
                    r"\s+inet6\s+addr:\s*(?P<ipaddr>[0-9a-fA-F:]+)",
                    line,
                )
                if match is None:
                    # newer net-tools: "inet6 fe80::1  prefixlen 64  scopeid ..."
                    match = re.match(
                        r"\s+inet6\s+(?P<ipaddr>[0-9a-fA-F:]+)",
                        line,
                    )

                if match is None:
                    continue
                return match.group("ipaddr")
        else:
            if "inet6" in line:
                continue
            if "inet" in line:
                match = re.match(
                    r"\s+inet\s+addr:(?P<ipaddr>\d+.\d+.\d+.\d+)\s+",
                    line,
                )
                if match is None:
                    match = re.match(
                        r"\s+inet\s(?P<ipaddr>\d+.\d+.\d+.\d+)\s+",
                        line,
                    )

                if match is None:
                    continue
                return match.group("ipaddr")
    return None


@tbot.testcase
def _lnx_get_ipaddr(
    lnx: linux.LinuxShell, name: str, ip6: bool = False, netcmd: str = "auto"
) -> str:
    """
    get the IP address of a network device, from "ip addr show" or
    "ifconfig" (lnx_netcmd())

    :param lnx: linux machine from which we want to get the ipaddr
    :param name: name of the interface
    :param ip6: set to true if you want the ipv6 addr
    :param netcmd: auto, ip or ifconfig
    """
    if lnx_netcmd(lnx, netcmd) == "ip":
        out = lnx.exec0("ip", "-6" if ip6 else "-4", "addr", "show", "dev", name)
        ipaddr = _ipaddr_from_ip(out, ip6)
    else:
        out = lnx.exec0("ifconfig", name)
        ipaddr = _ipaddr_from_ifconfig(out, ip6)
    if ipaddr is None:
        raise RuntimeError(f"Could not get ip for device {name}")
    return ipaddr


@tbot.testcase
def lnx_get_ipaddr(
    lnx: linux.LinuxShell,
    name: str,
    ip6: bool = False,
    poll: int = 5,
    sleep: int = 2,
    netcmd: str = "auto",
) -> str:
    """
    get the IP address of a network device, polling until it is there

    :param lnx: linux machine from which we want to get the ipaddr
    :param name: name of the interface
    :param ip6: set to true if you want the ipv6 addr
    :param poll: if != 0 poll n times to get the ip
    :param sleep: sleep in seconds between polls
    :param netcmd: auto, ip or ifconfig, see lnx_netcmd()
    """
    i = 0
    while i <= poll:
        try:
            return _lnx_get_ipaddr(lnx, name, ip6, netcmd)
        except Exception:
            if sleep:
                time.sleep(sleep)
            i += 1

    raise RuntimeError(f"Could not get ip for device {name}")


def lnx_network_ping(
    lnx: linux.LinuxShell,
    ip: str,
    retry: int,
) -> None:
    i = 0
    while i < retry:
        ret, out = lnx.exec("ping", ip, "-c", "1", "-W", "1")
        if ret == 0:
            return
        i += 1

    raise RuntimeError(f"Could not bring up device {ip}")


def lnx_network_up(
    lnx: linux.LinuxShell,
    device: str,
    ip: str,
    sip: str,
    retry: int,
    netmask: str = None,
) -> None:
    """
    set ip on device, with ip or ifconfig (lnx_netcmd()), and ping sip

    :param retry: pings to sip before giving up
    :param netmask: dotted netmask, default by the address class, as
        ifconfig without netmask
    """
    lnx_set_ipaddr(lnx, device, ip, netmask)
    lnx_network_ping(lnx, sip, retry)


def _check_iperf_installed(
    lnx: linux.LinuxShell,
    try_install: bool = True,
) -> bool:
    """
    check if iperf3 is installed on lnx machine

    If try_install try to install it if not
    """
    ret, out = lnx.exec("iperf3", "-v")
    if not ret:
        return True

    if not try_install:
        return False

    # Try to install iperf3 on OS; imported here, as tbottest.tc.common
    # imports from this module
    from tbottest.tc.common import lnx_install_package

    return lnx_install_package(lnx, "iperf3")


@tbot.testcase
def network_linux_iperf(
    lnx: linux.LinuxShell,
    lnxh: linux.LinuxShell,
    sip: str = "unknown",
    intervall: str = "5",
    cycles: str = "5",
    minval: str = "40",
    filename: str = "iperf.dat",
    subject: str = "unkown",
) -> bool:  # noqa: C901
    """
    start iperf measurement between lnx and lnxh machine

    toolname : iperf (oldversion) or iperf3

    lnxh : machine where iperf server runs
    lnx  : machine which start iperf client

    interval : seconds between periodic throughput reports
    cycles   : count of intervalls
    """

    toolname = "iperf3"
    pid = "notstarted"

    ret = _check_iperf_installed(lnx, try_install=False)
    if not ret:
        raise RuntimeError(f"Please install {toolname} in your rootfs")

    _check_iperf_installed(lnxh)

    result = []
    ymax = str(minval)
    step = str(float(intervall) / 2)
    xmax = str(int(cycles) * int(intervall))
    good = True
    # check if iperf is on rootfs, if not copy it
    # iperf = bbzu.copy_utility(lh, lnx, "iperf")
    # lnx.exec0("chmod", "+x", iperf)
    # check on labhost, if iperf server runs
    # if not start it
    ret = lnxh.exec0("ls", "-al", "/bin/ps")
    if "busybox" in ret:
        ret = lnxh.exec0("ps", linux.Pipe, "grep", toolname)
    else:
        ret = lnxh.exec0("ps", "afx", linux.Pipe, "grep", toolname)
    start = True
    for ln in ret.split("\n"):
        if "iperf" in ln and "grep" not in ln:
            start = False
    if start:
        # lnxh.exec0(toolname, "-s", linux.Background)
        lnxh.exec(linux.Raw(f"{toolname} -s 2>/dev/null 1>/dev/null &"))
        # lnxh.ch.sendline(f"{toolname} -s 2>&1 1>/dev/null &")
        time.sleep(3)
        # lnxh.ch.read_until_prompt()
        # wait as command has some output
        pid = lnxh.env("!")
        # lnxh.ch.sendline("iperf -s &")
        time.sleep(1)

    # log_event.doc_tag("iperf_minval", minval)
    # log_event.doc_tag("iperf_cycles", cycles)
    # log_event.doc_tag("iperf_intervall", intervall)
    # log_event.doc_begin("iperf_test")

    ret = lnx.exec0(toolname, "-c", sip, "-i", intervall, "-t", xmax)  # noqa: E501

    lowestval = "0"
    # output is something like
    # [  5]   4.00-5.00   sec  5.47 MBytes  45.9 Mbits/sec    0    102 KBytes
    # get Bitrate
    unit = "unknown"
    for ln in ret.split("\n"):
        if "- -" in ln:
            break

        if "Gbits/sec" in ln:
            unit = "Gbits/sec"
            mult = 1024 * 1024 * 1024

        if "Mbits/sec" in ln and unit == "unknown":
            unit = "Mbits/sec"
            mult = 1024 * 1024

        if "Kbits/sec" in ln and unit == "unknown":
            unit = "Kbits/sec"
            mult = 1024

        if "bits/sec" in ln and unit == "unknown":
            unit = "bits/sec"
            mult = 1

        if unit == "unknown":
            continue

        tmp = ln.split(unit)
        tmp = tmp[0].split("Bytes")
        val = tmp[-1].strip()
        val = float(val) * mult

        result.append({"bandwith": val, "step": step})
        if float(ymax) < float(val):
            ymax = val

        if float(val) < float(minval):
            if good:
                tbot.log.message(tbot.log.c(f"Not enough Bandwith {val} < {minval}").red)
                good = False

        if float(lowestval) > float(val):
            lowestval = val

        step = str(float(step) + float(intervall))

    # log_event.doc_tag("iperf_unit", unit)
    # log_event.doc_end("iperf_test")
    if pid != "notstarted":
        lnxh.exec("kill", pid, linux.Then, "wait", pid)

    if good:
        tbot.log.message(tbot.log.c(f"network Bandwith above {minval}").green)

    step = 0
    # round up ymax
    ymax = str(int(math.ceil(float(ymax) / 10.0)) * 10)
    fname = "results/iperf/" + filename
    try:
        fd = open(fname, "w")
    except Exception:
        tbot.log.message(
            tbot.log.c(
                f"could not open {fname}, May you create results/iperf, if you want to use the iperf results later"
            ).yellow
        )
        return good

    # save the xmax and ymax value behind the headlines
    # gnuplot uses them for setting the correct xmax / ymax values
    fd.write(f"step bandwith minimum {xmax} {ymax}\n")
    for el in result:
        fd.write(f'{el["step"]} {el["bandwith"]} {minval}\n')
        step += int(intervall)

    fd.close()

    return good
