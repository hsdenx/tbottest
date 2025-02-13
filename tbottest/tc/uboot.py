import contextlib
import re
import typing
import tbot
from tbot.machine import board
from tbot.context import Optional

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
