#
# collection of testcases, for CAN
# may go into mainline
#
import re
import typing
from typing import List
import tbot
import time
from tbot.machine import linux
from tbot.context import Optional
from tbottest.tc.common import tbot_start_thread
from tbottest.tc.common import tbot_stop_thread
from tbottest.tc.common import lnx_sudo


def get_lines(lnx: linux.LinuxShell, fi: typing.Union[str, "linux.Path"]) -> int:
    out = lnx.exec0("wc", "-l", fi)
    cl = out.split(" ")
    return int(cl[0])


def _default_can_devices(
    candev: typing.Optional[List[str]], candevsend: typing.Optional[List[str]]
) -> typing.Tuple[List[str], List[str]]:
    if candev is None:
        candev = ["can0", "can1"]
    if candevsend is None:
        candevsend = ["can0"]
    return candev, candevsend


def board_setup_can(
    lnx: linux.LinuxShell,
    candev: typing.Optional[List[str]] = None,
    br: str = "500000",
    tql: str = "500",
) -> None:
    """
    setup the can interface on linux machine

    ip needs root rights, so the commands run with sudo unless lnx is
    logged in as root (:py:func:`tbottest.tc.common.lnx_sudo`).

    :param lnx: linux machine where we work on
    :param candev: List of candevices which get intialized
    :param br: used bitrate
    :param tql: use tx queuelen
    """
    if candev is None:
        candev = ["can0", "can1"]
    sudo = lnx_sudo(lnx)

    for n in candev:
        lnx.exec0(*sudo, "ip", "link", "set", n, "down")

    for n in candev:
        lnx.exec0(*sudo, "ip", "link", "set", n, "type", "can", "bitrate", br)
        lnx.exec0(*sudo, "ip", "link", "set", n, "txqueuelen", tql)

    for n in candev:
        lnx.exec0(*sudo, "ip", "link", "set", n, "up")


def lnx_can_write_dump_compare(
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

    :param lnxsend: linux machine from where we send CAN data
    :param senddev: List of device from which we send
    :param lnxread: linux machine where we receive CAN data
    :param readdev: devices from which we read
    :param bitrate: used bitrate
    :param txqueuelen: used txqueuelen
    :param data: List of dictionary, see below

    data is an dictionary with format:

    .. code-block:: python

        {
            "dev": "linux device name",
            "data": "data format strig for cansend",
            "res": "resulting line in dump file created from candump",
        }

    """
    # init can busses
    board_setup_can(lnxsend, senddev, br=bitrate, tql=txqueuelen)
    board_setup_can(lnxread, readdev, br=bitrate, tql=txqueuelen)

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
            expected = data[i - ign]["res"]
            sent = data[i - ign]["data"]
            tbot.log.message(
                tbot.log.c(
                    f"found difference in candump '{line}' != '{expected}' send: '{sent}'"
                ).red
            )
            error = True

        i += 1

    if error:
        raise RuntimeError("candump errors")


# frames of `cangen -I i`: the CAN ID counts up and wraps after the 11 bit
# standard IDs (cangen masks it with CAN_SFF_MASK)
CAN_SFF_IDS = 0x800

# a line of `candump -L`: (1598423840.039597) can0 08C#8C00000000000000
CANDUMP_LOG_LINE = re.compile(
    r"^\((?P<time>\d+\.\d+)\) (?P<dev>\S+) (?P<canid>[0-9A-Fa-f]+)#(?P<data>[0-9A-Fa-f]*)$"
)


def check_cangen_log(log: str, frames: int, dllength: int, candev: str) -> List[str]:
    """
    Check the ``candump -L`` log of ``cangen -I i -L <dllength> -D i -n <frames>``.

    cangen counts the CAN ID up from 0 (wrapping after 0x7FF) and the data,
    a little endian counter in the first ``dllength`` bytes, up from 0
    (wrapping after 256 ** dllength).  So frame n has CAN ID n % 0x800 and
    data n % 256 ** dllength.

    :param log: the output of ``candump -L``
    :param frames: number of frames cangen sent
    :param dllength: data length cangen used
    :param candev: interface candump read from
    :returns: the differences found, an empty list if the log matches
    """
    errors = []
    lines = [ln.strip() for ln in log.splitlines() if ln.strip()]
    if len(lines) != frames:
        errors.append(f"{len(lines)} frames in the candump log, {frames} sent")

    datawrap = 1 << (8 * dllength)
    for n, line in enumerate(lines):
        m = CANDUMP_LOG_LINE.match(line)
        if m is None:
            errors.append(f"line {n + 1} is no candump -L frame: {line!r}")
            continue
        if m.group("dev") != candev:
            errors.append(f"line {n + 1} from {m.group('dev')}, not {candev}: {line!r}")
        canid = int(m.group("canid"), 16)
        if canid != n % CAN_SFF_IDS:
            errors.append(f"line {n + 1} has CAN ID {canid:#x}, expected {n % CAN_SFF_IDS:#x}")
        data = bytes.fromhex(m.group("data"))
        if len(data) != dllength:
            errors.append(f"line {n + 1} has {len(data)} data bytes, expected {dllength}")
            continue
        value = int.from_bytes(data, "little")
        if value != n % datawrap:
            errors.append(f"line {n + 1} has data {value}, expected {n % datawrap}")

    return errors


def candump_log_duration(log: str) -> float:
    """seconds between the first and the last frame of a ``candump -L`` log"""
    times = []
    for line in log.splitlines():
        m = CANDUMP_LOG_LINE.match(line.strip())
        if m is not None:
            times.append(float(m.group("time")))
    if len(times) < 2:
        return 0.0
    return times[-1] - times[0]


@tbot.testcase
def board_lnx_cangen(
    lnx: Optional[linux.LinuxShell] = None,
    lnxsend: Optional[linux.LinuxShell] = None,
    tmpdir: str = "/tmp",
    candev: typing.Optional[List[str]] = None,
    candevsend: typing.Optional[List[str]] = None,
    candevdump: str = "can0",
    frames: str = "1000",
    dllength: str = "8",
    bitrate: str = "500000",
    txqueuelen: str = "500",
    cangen_gap: str = "10",
) -> None:
    """
    Send frames with cangen and check what candump received.

    For each interface of ``candevsend``, ``lnxsend`` sends ``frames``
    frames with incrementing CAN ID and data (``cangen -I i -D i``), and
    candump on ``lnx`` logs them from ``candevdump`` to ``tmpdir`` on the
    board.  The log is read back and checked with
    :py:func:`check_cangen_log`: number of frames, interface, CAN IDs, data
    length and data.  The transfer rate comes from the timestamps of the
    first and the last frame in the log.
    """
    candev, candevsend = _default_can_devices(candev, candevsend)
    nframes = int(frames)
    ndata = int(dllength)

    with tbot.ctx() as cx:
        if lnx is None:
            lnx = cx.request(tbot.role.BoardLinux)

        board_setup_can(lnx, candev, br=bitrate, tql=txqueuelen)
        if lnxsend is None:
            lnxsend = lnx

        board_setup_can(lnxsend, candevsend, br=bitrate, tql=txqueuelen)
        cand = linux.Workdir.static(lnx, tmpdir) / "candump.log"
        for cs in candevsend:
            lnx.exec("rm", "-f", cand)
            # use logformat "-L" for candump output
            lnx.exec("candump", candevdump, "-L", linux.Background(stdout=cand, stderr=cand))
            pid = lnx.env("!")

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

            # wait until all frames are in the log, or it stops growing
            cl = get_lines(lnx, cand)
            retry = 4
            tries = 0
            while cl < nframes:
                time.sleep(1)
                clold = cl
                cl = get_lines(lnx, cand)
                if tries < retry:
                    tries += 1
                    continue
                if cl == clold:
                    break
            lnx.exec0("kill", pid, linux.Then, "wait", pid)

            log = lnx.exec0("cat", cand)
            errors = check_cangen_log(log, nframes, ndata, candevdump)
            for e in errors[:20]:
                tbot.log.message(tbot.log.c(e).red)
            if errors:
                raise RuntimeError(
                    f"{len(errors)} differences in the candump log of {cs} -> {candevdump}"
                )

            # length of one message
            bits = 1 + 1 + 11 + 6 + ndata * 8 + 15 + 2 + 7 + 3
            duration = candump_log_duration(log)
            realbitrate = nframes * bits / duration if duration > 0 else 0.0

            tbot.log.message(
                tbot.log.c(
                    f"send {frames} msgs with {dllength} databytes in {duration:.3f} s from "
                    f"{cs} to {candevdump} with gap {cangen_gap} txqueuelen {txqueuelen} "
                    f"bitrate {bitrate} {realbitrate:.0f}"
                ).green
            )
