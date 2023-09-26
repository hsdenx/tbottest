#
# collection of testcases, for CAN
# may go into mainline
#
import typing
from typing import List
import tbot
import time
import datetime
from tbot.machine import linux
from tbot.context import Optional
from tbottest.tc.common import tbot_start_thread
from tbottest.tc.common import tbot_stop_thread


def sudo_exec0(lnx: linux.LinuxShell, usesudo: bool, *args) -> str:
    if usesudo:
        return lnx.exec0("sudo", *args)

    return lnx.exec0(*args)


def get_lines(lnx: linux.LinuxShell, fi: str) -> int:
    out = lnx.exec0("wc", "-l", fi)
    cl = out.split(" ")
    return int(cl[0])


def board_setup_can(
    lnx: linux.LinuxShell,
    candev: List[str] = ["can0", "can1"],
    br: str = "500000",
    tql: str = "500",
    usesudo: bool = False,
) -> None:
    """
    setup the can interface on linux machine

    :param lnx: linux machine where we work on
    :param candev: List of candevices which get intialized
    :param br: used bitrate
    :param tql: use tx queuelen
    :param usesudo: if we need a sudo for calling ip command
    """

    for n in candev:
        sudo_exec0(lnx, usesudo, "ifconfig", n, "down")

    for n in candev:
        sudo_exec0(lnx, usesudo, "ip", "link", "set", n, "type", "can", "bitrate", br)
        sudo_exec0(lnx, usesudo, "ip", "link", "set", n, "txqueuelen", tql)

    for n in candev:
        sudo_exec0(lnx, usesudo, "ifconfig", n, "up")


def lnx_can_write_dump_compare(
    lab: linux.LinuxShell,
    lnx: linux.LinuxShell,
    lnxsend: linux.LinuxShell,
    senddev: List[str],
    lnxread: linux.LinuxShell,
    readdev: List[str],
    bitrate: str,
    txqueuelen: str,
    data: List[dict],
) -> None:
    """
    send in lnxsend shell with cansend over senddev the
    data and dump it with candump in lnxread shell on
    readdev. Use bitrate and txqueuelen

    :param lab: linux  machine where we work on
    :param lnx: linux machine where we work on
    :param lnxsend: linux machine from where we send CAN data
    :param senddev: List of device from which we send
    :param lnxread: linux machine where we receive CAN data
    :param readdev: devices from which we read
    :param bitrate: used bitrate
    :param txqueuelen: used txqueuelen
    :param data: List of dictionary, see below

    data is an dictionary with format:

    .. code-block:: python

        {"dev":"linux device name", "data":"data format strig for cansend", "res":"resulting line in dump file created from candump"}

    """
    # init can busses
    lnxsendsudo = False
    lnxreadsudo = False
    if lab == lnxsend:
        lnxsendsudo = True
    if lab == lnxread:
        lnxreadsudo = True

    board_setup_can(lnxsend, senddev, br=bitrate, tql=txqueuelen, usesudo=lnxsendsudo)
    board_setup_can(lnxread, readdev, br=bitrate, tql=txqueuelen, usesudo=lnxreadsudo)

    # logfiles in stdin: /tmp/thread_1_{tid} and stderr: /tmp/thread_2_{tid}
    tid = tbot_start_thread(lnxread, f"candump {readdev[0]}")

    for d in data:
        lnxsend.exec0("cansend", d["dev"], linux.Raw(d["data"]))

    tbot_stop_thread(tid, "-9")

    # check stderr
    log = lnxread.exec0(
        "wc",
        "-c",
        f"/tmp/thread_2_{tid}",
        linux.Pipe,
        "cut",
        "-d",
        linux.Raw('" "'),
        "-f",
        "1",
    )
    if int(log.strip()) != 0:
        tbot.log.message(tbot.log.c("found output in stderr").yellow)
        lnxread.exec0("cat", f"/tmp/thread_2_{tid}")

    log = lnxread.exec0("cat", f"/tmp/thread_1_{tid}")
    log = log.strip()
    i = 0
    ign = 0
    error = False
    for line in log.split("\n"):
        line = line.strip()
        if "interface" in line:
            i += 1
            ign += 1
            continue

        if line != data[i - ign]["res"]:
            tbot.log.message(
                tbot.log.c(
                    f"found difference in candump '{line}' != '{data[i - ign]['res']}' send: '{data[i - ign]['data']}'"
                ).red
            )
            error = True

        i += 1

    if error:
        raise RuntimeError("candump errors")


@tbot.testcase
def board_lnx_cangen(
    lab: typing.Optional[linux.LinuxShell] = None,
    lnx: Optional[linux.LinuxShell] = None,
    lnxsend: Optional[linux.LinuxShell] = None,
    labtbottestcasepath: str = None,
    tmpdir: str = "/tmp",
    candev: List[str] = ["can0", "can1"],
    candevsend: List[str] = ["can0"],
    candevdump: str = "can0",
    frames: str = "1000",
    dllength: str = "8",
    bitrate: str = "500000",
    txqueuelen: str = "500",
    cangen_gap: str = "10",
) -> None:
    """
    use cangen for generating testdata
    """
    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)

        if lnx is None:
            lnx = cx.request(tbot.role.BoardLinux)

        board_setup_can(lnx, candev, br=bitrate, tql=txqueuelen)
        # lnx.interactive()
        if lnxsend is None:
            lnxsend = lnx

        board_setup_can(lnxsend, candevsend, br=bitrate, tql=txqueuelen, usesudo=True)
        # lnx.interactive()
        for cs in candevsend:
            cand = "/tmp/candump.log"
            lnx.exec("rm", cand)
            # use logformat "-L" for candump output
            lnx.exec(linux.Raw(f"candump {candevdump} -L > {cand} 2>&1 &"))
            pid = lnx.env("!")

            # create data
            start = datetime.now()
            lnxsend.exec0(
                "cangen",
                "-g",
                cangen_gap,
                "-I",
                "i",
                "-L",
                dllength,
                "-D",
                "i",
                cs,
                "-n",
                frames,
            )

            # wait until all lines are in dump
            cl = get_lines(lnx, cand)
            stop = int(frames)
            retry = 4
            re = 0
            while cl < stop:
                time.sleep(1)
                clold = cl
                cl = get_lines(lnx, cand)
                if re < retry:
                    re += 1
                    continue
                if cl == clold:
                    lnx.interactive()
                    lnx.exec0("kill", pid, linux.Then, "wait", pid)
                    raise RuntimeError("Lost messages")

            end = datetime.now()
            lnx.exec0("kill", pid, linux.Then, "wait", pid)

            delta = end - start
            # length of one message
            bits = 1 + 1 + 11 + 6 + int(dllength) * 8 + 15 + 2 + 7 + 3
            alldata = int(frames) * bits

            realbitrate = alldata / delta.total_seconds()
            # lnx.interactive()

            # copy file to lab host and check it
            # ToDo use
            # lab.boardip["imx8mp"]
            # lab.workdir
            tmppath = lab.tmpdir()._local_str()
            df = f"{tmpdir}/candump.log"
            lab.exec0(
                "scp",
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "UserKnownHostsFile=/dev/null",
                f"root@192.168.3.21:{df}",
                tmppath,
            )
            ret, out = lab.exec("ls", "-1", f"{tmppath}/check_cangen_output.py")
            if ret != 0:
                if labtbottestcasepath is None:
                    raise RuntimeError("could not install check_cangen_output.py")
                else:
                    lab.exec0(
                        "scp",
                        "-o",
                        "StrictHostKeyChecking=no",
                        "-o",
                        "UserKnownHostsFile=/dev/null",
                        f"{labtbottestcasepath}/check_cangen_output.py",
                        tmppath,
                    )

            ret, out = lab.exec("python3", f"{tmppath}/check_cangen_output.py", "-i", df)
            if ret != 0:
                lnx.interactive()

            tbot.log.message(
                tbot.log.c(
                    f"send {frames} msgs with {dllength} databytes in {delta} from {cs} to {candevdump} with gap {cangen_gap} txqueuelen {txqueuelen} bitrate {bitrate} {realbitrate}"
                ).green
            )

            # lnx.interactive()
