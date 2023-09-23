import tbot
from tbot.machine import linux

@tbot.testcase
def lab_uname(
    lab: linux.LinuxShell = None,
) -> str:  # noqa: D107
    """
    simply try to connect to lab and exec0 uname
    """
    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)

        lab.exec0("uname", "-a")

