"""
Boot counter testcases.

Generic, they make no assumption about where U-Boot keeps the counter.
Whatever the backing store, bootcount_inc() mirrors the value into the
running environment on every boot, so "printenv bootcount" reads it for all
of them.

What differs from board to board is how Linux puts the counter back to zero
after a boot that came up. That is handed in as a callable, and the two
common shapes are here as lnx_bootcount_reset_nvmem() and
lnx_bootcount_reset_fw_setenv().
"""

import typing
import tbot
from tbot.machine import board
from tbot.machine import linux
from tbot.context import Optional

def lnx_bootcount_reset_nvmem(
    lnx: linux.LinuxShell,
    device: str = "/sys/bus/nvmem/devices/*rtc*/nvmem",
) -> str:
    """
    reset the boot counter by zeroing the first word of an nvmem device

    For boards where U-Boot keeps the counter in a register through
    CONFIG_BOOTCOUNT_MEM and Linux reaches that register as nvmem. Only the
    count is cleared, the magic word next to it is left alone.

    :param lnx: linux machine to run on
    :param device: path of the nvmem device, a shell glob is allowed
    :return: the path that was written, for the log
    """
    log = lnx.exec0("sh", "-c", f"ls -d {device}")
    path = log.strip().splitlines()[0].strip()

    lnx.exec0("sh", "-c", f"printf '\\000\\000\\000\\000' > {path}")

    return path

def lnx_bootcount_reset_fw_setenv(
    lnx: linux.LinuxShell,
    name: str = "bootcount",
) -> str:
    """
    reset the boot counter through fw_setenv

    For boards using CONFIG_BOOTCOUNT_ENV, where the counter is a variable
    in the stored U-Boot environment.

    :param lnx: linux machine to run on
    :param name: name of the variable
    :return: the name that was written, for the log
    """
    lnx.exec0("fw_setenv", name, "0")

    return name

def ub_bootcount(ub: board.UBootShell) -> int:
    """
    the boot counter as U-Boot sees it

    :param ub: U-Boot machine to read from
    """
    ret, log = ub.exec("printenv", "bootcount")
    if ret != 0:
        raise RuntimeError(
            "'bootcount' is not set, is CONFIG_BOOTCOUNT_LIMIT enabled?"
        )

    return int(log.partition("=")[2].strip())

def _ub_env_or_empty(ub: board.UBootShell, name: str) -> str:
    """
    read a U-Boot variable, empty string when it is not defined
    """
    ret, log = ub.exec("printenv", name)
    if ret != 0:
        return ""

    return log.partition("=")[2].strip()

def _ub_bootcount_check(ub: board.UBootShell, expected: int, what: str) -> bool:
    """
    read the counter and compare, one green or red line either way
    """
    got = ub_bootcount(ub)

    if got != expected:
        tbot.log.message(tbot.log.c(f"bootcount is {got} {what}, expected {expected}").red)
        return False

    tbot.log.message(tbot.log.c(f"bootcount is {got} {what}").green)

    return True

@tbot.testcase
def board_ub_bootcount(
    lab: Optional[linux.LinuxShell] = None,
    reset: typing.Optional[typing.Callable[[linux.LinuxShell], str]] = None,
    warm_resets: int = 2,
) -> bool:
    """
    the boot counter counts, and Linux can put it back

    Three things, and none of them cares where the counter is stored:

    - a cold boot starts the count at 1
    - every warm reset adds one
    - once Linux has reset it, the next boot is back at 1

    The last one is the receipt the A/B fallback depends on. Without it the
    counter climbs until bootlimit and the board falls back although every
    boot came up fine.

    The board and the lab host are requested once and held, the U-Boot
    machine is built from the board object rather than requested as a role.
    Requesting it takes the board with exclusive=True, and an exclusively
    requested instance is torn down on release, which would power the board
    off between the resets.

    :param lab: lab host, requested when not given
    :param reset: called with the linux machine to clear the counter, see
        lnx_bootcount_reset_nvmem() and lnx_bootcount_reset_fw_setenv().
        When None the linux half is skipped and only the counting is
        checked.
    :param warm_resets: how many warm resets to do
    """
    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)

        b = cx.request(tbot.role.Board)
        ub_class = cx.get_machine_class(tbot.role.BoardUBoot)
        lnx_class = cx.get_machine_class(tbot.role.BoardLinux)

        retval = True
        had_nopoweroff = "nopoweroff" in tbot.flags

        # Letting go of a shell can reach the board, so keep its power for
        # the whole run. A board that gets switched off in between starts
        # counting at 1 again and the test would fail for the wrong reason.
        tbot.flags.add("nopoweroff")

        try:
            expected = 1
            what = "after power on"

            for i in range(warm_resets + 1):
                with ub_class(b) as ub:
                    if i == 0:
                        limit = _ub_env_or_empty(ub, "bootlimit")
                        if limit not in ("", "0") and 1 + warm_resets > int(limit):
                            warm_resets = max(int(limit) - 1, 0)
                            tbot.log.message(
                                f"bootlimit is {limit}, doing {warm_resets} warm "
                                "resets so altbootcmd does not kick in"
                            )

                    if not _ub_bootcount_check(ub, expected, what):
                        retval = False

                    if i < warm_resets:
                        # every U-Boot machine below has to have a boot to
                        # catch, so the reset goes out here and the block
                        # ends with it
                        ub.ch.sendline("reset")
                        expected += 1
                        what = "after a warm reset"
                    elif reset is not None:
                        with lnx_class(ub) as lnx:
                            name = reset(lnx)
                            tbot.log.message(tbot.log.c(f"boot counter reset through {name}").green)

                            lnx.ch.sendline("reboot")

            if reset is None:
                tbot.log.skip("the reset from linux, no reset function was given")
                return retval

            with ub_class(b) as ub:
                if not _ub_bootcount_check(ub, 1, "after the reset from linux"):
                    retval = False
        finally:
            if not had_nopoweroff:
                tbot.flags.discard("nopoweroff")

        return retval
