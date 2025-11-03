import contextlib
import re
import typing
import tbot
from tbot.machine import board
from tbot.context import Optional

def ub_read_register(ub: typing.Optional[board.UBootShell], address: str, bytesize: int = 4) ->str:
    """
    read a register in u-boot with md command
    return the value as a hex string
    """
    if bytesize == 1:
        bl = ".b"
    elif bytesize == 2:
        bl = ".w"
    elif bytesize == 4:
        bl = ".l"
    elif bytesize == 8:
        bl = ".q"
    else:
        raise RuntimeError(f"bytesize {bytesize} not allowed, [1,2,4,8]")

    log = ub.exec0(f"md{bl}", address, "1")
    rval = log.split(":")[1]
    rval = rval.split(" ")[1]
    val = f"0x{rval}"
    return val


@tbot.testcase
def board_ub_unit_test(
    ub: typing.Optional[board.UBootShell] = None,
) -> bool:  # noqa: D107
    """
    check if unit test command ut in U-Boot is activated
    and call it.
    """
    # check if ut command is installed, unfortunately
    # we cannot check return code, so parse log
    ret, log = ub.exec("ut")
    if "ut - unit tests" not in log:
        return True

    ret, log = ub.exec("ut", "all")
    result = None
    for l in log.split("\n"):
        if "Suites run" in l:
            result = l
            break

    if ret != 0:
        tbot.log.message(tbot.log.c(f"Failed {l}").red)
        return False

    tbot.log.message(tbot.log.c(f"Success {l}").green)
    return True
