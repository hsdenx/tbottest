import tbot
from tbot.machine import linux

from tbotconfig.ci.tests_helper import run_all_tests, FAILED, SUCCESS


@tbot.testcase
def uname(
    bh: linux.LinuxShell = None,
) -> bool:  # noqa: D107
    """
    simply try to connect to bh and exec0 uname
    """
    with tbot.ctx() as cx:
        if bh is None:
            bh = cx.request(tbot.role.BuildHost)

        log = bh.exec0("uname", "-a")
        contain = "Linux threadripper"
        bn = ""
        for flag in tbot.flags:
            if "buildername" in flag:
                bn = flag.split(":")[1]

        if "sisyphus" in bn:
            contain = "sisyphus.denx.de"

        if contain not in log:
            return FAILED

        return SUCCESS

    return FAILED


bh_tests = [
    "uname",
]


@tbot.testcase
def bhall() -> None:  # noqa: D107
    """
    start all tests on Build Host
    """
    return run_all_tests(bh_tests, "tbotconfig.ci.testbh", "Build Host")
