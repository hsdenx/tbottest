#
# collection of testcases, which may can go into mainline
#
import typing
import tbot
import time
from tbot.machine import linux
from tbot.machine import board
from tbot.context import Optional
import re
import contextlib

ENVCMD = None

@tbot.testcase
def check_yocto_build_install_sdk(
    lnx: linux.LinuxShell = None,
    sdk_install_path: str = None,
    sdk_path: str = None,
    sdk_name: str = None,
) -> None:  # noqa: D107
    """
    install SDK.

    :param lnx: board linux machine
    :param sdk_install_path: path to where the SDK gets installed
    :param sdk_path: path where to find the SDK installation scirpt
    :param sdk_name: SDK installation scripts name
    """
    if lnx == None:
        raise RuntimeError("Please set linux shell machine")
    if sdk_install_path == None:
        raise RuntimeError("Please set path to where SDK should be installed")
    if sdk_path == None:
        raise RuntimeError("Please set path to SDK installation script")
    if sdk_name == None:
        raise RuntimeError("Please set name of SDK installation script")

    lnx.exec0("pwd")
    lnx.exec0("mkdir", "-p", sdk_install_path)
    lnx.exec0("cd", sdk_install_path)
    lnx.exec0("rm", "-rf", linux.Raw("*"))
    lnx.exec0("cd", "-")
    log = lnx.exec0(f"{sdk_path}/{sdk_name}", "-y", "-d", sdk_install_path)
    # get command for sourcing environment script
    for l in log.split("\n"):
        if sdk_install_path in l:
            if "Proceed" in l:
                continue
            ENVCMD = l.split("$ . ")[1]

    if ENVCMD == None:
        raise RuntimeError("command for sourcing environment not found!")

    return ENVCMD

@tbot.testcase
def check_yocto_sdk_get_scriptname(
    lnx: linux.LinuxShell = None,
) -> None:  # noqa: D107
    """
    return scriptname of installed SDK

    :param lnx: board linux machine
    """
    return ENVCMD
