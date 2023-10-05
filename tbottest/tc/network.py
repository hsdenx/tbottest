import tbot
import time
from tbot.machine import linux
import math

from tbottest.tc.common import lnx_install_package


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
) -> None:
    lnx.exec0("ifconfig", device, "down", ip, "up")
    lnx_network_ping(lnx, sip, 5)

    raise RuntimeError(f"Could not bring up device {device}")


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

    # Try to install iperf3 on OS
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
    except:
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
