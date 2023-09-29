import tbot
from tbot.machine import linux

from tbotconfig.ci.tests_helper import run_all_tests, FAILED, SUCCESS


@tbot.testcase
def uname(
    lab: linux.LinuxShell = None,
) -> bool:  # noqa: D107
    """
    simply try to connect to lab and exec0 uname
    """
    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)

        lab.exec0("uname", "-a")
        return SUCCESS

    return FAILED


lab_tests = [
    "uname",
]


@tbot.testcase
def laball() -> None:  # noqa: D107
    """
    start all tests on lab
    """
    return run_all_tests(lab_tests, "tbotconfig.ci.testlab", "LAB Host")
