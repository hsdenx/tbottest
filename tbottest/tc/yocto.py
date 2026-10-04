import tbot
from tbot.machine import linux

ENVCMD = None

# hello world for checking an installed SDK
SDK_HELLO_C = """#include <stdio.h>

int main(void)
{
    printf("Hello World from the SDK\\n");
    return 0;
}
"""
SDK_HELLO_OUTPUT = "Hello World from the SDK"


def yocto_sdk_envcmd_from_log(log: str, sdk_install_path: str):
    """
    returns the path of the environment setup script from the output of
    the SDK installer, which ends with a line like
    " $ . <sdk_install_path>/environment-setup-<target>", or None
    """
    for line in log.split("\n"):
        if sdk_install_path in line and "$ . " in line:
            return line.split("$ . ", 1)[1].strip()
    return None


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
    :returns: path of the environment setup script, also kept for
        check_yocto_sdk_get_scriptname()
    """
    global ENVCMD

    if lnx is None:
        raise RuntimeError("Please set linux shell machine")
    if sdk_install_path is None:
        raise RuntimeError("Please set path to where SDK should be installed")
    if sdk_path is None:
        raise RuntimeError("Please set path to SDK installation script")
    if sdk_name is None:
        raise RuntimeError("Please set name of SDK installation script")

    # start from an empty install directory; removed by its absolute path,
    # never with a wildcard in whatever the current directory is
    if not sdk_install_path.startswith("/") or sdk_install_path.rstrip("/") == "":
        raise RuntimeError(f"SDK install path {sdk_install_path!r} must be absolute, not /")
    lnx.exec0("rm", "-rf", sdk_install_path)
    lnx.exec0("mkdir", "-p", sdk_install_path)
    log = lnx.exec0(f"{sdk_path}/{sdk_name}", "-y", "-d", sdk_install_path)
    # get command for sourcing environment script
    ENVCMD = yocto_sdk_envcmd_from_log(log, sdk_install_path)
    if ENVCMD is None:
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


@tbot.testcase
def check_yocto_sdk_build_hello(
    lnx: linux.LinuxShell = None,
    envcmd: str = None,
    builddir: linux.Path = None,
) -> linux.Path:  # noqa: D107
    """
    build a hello world program with an installed SDK

    :param lnx: linux machine the SDK is installed on
    :param envcmd: environment setup script of the SDK, as
        check_yocto_build_install_sdk() returns it
    :param builddir: directory on lnx, created if missing
    :returns: path of the program on lnx; run on the target it prints
        SDK_HELLO_OUTPUT
    """
    if lnx is None:
        raise RuntimeError("Please set linux shell machine")
    if envcmd is None:
        raise RuntimeError("Please set the environment setup script of the SDK")
    if builddir is None:
        raise RuntimeError("Please set the build directory")

    lnx.exec0("mkdir", "-p", builddir)
    src = builddir / "hello.c"
    src.write_text(SDK_HELLO_C)
    hello = builddir / "hello"
    lnx.exec0("rm", "-f", hello)
    # the environment script sets CC with the target flags, so it has to
    # stay unquoted; a subshell keeps the SDK environment out of lnx
    lnx.exec0(
        linux.Raw(
            f"(. {envcmd} && cd {builddir._local_str()} && $CC -o hello hello.c)"
        )
    )
    lnx.exec0("ls", "-l", hello)
    return hello
