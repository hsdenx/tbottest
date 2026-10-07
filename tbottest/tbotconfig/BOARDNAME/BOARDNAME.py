import os
import re
import sys
import tbot
import time
from datetime import datetime
from tbot.context import Optional

from tbot.machine import linux
from tbot.machine import board
from tbot.machine import connector

from tbottest.boardgeneric import cfggeneric
from tbottest.labgeneric import cfgt as cfglab
import tbottest.labgeneric as labgeneric

cfg = cfggeneric
server_nfs_path = cfg.get_default_config("nfs_path", "None")
si = cfg.get_default_config("serverip", "None")
nfspath = f"{cfg.tmpdir}/nfs"


################################################
# Lab
################################################
class BOARDNAMEPower(labgeneric.BOARDCON, labgeneric.BOARDCTL, board.Board):
    """
    the board with the power control configured in tbot.ini, only to
    call poweron() and poweroff(). It is never entered as a machine, so
    nothing powers the board on when it starts or off when it ends, and
    the console stays closed.
    """

    pass


@tbot.testcase
def BOARDNAME_power(
    lab: Optional[linux.LinuxShell] = None,
    state: str = "on",
) -> None:  # noqa: D107
    """
    switch the power of the board on or off, state is "on" or "off"

    The board stays in this state when tbot ends.
    """
    if state not in ("on", "off"):
        raise RuntimeError(f'power state {state} not supported, use "on" or "off"')

    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)

        power = BOARDNAMEPower(lab)
        if state == "on":
            power.poweron()
        else:
            # poweroff() does nothing while the flag nopoweroff is set,
            # which keeps the end of a board machine from switching the
            # board off. Here switching off is what is asked for.
            had_nopoweroff = "nopoweroff" in tbot.flags
            tbot.flags.discard("nopoweroff")
            try:
                power.poweroff()
            finally:
                if had_nopoweroff:
                    tbot.flags.add("nopoweroff")

        tbot.log.message(tbot.log.c(f"board BOARDNAME power {state}").green)


@tbot.testcase
def BOARDNAME_power_on(
    lab: Optional[linux.LinuxShell] = None,
) -> None:  # noqa: D107
    """
    switch the power of the board on
    """
    BOARDNAME_power(lab, "on")


@tbot.testcase
def BOARDNAME_power_off(
    lab: Optional[linux.LinuxShell] = None,
) -> None:  # noqa: D107
    """
    switch the power of the board off
    """
    BOARDNAME_power(lab, "off")


################################################
# U-Boot
################################################
@tbot.testcase
def BOARDNAME_ub_dummy(
    lab: Optional[linux.LinuxShell] = None,
    ub: Optional[board.UBootShell] = None,
) -> bool:  # noqa: D107
    """
    Dummy U-Boot example
    """
    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)

        if ub is None:
            ub = cx.request(tbot.role.BoardUBoot)

        ub.exec0("echo", "Hello World!")


from tbotconfig import tc_BOARDNAME

ub_testcases = ["BOARDNAME_ub_dummy"]


@tbot.testcase
def BOARDNAME_ub_all(
    lab: Optional[linux.LinuxShell] = None,
    ub: Optional[board.UBootShell] = None,
    interactive=False,
) -> None:  # noqa: D107
    """
    call all U-Boot tests
    """
    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)

        if ub is None:
            ub = cx.request(tbot.role.BoardUBoot)

        failed = 0
        success = 0
        count = 0
        tests = len(ub_testcases)

        for t in ub_testcases:
            count += 1
            tbot.log.message(
                tbot.log.c(
                    f"---- start test {t} {count} / {tests} suc: {success} fail: {failed} ----"
                ).yellow
            )
            func = getattr(tc_BOARDNAME, t, None)
            if func is None:
                tbot.log.message(tbot.log.c(f"---- test {t} not found ----").red)
                failed += 1
                continue

            try:
                ret = func()
            except Exception as e:
                tbot.log.message(tbot.log.c(f"---- test {t} failed: {e} ----").red)
                failed += 1
                continue

            # testcases without a result return None, only False fails
            if ret is False:
                tbot.log.message(tbot.log.c(f"---- test {t} failed ----").red)
                failed += 1
            else:
                success += 1

        if failed == 0:
            tbot.log.message(
                tbot.log.c(
                    f"---- tests {count} / {tests} suc: {success} fail: {failed} ----"
                ).green
            )
        else:
            tbot.log.message(
                tbot.log.c(
                    f"---- tests {count} / {tests} suc: {success} fail: {failed} ----"
                ).red
            )

        if interactive:
            ub.interactive()


################################################
# Linux
################################################
@tbot.testcase
def BOARDNAME_lx_dummy(
    lab: linux.LinuxShell = None,
    lnx: linux.LinuxShell = None,
    interactive=False,
) -> None:  # noqa: D107
    """ """
    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)

        if lnx is None:
            lnx = cx.request(tbot.role.BoardLinux)

        lnx.exec0("echo", "Hello Linux World!")

        if interactive:
            lnx.interactive()
