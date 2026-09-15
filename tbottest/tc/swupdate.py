"""
SWUpdate over the embedded web server.

The bundle is pushed from the lab host with curl, the way the SWUpdate
documentation describes it and the way a deployment does it, rather than
through a client on the board. tc/swu.py has the other two paths, the
swupdate_client.py example from the lab host and swupdate-client on the
board itself.

The upload returns as soon as the bundle is in, so whether the update
worked is taken from the swupdate journal on the board, read from a cursor
taken before the upload. Without that cursor an older run's success line
would answer for this one.

What an update is supposed to change is board specific and stays out of
here. board_swu_update() asks the board side for its expectations through
a callable, checks them, reboots and checks what came up.
"""

import time
import typing
import tbot
from tbot.machine import linux
from tbot.context import Optional

from tbottest.tc.systemd import systemd_active
from tbottest.tc.systemd import systemd_stop_service

#: default port of the swupdate web server, MG_PORT in mongoose_interface.c
SWU_PORT = 8080

#: what swupdate notifies at the end of an update, core/notifier.c
SWU_DONE_OK = "SWUPDATE successful !"
SWU_DONE_FAIL = "SWUPDATE failed"


def swu_stop_progress(lnx: linux.LinuxShell, name: str = "swupdate-progress") -> bool:
    """
    keep the board from rebooting the moment an update finishes

    swupdate-progress runs with -r and reboots as soon as it sees a
    successful update. A testcase wants to look at what the update wrote
    before anything acts on it, and it wants to decide itself when the
    reboot happens, so the service goes away first. tc/swu.py does the
    same before its updates.

    The service comes back with the next boot, so this is done again for
    every round rather than once.

    :param lnx: board linux machine
    :param name: name of the service
    :return: whether it was stopped
    """
    if not systemd_active(lnx):
        tbot.log.message(
            tbot.log.c("no systemd, cannot stop the progress service").yellow
        )
        return False

    try:
        systemd_stop_service(lnx, name)
    except RuntimeError:
        tbot.log.message(
            tbot.log.c(f"could not stop {name}, the board may reboot on its own").yellow
        )
        return False

    return True


def lnx_bootenv(lnx: linux.LinuxShell, name: str) -> str:
    """
    read a U-Boot environment variable from linux

    :param lnx: board linux machine
    :param name: name of the variable
    :return: the value, empty string when the variable is not set
    """
    ret, log = lnx.exec("fw_printenv", "-n", name)
    if ret != 0:
        return ""

    return log.strip()


def lnx_mount_source(lnx: linux.LinuxShell, mountpoint: str) -> str:
    """
    the device mounted at a mount point

    :param lnx: board linux machine
    :param mountpoint: path to look up, exactly as /proc/mounts spells it
    :return: the device, empty string when nothing is mounted there
    """
    log = lnx.exec0(
        "awk", "-v", f"m={mountpoint}", "$2 == m { print $1 }", "/proc/mounts"
    )

    return log.strip()


def swu_journal_cursor(lnx: linux.LinuxShell, unit: str = "swupdate") -> str:
    """
    a journal cursor pointing at the end of a unit's log right now

    Everything after it belongs to what happens next, which is what
    swu_wait_result() reads.

    :param lnx: board linux machine
    :param unit: name of the systemd unit
    :return: the cursor, empty string when journalctl did not give one
    """
    ret, log = lnx.exec(
        "journalctl", "--no-pager", "-u", unit, "-n", "0", "--show-cursor"
    )
    if ret != 0:
        return ""

    for line in log.splitlines():
        if line.startswith("-- cursor:"):
            return line.partition(":")[2].strip()

    return ""


def swu_wait_result(
    lnx: linux.LinuxShell,
    cursor: str = "",
    unit: str = "swupdate",
    timeout: int = 900,
    poll: int = 5,
) -> typing.Tuple[bool, str]:
    """
    wait for an update to finish and say whether it worked

    :param lnx: board linux machine
    :param cursor: journal cursor from swu_journal_cursor(), taken before
        the upload. Without one the whole log is read, and an older run
        can answer for this one.
    :param unit: name of the systemd unit
    :param timeout: seconds to wait for a verdict
    :param poll: seconds between two looks at the journal
    :return: whether it worked, and the log that says so
    """
    args = ["journalctl", "--all", "--no-pager", "-u", unit]
    if cursor:
        args += ["--after-cursor", cursor]

    waited = 0
    log = ""

    while waited <= timeout:
        log = lnx.exec0(*args)

        if SWU_DONE_OK in log:
            return True, log

        if SWU_DONE_FAIL in log:
            return False, log

        lnx.exec0("sleep", str(poll))
        waited += poll

    tbot.log.message(
        tbot.log.c(f"no result from {unit} within {timeout}s").red
    )

    return False, log


def swu_curl_upload(
    lab: linux.LinuxShell,
    swu: str,
    ipaddr: str,
    port: int = SWU_PORT,
    timeout: int = 900,
    field: str = "file",
) -> typing.Tuple[int, str]:
    """
    push a .swu to the board's web server with curl

    Runs on the lab host, so the bundle does not have to be on the board
    first, and the board installs while it receives.

    :param lab: lab linux machine, where curl runs and where the bundle is
    :param swu: the bundle, absolute path or a name in the lab's tftp dir
    :param ipaddr: address of the board
    :param port: port of the swupdate web server
    :param timeout: curl --max-time, the whole transfer
    :param field: name of the multipart field, swupdate takes any
    :return: curl's exit code and its output
    """
    if not swu.startswith("/"):
        swu = f"{lab.tftp_dir()._local_str()}/{swu}"

    ret, log = lab.exec("ls", "-l", swu)
    if ret != 0:
        raise RuntimeError(f"{swu} is not on the lab host")

    return lab.exec(
        "curl",
        "-sS",
        "--max-time",
        str(timeout),
        "-w",
        "curl_http_code=%{http_code}",
        "-F",
        f"{field}=@{swu}",
        f"http://{ipaddr}:{port}/upload",
    )


@tbot.testcase
def swu_install(
    lab: Optional[linux.LinuxShell] = None,
    lnx: Optional[linux.LinuxShell] = None,
    swu: str = None,
    ipaddr: str = None,
    port: int = SWU_PORT,
    timeout: int = 900,
) -> bool:
    """
    install a bundle and wait for the verdict

    Does not reboot, so the caller can look at what the update wrote
    before anything acts on it. swupdate-progress is stopped for the same
    reason, see swu_stop_progress().

    :param lab: lab linux machine
    :param lnx: board linux machine
    :param swu: the bundle, see swu_curl_upload()
    :param ipaddr: address of the board
    :param port: port of the swupdate web server
    :param timeout: seconds for the upload and for the install each
    :return: whether the update finished successfully
    """
    if swu is None:
        raise RuntimeError("please configure swu")
    if ipaddr is None:
        raise RuntimeError("please configure ipaddr")

    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)
        if lnx is None:
            lnx = cx.request(tbot.role.BoardLinux)

        swu_stop_progress(lnx)

        cursor = swu_journal_cursor(lnx)

        ret, log = swu_curl_upload(lab, swu, ipaddr, port, timeout)
        if ret != 0:
            tbot.log.message(tbot.log.c(f"curl failed: {log.strip()}").red)
            return False

        if "curl_http_code=200" not in log:
            tbot.log.message(tbot.log.c(f"upload was not accepted: {log.strip()}").red)
            return False

        ok, log = swu_wait_result(lnx, cursor, timeout=timeout)

        if not ok:
            tbot.log.message(tbot.log.c("update failed, the log follows").red)
            tbot.log.message(log)
            return False

        tbot.log.message(tbot.log.c("update installed").green)

        return True


def swu_check_bootenv(
    lnx: linux.LinuxShell,
    expected: typing.Dict[str, typing.Optional[str]],
    what: str = "",
) -> bool:
    """
    compare U-Boot environment variables with what they should be

    :param lnx: board linux machine
    :param expected: variable name to value. A value of None only reports
        what is there, for something the test cannot know beforehand.
    :param what: added to every message, to tell rounds apart
    :return: whether every named variable matched
    """
    retval = True

    for name, want in expected.items():
        got = lnx_bootenv(lnx, name)

        if want is None:
            tbot.log.message(f"{what}{name} is '{got}'")
            continue

        if got != want:
            tbot.log.message(
                tbot.log.c(f"{what}{name} is '{got}', expected '{want}'").red
            )
            retval = False
        else:
            tbot.log.message(tbot.log.c(f"{what}{name} is '{got}'").green)

    return retval


def swu_check_mounts(
    lnx: linux.LinuxShell,
    expected: typing.Dict[str, str],
    what: str = "",
) -> bool:
    """
    compare mount points with the devices that should be behind them

    :param lnx: board linux machine
    :param expected: mount point to device
    :param what: added to every message, to tell rounds apart
    :return: whether every mount point matched
    """
    retval = True

    for mountpoint, want in expected.items():
        got = lnx_mount_source(lnx, mountpoint)

        if got != want:
            tbot.log.message(
                tbot.log.c(
                    f"{what}{mountpoint} comes from '{got or 'nothing'}', "
                    f"expected '{want}'"
                ).red
            )
            retval = False
        else:
            tbot.log.message(tbot.log.c(f"{what}{mountpoint} comes from {got}").green)

    return retval


def _swu_update_install(
    lab: linux.LinuxShell,
    lnx: linux.LinuxShell,
    swu: str,
    ipaddr: str,
    port: int,
    timeout: int,
    expect: typing.Optional[typing.Callable],
    what: str,
    out: dict,
) -> bool:
    """
    the first half of a round: ask for the expectations, install, compare

    out carries the expectations back out, and out["installed"] says
    whether there is any point in rebooting at all.
    """
    if expect is not None:
        out["bootenv"], out["mounts"] = expect(lnx)

    out["installed"] = swu_install(lab, lnx, swu, ipaddr, port, timeout)
    if not out["installed"]:
        return False

    return swu_check_bootenv(lnx, out["bootenv"], what)


def _swu_update_verify(
    lnx: linux.LinuxShell,
    out: dict,
    check: typing.Optional[typing.Callable[[linux.LinuxShell], bool]],
    what: str,
) -> bool:
    """
    the second half: is the system that came up the one the update named
    """
    retval = swu_check_mounts(lnx, out["mounts"], what)

    # The environment is read a second time on purpose. Before the reboot
    # it was what the running system had written, here it is what the
    # bootloader actually used.
    if not swu_check_bootenv(lnx, out["bootenv"], what):
        retval = False

    if check is not None and not check(lnx):
        retval = False

    return retval


@tbot.testcase
def board_swu_update(
    lab: Optional[linux.LinuxShell] = None,
    swu: str = None,
    ipaddr: str = None,
    port: int = SWU_PORT,
    expect: typing.Optional[
        typing.Callable[
            [linux.LinuxShell],
            typing.Tuple[typing.Dict[str, typing.Optional[str]], typing.Dict[str, str]],
        ]
    ] = None,
    check: typing.Optional[typing.Callable[[linux.LinuxShell], bool]] = None,
    name: str = "",
    powercycle: bool = False,
    timeout: int = 900,
) -> bool:
    """
    install a bundle, then boot what it installed and look at it

    One round: read the expectations, install, check the environment the
    update wrote, reboot, and check that the system that came up is the
    one the environment names.

    The board and the lab host are requested once and held, the U-Boot and
    Linux machines are built from the board object rather than requested
    as roles. Requesting them takes the board with exclusive=True, and an
    exclusively requested instance is torn down on release, which would
    power the board off in the middle of the round.

    :param lab: lab host, requested when not given
    :param swu: the bundle, see swu_curl_upload()
    :param ipaddr: address of the board
    :param port: port of the swupdate web server
    :param expect: called with the linux machine before the update, with
        the board in the state the update will change. Returns what the
        U-Boot environment and the mount points should look like
        afterwards, as two dicts, see swu_check_bootenv() and
        swu_check_mounts(). This is where the board specific knowledge
        sits; nothing in here knows what a bundle means.
    :param check: called with the linux machine of the system that came
        up, for whatever else a board wants to look at. Returns whether
        that was in order.
    :param name: what to call this round in the log
    :param powercycle: cut the power instead of rebooting from linux. The
        eMMC is what the update wrote, so both work, but only this one
        also proves the ROM picks up a new bootloader from cold.
    :param timeout: seconds for the upload and for the install each
    :return: whether everything matched
    """
    if swu is None:
        raise RuntimeError("please configure swu")
    if ipaddr is None:
        raise RuntimeError("please configure ipaddr")

    what = f"{name}: " if name else ""

    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)

        b = cx.request(tbot.role.Board)
        ub_class = cx.get_machine_class(tbot.role.BoardUBoot)
        lnx_class = cx.get_machine_class(tbot.role.BoardLinux)

        had_nopoweroff = "nopoweroff" in tbot.flags

        # Letting go of a shell can reach the board, and a board that
        # loses power between the install and the boot would not tell us
        # whether the boot followed what the install wrote.
        tbot.flags.add("nopoweroff")

        out: dict = {"bootenv": {}, "mounts": {}, "installed": False}

        try:
            with ub_class(b) as ub:
                with lnx_class(ub) as lnx:
                    retval = _swu_update_install(
                        lab, lnx, swu, ipaddr, port, timeout, expect, what, out
                    )

                    if out["installed"] and not powercycle:
                        # every machine below has to have a boot to catch,
                        # so the reboot goes out here and the block ends
                        # with it
                        lnx.ch.sendline("reboot")

            if not out["installed"]:
                return False

            if powercycle:
                # poweroff() honours nopoweroff and does nothing while it
                # is set, see powercontrol.py. The flag is there to keep a
                # machine teardown from cutting the power, and this cycle
                # is not that, so it comes off for exactly these two
                # calls. Without this the board stays up, poweron() runs
                # on a running board and no boot is ever caught.
                tbot.flags.discard("nopoweroff")
                b.poweroff()
                time.sleep(5)
                b.poweron()
                tbot.flags.add("nopoweroff")

            with ub_class(b) as ub:
                with lnx_class(ub) as lnx:
                    if not _swu_update_verify(lnx, out, check, what):
                        retval = False
        finally:
            if not had_nopoweroff:
                tbot.flags.discard("nopoweroff")

        return retval
