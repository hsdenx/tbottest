import tbot
from tbot.machine import linux
from tbot.context import Optional


@tbot.testcase
def systemd_stop_service(
    lnx: Optional[linux.LinuxShell] = None, name: str = "",
) -> None:  # noqa: D107
    """
    stops a service on linux machine lnx

    :param lnx: board linux machine
    :param name: name of the systemd service
    """
    with tbot.ctx() as cx:
        if lnx is None:
            lnx = cx.request(tbot.role.BoardLinux)

        rcode, log = lnx.exec("systemctl", "--all", "--no-pager", "stop", name)
        if rcode == 0:
            return

        raise RuntimeError(f"could not stop service {name}")


@tbot.testcase
def systemd_get_log_from_service(
    lnx: Optional[linux.LinuxShell] = None, name: str = "",
) -> str:  # noqa: D107
    """
    returns the log of a systemd service

    :param lnx: board linux machine
    :param name: name of the systemd service
    :return: log of "journalctl --all --no-pager -u name"
    """
    with tbot.ctx() as cx:
        if lnx is None:
            lnx = cx.request(tbot.role.BoardLinux)

        rcode, log = lnx.exec("journalctl", "--all", "--no-pager", "-u", name)
        if rcode == 0:
            return log

        raise RuntimeError(f"could not stop service {name}")


@tbot.testcase
def systemd_active(
    lnx: Optional[linux.LinuxShell] = None,
) -> bool:  # noqa: D107
    """
    check if systemd is installed

    :param lnx: board linux machine
    """
    with tbot.ctx() as cx:
        if lnx is None:
            lnx = cx.request(tbot.role.BoardLinux)

    ret, log = lnx.exec("ls", "/usr/lib/systemd")

    if ret != 0:
        return False

    return True
