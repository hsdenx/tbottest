#
# collection of testcases, for CAN
# may go into mainline
#
import typing
import tbot
from tbot.machine import linux
from tbot.context import Optional

from tbottest.tc.systemd import systemd_stop_service
from tbottest.tc.systemd import systemd_get_log_from_service
from tbottest.tc.systemd import systemd_active


@tbot.testcase
def board_lnx_check_swu(
    lab: typing.Optional[linux.LinuxShell] = None, usesshmachine: bool = False
) -> None:
    """
    check if swupdate-client.py is installed on lab host
    if not, try  install into lab.toolsdir

    :param lab: lab machine where we work on
    :param usesshmachine: set to True if you want to use labs sshmachine instead of lab
    """
    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)

        if lab.has_sshmachine() and usesshmachine:
            with lab.sshmachine() as lnxssh:
                _board_lnx_check_swu(lnxssh)
        else:
            _board_lnx_check_swu(lab)


def _board_lnx_check_swu(lab: typing.Optional[linux.LinuxShell] = None) -> None:
    p = lab.toolsdir()
    ret, out = lab.exec("ls", p / "swupdate_client.py")
    if ret == 0:
        return

    # swupdate-client.py not installed, try to install it
    tbot.log.message(
        tbot.log.c(f"swupdate-client.py not installed in {p}. Try to install it").green
    )
    lab.exec0("mkdir", "-p", p)
    lab.exec0("cd", p)
    lab.exec0(
        "wget",
        "https://raw.githubusercontent.com/sbabic/swupdate/master/examples/client/swupdate_client.py",
    )
    lab.exec0("chmod", "744", "swupdate_client.py")


@tbot.testcase
def board_lnx_swu(
    lab: typing.Optional[linux.LinuxShell] = None,
    lnx: Optional[linux.LinuxShell] = None,
    swuimage: str = None,
    ipaddr: str = None,
    usesshmachine: bool = False,
):
    """
    install swuimage with swupdate_client.py on lab_host to
    board with ipaddr.

    :param lab: lab linux machine
    :param lnx: board linux machine
    :param swuimage: path to swuimage
    :param ipaddr: address of board to where swuimage gets installed
    :param usesshmachine: set to True if you want to use labs sshmachine instead of lab
    """
    if swuimage is None:
        raise RuntimeError("please configure swuimage")
    if ipaddr is None:
        raise RuntimeError("please configure ipaddr")

    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)

        if lnx is None:
            lnx = cx.request(tbot.role.BoardLinux)

        board_lnx_check_swu(lab)

        systemd = systemd_active(lnx)

        if systemd:
            # stop progres if active
            # so we get no reboot after finished
            systemd_stop_service(lnx, "swupdate-progress")
            log = systemd_get_log_from_service(lnx, "swupdate")
        else:
            pid = lnx.exec0("pidof", "swupdate-progress").strip()
            lnx.exec("kill", pid, linux.Then, "wait", pid)
            # ToDo get log from swupdate

        if lab.has_sshmachine() and usesshmachine:
            with lab.sshmachine() as lnxssh:
                # copy file from labhost to sshmachine
                # copy only if different md5sums
                md5lab = lab.exec0(
                    "md5sum",
                    lab.tftp_dir() / swuimage,
                    linux.Pipe,
                    "cut",
                    "-d",
                    " ",
                    "-f",
                    "1",
                )
                ret, log = lnxssh.exec("ls", lnxssh.tftp_dir() / swuimage)
                if ret == 0:
                    md5ssh = lnxssh.exec0(
                        "md5sum",
                        lnxssh.tftp_dir() / swuimage,
                        linux.Pipe,
                        "cut",
                        "-d",
                        " ",
                        "-f",
                        "1",
                    )
                else:
                    md5ssh = "none"

                if md5ssh != md5lab:
                    tbot.tc.shell.copy(lab.tftp_dir() / swuimage, lnxssh.tftp_dir())

                return _board_lnx_swu(lnxssh, swuimage, ipaddr)
        else:
            return _board_lnx_swu(lab, swuimage, ipaddr)


def _board_lnx_swu(lab, swuimage, ipaddr):
    pa = lab.toolsdir()._local_str()
    pt = lab.tftp_dir()._local_str()
    rcode, log = lab.exec(f"{pa}/swupdate_client.py", f"{pt}/{swuimage}", ipaddr)

    return rcode, log


@tbot.testcase
def swu_swupdate_from_file(
    lab: Optional[linux.LinuxShell] = None,
    lnx: Optional[linux.LinuxShell] = None,
    swuimage: str = None,
) -> str:
    """
    update the software with swupdate on the lnx machine.

    Use swupdate-image binary on lnx machine with swupdate image
    swuimage (full path to swuimage)

    :param lab: lab linux machine
    :param lnx: board linux machine
    :param swuimage: path to swuimage
    """
    if swuimage is None:
        raise RuntimeError("please configure swuimage")

    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)
        if lnx is None:
            lnx = cx.request(tbot.role.BoardLinux)

        # stop progres if active
        # so we get no reboot after finished
        systemd_stop_service(lnx, "swupdate-progress")
        log = systemd_get_log_from_service(lnx, "swupdate")

        # extract values, so we can check if new values after swupdate are correct
        # ToDO

        rcode, log = lnx.exec("swupdate-client", "-v", swuimage)

        if rcode != 0:
            tbot.log.message(tbot.log.c("swupdate-client failed").red)
            raise RuntimeError("install swupdate-client failed, please fix")

        log = systemd_get_log_from_service(lnx, "swupdate")
        # ToDo
        # check output, check Environment variables...
        return log
