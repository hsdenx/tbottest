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

# a frame of candump of canutils (Pengutronix), which has no -L:
# <0x08c> [8] 8c 00 00 00 00 00 00 00
CANDUMP_CANUTILS_LINE = re.compile(
    r"^<0x(?P<canid>[0-9A-Fa-f]+)> \[(?P<dlc>\d+)\](?P<data>(?: [0-9A-Fa-f]{2})*)$"
)

# the line candump of canutils prints before the frames
CANDUMP_CANUTILS_HEADER = re.compile(r"^interface = \S+, family = ")


def candump_is_canutils(lnx: linux.LinuxShell) -> bool:
    """
    True if candump on lnx is the one of canutils (Pengutronix), which has
    no log format -L and logs frames as ``<0x08c> [8] 8c 00 ...``, without
    timestamp and interface.  tbot's cmd_get_version() tells it from the
    candump of can-utils by its version output.
    """
    return lnx.cmd_get_version("candump").impl == "canutils"


def check_cangen_log(
    log: str, frames: int, dllength: int, candev: str, canutils: bool = False
) -> List[str]:
    """
    Check the candump log of ``cangen -I i -L <dllength> -D i -n <frames>``.

    cangen counts the CAN ID up from 0 (wrapping after 0x7FF) and the data,
    a little endian counter in the first ``dllength`` bytes, up from 0
    (wrapping after 256 ** dllength).  So frame n has CAN ID n % 0x800 and
    data n % 256 ** dllength.

    The log is the output of ``candump -L``, or with ``canutils`` the
    output of candump of canutils, which has no interface in its lines
    and starts with a header line.

    :param log: the output of candump
    :param frames: number of frames cangen sent
    :param dllength: data length cangen used
    :param candev: interface candump read from
    :param canutils: the log comes from candump of canutils
    :returns: the differences found, an empty list if the log matches
    """
    errors = []
    lines = [ln.strip() for ln in log.splitlines() if ln.strip()]
    if canutils:
        lines = [ln for ln in lines if not CANDUMP_CANUTILS_HEADER.match(ln)]
    if len(lines) != frames:
        errors.append(f"{len(lines)} frames in the candump log, {frames} sent")

    datawrap = 1 << (8 * dllength)
    for n, line in enumerate(lines):
        if canutils:
            m = CANDUMP_CANUTILS_LINE.match(line)
            if m is None:
                errors.append(f"line {n + 1} is no candump frame: {line!r}")
                continue
            data = bytes.fromhex(m.group("data").replace(" ", ""))
            if int(m.group("dlc")) != len(data):
                errors.append(f"line {n + 1} has length {m.group('dlc')} for {len(data)} bytes")
        else:
            m = CANDUMP_LOG_LINE.match(line)
            if m is None:
                errors.append(f"line {n + 1} is no candump -L frame: {line!r}")
                continue
            if m.group("dev") != candev:
                errors.append(f"line {n + 1} from {m.group('dev')}, not {candev}: {line!r}")
            data = bytes.fromhex(m.group("data"))
        canid = int(m.group("canid"), 16)
        if canid != n % CAN_SFF_IDS:
            errors.append(f"line {n + 1} has CAN ID {canid:#x}, expected {n % CAN_SFF_IDS:#x}")
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


def stop_candump(lnx: linux.LinuxShell, pid: str, timeout: float = 2.0) -> None:
    """
    Stop the candump started in the background on lnx with process id pid.

    candump of canutils only notices SIGTERM when the next frame arrives,
    its read() of the socket goes on after the signal. So if it still runs
    after timeout seconds, it is killed with SIGKILL. It writes every frame
    at once, so nothing gets lost.

    :param lnx: Linux machine candump runs on
    :param pid: process id of candump
    :param timeout: seconds to wait for candump to end after SIGTERM
    """
    lnx.exec("kill", pid)
    end = time.monotonic() + timeout
    while lnx.test("kill", "-0", pid):
        if time.monotonic() >= end:
            lnx.exec("kill", "-9", pid)
            break
        time.sleep(0.2)
    # wait reports the exit status of candump, 143 or 137 after a signal
    lnx.exec("wait", pid)


# directions of generic_lnx_test_cangen, who sends and who receives
CANGEN_DIRECTIONS = ("lab2board", "board2lab")

# keys of an entry of the board configuration key cangen
CANGEN_CONFIG_KEYS = (
    "boarddev",
    "labdev",
    "directions",
    "tmpdir",
    "frames",
    "dllength",
    "bitrate",
    "txqueuelen",
    "cangen_gap",
)


def cangen_config_calls(run: dict) -> List[typing.Tuple[str, dict]]:
    """
    The calls of :py:func:`board_lnx_cangen` for one entry of the board
    configuration key ``cangen``.

    ``boarddev`` and ``labdev`` name the CAN interfaces of the board and of
    the lab host, a list or a single interface. For every direction of
    ``directions`` (default both of :py:data:`CANGEN_DIRECTIONS`) the
    receiving side gets its interfaces as ``candev`` and candump reads from
    the first of them, the sending side gets its interfaces as
    ``candevsend``. The other keys of :py:data:`CANGEN_CONFIG_KEYS` go to
    every call as strings, as a JSON configuration may give numbers.

    :param run: one entry of ``cangen``
    :returns: the direction and the keyword arguments, without the
        machines, for every direction
    """
    unknown = sorted(set(run) - set(CANGEN_CONFIG_KEYS))
    if unknown:
        raise ValueError(
            f"unknown keys {unknown} in cangen, known are {', '.join(CANGEN_CONFIG_KEYS)}"
        )
    missing = [key for key in ("boarddev", "labdev") if key not in run]
    if missing:
        raise ValueError(f"cangen needs {', '.join(missing)}")

    def as_list(value: typing.Any) -> List[str]:
        values = value if isinstance(value, (list, tuple)) else [value]
        return [str(v) for v in values]

    boarddev = as_list(run["boarddev"])
    labdev = as_list(run["labdev"])
    directions = as_list(run.get("directions", CANGEN_DIRECTIONS))
    bad = [d for d in directions if d not in CANGEN_DIRECTIONS]
    if bad:
        raise ValueError(
            f"unknown directions {bad} in cangen, known are {', '.join(CANGEN_DIRECTIONS)}"
        )

    common = {
        key: str(value)
        for key, value in run.items()
        if key not in ("boarddev", "labdev", "directions")
    }
    calls = []
    for direction in directions:
        recv, send = (boarddev, labdev) if direction == "lab2board" else (labdev, boarddev)
        calls.append(
            (direction, dict(common, candev=recv, candevsend=send, candevdump=recv[0]))
        )
    return calls


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

    candump of canutils (Pengutronix, see :py:func:`candump_is_canutils`)
    has no log format ``-L``; its log has no interface and no timestamps,
    so these are not checked and the transfer rate is not reported.
    canutils has no cangen, ``lnxsend`` needs the one of can-utils.
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

        if not lnxsend.cmd_get_version("cangen").found:
            raise RuntimeError(
                f"cangen not found on {lnxsend.name}, it needs the one of can-utils "
                "(canutils of Pengutronix has none)"
            )

        board_setup_can(lnxsend, candevsend, br=bitrate, tql=txqueuelen)
        canutils = candump_is_canutils(lnx)
        # candump of canutils writes a header line before the frames
        nlines = nframes + 1 if canutils else nframes
        dumpopts = [] if canutils else ["-L"]
        cand = linux.Workdir.static(lnx, tmpdir) / "candump.log"
        for cs in candevsend:
            lnx.exec("rm", "-f", cand)
            lnx.exec("candump", candevdump, *dumpopts, linux.Background(stdout=cand, stderr=cand))
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
            while cl < nlines:
                time.sleep(1)
                clold = cl
                cl = get_lines(lnx, cand)
                if tries < retry:
                    tries += 1
                    continue
                if cl == clold:
                    break
            stop_candump(lnx, pid)

            log = lnx.exec0("cat", cand)
            errors = check_cangen_log(log, nframes, ndata, candevdump, canutils)
            for e in errors[:20]:
                tbot.log.message(tbot.log.c(e).red)
            if errors:
                raise RuntimeError(
                    f"{len(errors)} differences in the candump log of {cs} -> {candevdump}"
                )

            if canutils:
                tbot.log.message(
                    tbot.log.c(
                        f"send {frames} msgs with {dllength} databytes from {cs} to "
                        f"{candevdump}; candump of canutils has no timestamps, no bitrate"
                    ).green
                )
                continue

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
