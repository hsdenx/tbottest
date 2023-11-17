import tbot
from tbot.machine import linux
from tbottest.tc import common

from tbotconfig.ci.tests_helper import run_all_tests, FAILED, SUCCESS


@tbot.testcase
def test_create_file(
    lab: linux.LinuxShell = None,
) -> bool:  # noqa: D107
    """
    test if file creation works
    """
    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)

        scriptname = "/tmp/createfiletest.sh"
        filedata = [
            "#!/bin/sh",
            "",
            "while true;do",
            "    sleep 5",
            "    echo hello world!",
            "done",
        ]
        common.lnx_create_file(lab, scriptname, filedata)
        log = lab.exec0("md5sum", scriptname)

        musthave = ["9385297f1a82efb7f1f48c931691a20b"]
        ret = common.search_multistring_in_multiline(musthave, log)
        if ret is not True:
            return FAILED

    return SUCCESS


@tbot.testcase
def test_sudo_subshell(
    lab: linux.LinuxShell = None,
) -> bool:  # noqa: D107
    """
    simply try to connect to lab and exec0 uname
    """
    with tbot.ctx() as cx:
        if lab is None:
            lab = cx.request(tbot.role.LabHost)

            cmds = ["whoami", "uname -a"]
            log = common.sudo_subshell(lab, cmds)
            # check if in log of first command is the string "root"
            musthave = ["root"]
            ret = common.search_multistring_in_multiline(musthave, log[0])
            if ret is not True:
                return FAILED

    return SUCCESS


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
    "test_create_file",
    "test_sudo_subshell",
    "uname",
]


@tbot.testcase
def laball() -> None:  # noqa: D107
    """
    start all tests on lab
    """
    return run_all_tests(lab_tests, "tbotconfig.ci.testlab", "LAB Host")
