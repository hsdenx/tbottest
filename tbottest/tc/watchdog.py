"""
Watchdog testcases.

A watchdog that is never tested is a watchdog that may not work, and the way
to test one is to stop feeding it and see the board come back. That is what
board_lnx_watchdog_bites() does.

Generic: what feeds the watchdog is a systemd service whose name is handed
in, and what a reset looks like from the bootloader is handed in as a
callable, because only the board knows which register says so and what it
says.
"""

import typing
import tbot
from tbot.machine import linux
from tbot.context import Optional


def lnx_service_main_pid(lnx: linux.LinuxShell, service: str) -> str:
    """
    the main PID of a systemd service, empty string when it is not running

    :param lnx: board linux machine
    :param service: name of the service
    """
    ret, log = lnx.exec("systemctl", "show", "-p", "MainPID", "--value", service)
    if ret != 0:
        return ""

    pid = log.strip()

    return "" if pid in ("", "0") else pid


def lnx_pid_holds(lnx: linux.LinuxShell, pid: str, path: str) -> bool:
    """
    does this process hold that file open

    Reads /proc/<pid>/fd rather than using fuser or lsof, so it works on an
    image that ships neither.

    :param lnx: board linux machine
    :param pid: process id as a string
    :param path: the file to look for
    """
    ret, log = lnx.exec(
        "sh",
        "-c",
        f"for f in /proc/{pid}/fd/*; do readlink $f; done",
    )
    if ret != 0:
        return False

    return path in log.split()


@tbot.testcase
def board_lnx_watchdog_bites(
    lab: Optional[linux.LinuxShell] = None,
    service: str = "",
    device: str = "/dev/watchdog",
    check: typing.Optional[typing.Callable[[typing.Any], bool]] = None,
    boot_timeout: float = 120,
) -> bool:
    """
    stop feeding the watchdog and prove that it resets the board

    The one test a watchdog cannot pass on paper. Everything up to here can
    look right, the service can be running and the device can be open, and
    the watchdog can still be doing nothing because the bootloader never
    started it or because the kernel is quietly feeding it instead.

    The run: check that the service holds the device, stop it, and wait for
    the board to come up in the bootloader on its own. Nobody asked it to
    reboot, so arriving there at all is the result. What kind of reset it
    was is left to the caller through check(), and the board is booted back
    into linux at the end so it is not left sitting at a prompt.

    The board and the lab host are requested once and held, the U-Boot and
    Linux machines are built from the board object rather than requested as
    roles. Requesting them takes the board with exclusive=True, and an
    exclusively requested instance is torn down on release, which would
    power the board off in the middle of the run and answer the question
    with a power cycle instead of a watchdog.

    :param lab: lab host, requested when not given
    :param service: the systemd service that feeds the watchdog
    :param device: the watchdog device that service is expected to hold
    :param check: called with the U-Boot machine that came up after the
        reset, for whatever the board can say about what kind of reset it
        was. Returns whether that was the expected kind.
    :param boot_timeout: seconds to wait for the board to come back. The
        budget is the watchdog timeout, which starts at the last feed just
        before the service was stopped, plus the boot to the prompt. Set so
        that a watchdog which does not bite fails the testcase instead of
        hanging it.
    """
    if service == "":
        raise RuntimeError("please configure service")

    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)

        b = cx.request(tbot.role.Board)
        ub_class = cx.get_machine_class(tbot.role.BoardUBoot)
        lnx_class = cx.get_machine_class(tbot.role.BoardLinux)

        # Same machine, but it gives up waiting. Without a boot_timeout the
        # connector waits for the prompt forever, and a watchdog that does
        # not bite would hang the run rather than fail it.
        ub_wait_class = type(
            "UBootWaitForWatchdog", (ub_class,), {"boot_timeout": boot_timeout}
        )

        retval = True
        had_nopoweroff = "nopoweroff" in tbot.flags

        # The whole point is that the board resets by itself. A teardown
        # that cuts the power would look exactly the same from the outside.
        tbot.flags.add("nopoweroff")

        try:
            with ub_class(b) as ub:
                with lnx_class(ub) as lnx:
                    pid = lnx_service_main_pid(lnx, service)
                    if pid == "":
                        tbot.log.message(
                            tbot.log.c(
                                f"{service} is not running, nothing feeds {device}"
                            ).red
                        )
                        return False

                    if not lnx_pid_holds(lnx, pid, device):
                        tbot.log.message(
                            tbot.log.c(
                                f"{service} runs as pid {pid} but does "
                                f"not hold {device}"
                            ).red
                        )
                        return False

                    tbot.log.message(
                        tbot.log.c(f"{service} holds {device} as pid {pid}").green
                    )

                    # Every machine below has to have a boot to catch, so
                    # the stop goes out here and the block ends with it.
                    # There is no prompt to wait for either: the shell dies
                    # with the board somewhere in the next seconds.
                    lnx.ch.sendline(f"systemctl stop {service}")

            tbot.log.message(
                f"{service} stopped, waiting up to {boot_timeout:.0f}s "
                "for the board to reset"
            )

            with ub_wait_class(b) as ub:
                tbot.log.message(
                    tbot.log.c("the board reset itself with nobody asking it to").green
                )

                if check is not None and not check(ub):
                    retval = False

                # Back into linux, so the board is left running rather than
                # sitting at a prompt with an unfed watchdog.
                with lnx_class(ub) as lnx:
                    pid = lnx_service_main_pid(lnx, service)
                    if pid == "":
                        tbot.log.message(
                            tbot.log.c(
                                f"{service} did not come back after the reset"
                            ).red
                        )
                        retval = False
                    else:
                        tbot.log.message(
                            tbot.log.c(f"{service} is feeding {device} again").green
                        )
        finally:
            if not had_nopoweroff:
                tbot.flags.discard("nopoweroff")

        return retval
