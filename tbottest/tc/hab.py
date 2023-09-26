import tbot
from tbot.machine import board
from tbot.context import Optional


@tbot.testcase
def ub_check_hab_state(
    ub: Optional[board.UBootShell] = None,
) -> str:
    """
    prerequisite: Board boots into U-Boot

    check output of U-Boot hab_status command
    if it does not report errors.

    :param ub: U-Boot machine
    :return: output of hab_status command
    """
    with tbot.ctx() as cx:
        if ub is None:
            ub = cx.request(tbot.role.BoardUBoot)

        out = ub.exec0("hab_status")

        if "HAB Configuration: 0xf0, HAB State: 0x66" not in out:
            raise RuntimeError("HAB Configuration error {out}")

        if "No HAB Events Found" not in out:
            raise RuntimeError("HAB Events found {out}")

        return out
